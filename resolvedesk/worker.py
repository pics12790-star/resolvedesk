import json
import threading
import time
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from resolvedesk import store
from resolvedesk.agent import build_graph
from resolvedesk.config import CHECKPOINTS, agent_mode
from resolvedesk.tracing import runnable_config, traceable


@traceable(name="process_support_run", run_type="chain", tags=["worker", "resolvedesk"])
def process_run(graph, rid):
    row = store.run(rid)
    ticket = store.ticket(row["ticket_id"])
    mode = agent_mode()
    config = runnable_config(
        rid,
        ticket_id=row["ticket_id"],
        mode=mode,
        customer_id=ticket.get("customer_id"),
    )
    snapshot = graph.get_state(config)
    if row["decision"]:
        # A restart may occur after execution but before the final application status is saved.
        payload = Command(resume=json.loads(row["decision"])) if snapshot.next == ("approval",) else None
    elif snapshot.values:
        payload = None
    else:
        payload = {
            "run_id": rid,
            "message": ticket["subject"] + "\n" + ticket["message"],
            "capability": row["capability"],
            "mode": mode,
            "started": time.time(),
        }
    output = graph.invoke(payload, config)
    snapshot = graph.get_state(config)
    state = dict(snapshot.values or output)
    status = "awaiting_approval" if snapshot.next == ("approval",) else state.get("status", "failed")
    store.save_state(rid, state, status)
    if status == "awaiting_approval":
        store.event(
            rid,
            "approval",
            "Waiting for reviewer approval",
            {"proposal_hash": store.proposal_hash(state["proposal"])},
        )


def work(stop: threading.Event):
    # Single worker per local deployment; interrupted jobs are replayed from durable checkpoints.
    with store.connection() as db:
        db.execute(
            "UPDATE runs SET status=CASE WHEN decision IS NULL THEN 'queued' ELSE 'resume_queued' END WHERE status='running'"
        )
    with SqliteSaver.from_conn_string(str(CHECKPOINTS)) as saver:
        graph = build_graph(saver)
        while not stop.is_set():
            with store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT id FROM runs WHERE status IN ('queued','resume_queued') ORDER BY created LIMIT 1"
                ).fetchone()
                if row:
                    db.execute("UPDATE runs SET status='running',updated=? WHERE id=?", (time.time(), row[0]))
            if not row:
                stop.wait(0.25)
                continue
            rid = row[0]
            try:
                process_run(graph, rid)
            except Exception as exc:
                from resolvedesk.providers import ProviderUnavailable

                error = (
                    str(exc)
                    if isinstance(exc, ProviderUnavailable)
                    else f"Investigation failed ({type(exc).__name__}); inspect local diagnostics."
                )
                store.event(rid, "error", error)
                current = store.run(rid)
                store.save_state(rid, current["state"], "failed")
                with store.connection() as db:
                    db.execute("UPDATE runs SET error=? WHERE id=?", (error, rid))


if __name__ == "__main__":
    store.init_db()
    work(threading.Event())
