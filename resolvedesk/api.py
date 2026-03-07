import asyncio
import json
import mimetypes
import secrets
import threading
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from resolvedesk import store, retrieval
from resolvedesk.config import ROOT, REPORTS, agent_mode
from resolvedesk.models import TicketInput, ApprovalInput, LoginInput, PurchaseInput
from resolvedesk.worker import work

# Windows registry MIME associations can label .js as text/plain, blocking ES modules.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")


@asynccontextmanager
async def lifespan(app):
    store.init_db()
    stop = threading.Event()
    worker = threading.Thread(target=work, args=(stop,), daemon=True)
    worker.start()
    yield
    stop.set()
    worker.join(timeout=2)


app = FastAPI(title="ResolveDesk", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def same_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
        from urllib.parse import urlparse

        if urlparse(origin).netloc != request.headers.get("host"):
            return Response("Cross-origin mutations are not allowed", status_code=403)
    return await call_next(request)


def identity(request: Request):
    token = request.cookies.get("resolvedesk_session", "")
    with store.connection() as db:
        row = db.execute(
            "SELECT identity FROM sessions WHERE token=? AND expires>?", (token, time.time())
        ).fetchone()
    if not row:
        raise HTTPException(401, "Choose a demo identity to continue")
    return store.IDENTITIES[row[0]] | {"id": row[0]}


def reviewer(user=Depends(identity)):
    if user["role"] != "reviewer":
        raise HTTPException(403, "Reviewer access required")
    return user


def access_ticket(tid, user):
    ticket = store.ticket(tid)
    if not ticket or (user["role"] != "reviewer" and ticket["customer_id"] != user["customer_id"]):
        raise HTTPException(404, "Ticket not found")
    return ticket


def access_run(rid, user):
    row = store.public_run(rid)
    if not row:
        raise HTTPException(404, "Run not found")
    access_ticket(row["ticket_id"], user)
    return row


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "agent_mode": agent_mode(),
        "store": "neon-postgres" if store.USE_POSTGRES else "local-sqlite",
        "judge": "gpt-4o (API key required)",
    }


@app.post("/api/auth/demo")
def login(body: LoginInput, response: Response):
    token = secrets.token_urlsafe(32)
    with store.connection() as db:
        db.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
        db.execute("INSERT INTO sessions VALUES(?,?,?)", (token, body.identity, time.time() + 86400))
    response.set_cookie("resolvedesk_session", token, httponly=True, samesite="strict", max_age=86400)
    return store.IDENTITIES[body.identity] | {"id": body.identity}


@app.get("/api/auth/me")
def me(user=Depends(identity)):
    return user


@app.get("/api/tickets")
def list_tickets(user=Depends(identity)):
    with store.connection() as db:
        query = "SELECT * FROM tickets"
        args = ()
        if user["role"] != "reviewer":
            query += " WHERE customer_id=?"
            args = (user["customer_id"],)
        return [dict(r) for r in db.execute(query + " ORDER BY created DESC", args)]


@app.post("/api/tickets", status_code=201)
def create_ticket(body: TicketInput, user=Depends(identity)):
    # Reviewer-created demo tickets explicitly belong to Maya; text never controls identity.
    customer = user if user["role"] == "customer" else store.IDENTITIES["maya"]
    tid = store.create_ticket(
        customer["customer_id"], customer["name"], body.subject, body.message, body.order_id
    )
    return store.ticket(tid)


@app.get("/api/products")
def products(user=Depends(identity)):
    return store.list_products()


@app.post("/api/orders", status_code=201)
def create_order(body: PurchaseInput, user=Depends(identity)):
    # Reviewer purchases are created for Maya so an interviewer can demo the
    # customer path without switching identities first.
    customer = user if user["role"] == "customer" else store.IDENTITIES["maya"]
    try:
        return store.create_order(customer["customer_id"], body.product_id, body.quantity)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@app.get("/api/tickets/{tid}")
def get_ticket(tid: str, user=Depends(identity)):
    ticket = access_ticket(tid, user)
    with store.connection() as db:
        run_ids = [
            r[0] for r in db.execute("SELECT id FROM runs WHERE ticket_id=? ORDER BY created DESC", (tid,))
        ]
        order = db.execute(
            "SELECT data FROM orders WHERE id=? AND customer_id=?",
            (ticket["order_id"], ticket["customer_id"]),
        ).fetchone()
    return ticket | {
        "runs": [store.public_run(rid) for rid in run_ids],
        "order": json.loads(order[0]) if order else None,
    }


@app.post("/api/tickets/{tid}/runs", status_code=202)
def start_run(tid: str, user=Depends(identity)):
    access_ticket(tid, user)
    return {"id": store.create_run(tid)}


@app.get("/api/runs/{rid}")
def get_run(rid: str, user=Depends(identity)):
    return access_run(rid, user)


@app.post("/api/runs/{rid}/approval")
def approve(rid: str, body: ApprovalInput, user=Depends(reviewer)):
    access_run(rid, user)
    try:
        aid = store.approve(rid, body.proposal_hash, body.approve, user["id"])
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    return {"approval_id": aid}


@app.get("/api/runs/{rid}/audit")
def audit(rid: str, user=Depends(identity)):
    access_run(rid, user)
    return store.events(rid)


@app.get("/api/runs/{rid}/events")
async def stream(rid: str, request: Request, user=Depends(identity)):
    access_run(rid, user)
    try:
        cursor = int(request.headers.get("last-event-id", "0"))
    except ValueError:
        cursor = 0

    async def generate():
        nonlocal cursor
        while not await request.is_disconnected():
            for entry in store.events(rid, cursor):
                cursor = entry["id"]
                yield f"id: {cursor}\ndata: {json.dumps(entry)}\n\n"
            current = store.public_run(rid)
            yield f"event: status\ndata: {json.dumps({'status': current['status']})}\n\n"
            if current["status"] not in ("queued", "running", "resume_queued"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/policies")
def policies(user=Depends(identity)):
    return retrieval.policies()


@app.get("/api/evaluations")
def evaluations(user=Depends(reviewer)):
    reports = []
    for path in sorted(REPORTS.glob("*/summary.json"), reverse=True):
        reports.append(json.loads(path.read_text(encoding="utf-8")))
    return reports


@app.get("/api/evaluations/{eid}")
def evaluation(eid: str, user=Depends(reviewer)):
    if not eid.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(404)
    path = REPORTS / eid / "results.jsonl"
    if not path.exists():
        raise HTTPException(404)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if (ROOT / "apps/web/dist").exists():
    app.mount("/", StaticFiles(directory=ROOT / "apps/web/dist", html=True), name="web")
