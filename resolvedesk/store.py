"""Transactional demo store with SQLite fallback and optional Neon/Postgres."""

import hashlib
import json
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from resolvedesk.config import DB

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None

DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_POSTGRES = DATABASE_URL.startswith(("postgresql://", "postgres://"))
UNLIMITED_STOCK = 1_000_000

IDENTITIES = {
    "reviewer": {"name": "Jordan Smith", "role": "reviewer", "customer_id": None},
    "maya": {"name": "Maya Chen", "role": "customer", "customer_id": "C-1"},
    "alex": {"name": "Alex Rivera", "role": "customer", "customer_id": "C-2"},
    "priya": {"name": "Priya Kapoor", "role": "customer", "customer_id": "C-3"},
}


class Row(dict):
    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class CursorAdapter:
    def __init__(self, cursor):
        self.cursor = cursor

    def _wrap(self, row):
        if row is None:
            return None
        columns = [column.name for column in self.cursor.description]
        return Row(columns, row)

    def fetchone(self):
        return self._wrap(self.cursor.fetchone())

    def __iter__(self):
        columns = [column.name for column in self.cursor.description]
        for row in self.cursor:
            yield Row(columns, row)


class PostgresConnection:
    def __init__(self, conn):
        self.conn = conn

    @staticmethod
    def _convert(sql):
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            return "BEGIN"
        return sql.replace("?", "%s")

    def execute(self, sql, args=()):
        cursor = self.conn.cursor()
        cursor.execute(self._convert(sql), args)
        return CursorAdapter(cursor)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def proposal_hash(proposal):
    return hashlib.sha256(json.dumps(proposal, sort_keys=True).encode()).hexdigest()


@contextmanager
def connection(path=DB):
    if USE_POSTGRES:
        if psycopg is None:
            raise RuntimeError("DATABASE_URL is set, but psycopg is not installed. Run `uv sync`.")
        db = PostgresConnection(psycopg.connect(DATABASE_URL))
    else:
        db = sqlite3.connect(path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def _create_schema(db):
    if USE_POSTGRES:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS products(
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              description TEXT NOT NULL,
              price_cents INTEGER NOT NULL CHECK(price_cents>=0),
              currency TEXT NOT NULL DEFAULT 'USD',
              unlimited INTEGER NOT NULL DEFAULT 0
            )
            """,
            "CREATE TABLE IF NOT EXISTS inventory(product_id TEXT PRIMARY KEY REFERENCES products(id), stock INTEGER NOT NULL CHECK(stock>=0))",
            "CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, data TEXT NOT NULL)",
            """
            CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, customer_name TEXT NOT NULL,
              subject TEXT NOT NULL, message TEXT NOT NULL, order_id TEXT, status TEXT NOT NULL, created DOUBLE PRECISION NOT NULL)
            """,
            """
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES tickets(id),
              status TEXT NOT NULL, state TEXT NOT NULL DEFAULT '{}', capability TEXT NOT NULL UNIQUE,
              created DOUBLE PRECISION NOT NULL, updated DOUBLE PRECISION NOT NULL, decision TEXT, error TEXT)
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON runs(ticket_id)
              WHERE status IN ('queued','running','awaiting_approval','resume_queued')
            """,
            """
            CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE REFERENCES runs(id),
              proposal_hash TEXT NOT NULL, approved INTEGER NOT NULL, reviewer TEXT NOT NULL, created DOUBLE PRECISION NOT NULL)
            """,
            """
            CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE, order_id TEXT NOT NULL,
              action TEXT NOT NULL, data TEXT NOT NULL, created DOUBLE PRECISION NOT NULL)
            """,
            """
            CREATE TABLE IF NOT EXISTS events(id BIGSERIAL PRIMARY KEY, run_id TEXT NOT NULL,
              kind TEXT NOT NULL, message TEXT NOT NULL, data TEXT NOT NULL, created DOUBLE PRECISION NOT NULL,
              UNIQUE(run_id,kind,message))
            """,
            "CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, identity TEXT NOT NULL, expires DOUBLE PRECISION NOT NULL)",
        ]
        for statement in statements:
            db.execute(statement)
        return

    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
      price_cents INTEGER NOT NULL CHECK(price_cents>=0), currency TEXT NOT NULL DEFAULT 'USD',
      unlimited INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS inventory(product_id TEXT PRIMARY KEY REFERENCES products(id), stock INTEGER NOT NULL CHECK(stock>=0));
    CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, data TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, customer_name TEXT NOT NULL,
      subject TEXT NOT NULL, message TEXT NOT NULL, order_id TEXT, status TEXT NOT NULL, created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES tickets(id),
      status TEXT NOT NULL, state TEXT NOT NULL DEFAULT '{}', capability TEXT NOT NULL UNIQUE,
      created REAL NOT NULL, updated REAL NOT NULL, decision TEXT, error TEXT);
    CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON runs(ticket_id)
      WHERE status IN ('queued','running','awaiting_approval','resume_queued');
    CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE REFERENCES runs(id),
      proposal_hash TEXT NOT NULL, approved INTEGER NOT NULL, reviewer TEXT NOT NULL, created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE, order_id TEXT NOT NULL,
      action TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
      kind TEXT NOT NULL, message TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL,
      UNIQUE(run_id,kind,message));
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, identity TEXT NOT NULL, expires REAL NOT NULL);
    """)


def init_db():
    with connection() as db:
        _create_schema(db)
        if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            # Older local demo databases already had inventory rows before the
            # products table existed. Clear those orphanable rows before adding
            # the product catalog.
            db.execute("DELETE FROM inventory")
            seed_products = [
                ("P-1", "Studio headphones", "Over-ear headphones used for the damaged-item replacement demo.", 12900, 0, 8),
                ("P-2", "Everyday backpack", "Backpack used for delayed-delivery support tickets.", 7900, 0, 5),
                ("P-3", "Desk lamp", "Lamp used for refund-status support tickets.", 6400, 0, 4),
                ("P-4", "USB-C cable", "Unlimited-stock accessory for quick order-number demos.", 1900, 1, UNLIMITED_STOCK),
                ("P-5", "Notebook pack", "Unlimited-stock low-risk product for repeated demos.", 1200, 1, UNLIMITED_STOCK),
            ]
            for pid, name, description, cents, unlimited, stock in seed_products:
                db.execute(
                    "INSERT INTO products(id,name,description,price_cents,currency,unlimited) VALUES(?,?,?,?,?,?)",
                    (pid, name, description, cents, "USD", unlimited),
                )
                db.execute("INSERT INTO inventory VALUES(?,?)", (pid, stock))

        if db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
            fixtures = [
                ("ORD-1001", "C-1", "Studio headphones", "P-1", 12900, "delivered", 4, 0, None),
                ("ORD-1002", "C-2", "Everyday backpack", "P-2", 7900, "in_transit", None, 2, None),
                ("ORD-1003", "C-3", "Desk lamp", "P-3", 6400, "delivered", 12, 0, "pending"),
            ]
            for oid, customer, product, pid, cents, shipping, days, late, refund in fixtures:
                data = _order_data(oid, customer, product, pid, cents, shipping, days, late, refund)
                db.execute("INSERT INTO orders VALUES(?,?,?)", (oid, customer, json.dumps(data)))

        if db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 0:
            tickets = [
                (
                    "T-1001",
                    "C-1",
                    "Maya Chen",
                    "My headphones arrived damaged",
                    "The headphones arrived with a cracked ear cup. Could you send a replacement?",
                    "ORD-1001",
                ),
                (
                    "T-1002",
                    "C-2",
                    "Alex Rivera",
                    "Where is my delivery?",
                    "My backpack is two days late. Can you check the delivery?",
                    "ORD-1002",
                ),
                (
                    "T-1003",
                    "C-3",
                    "Priya Kapoor",
                    "Has my refund been processed?",
                    "I returned my desk lamp. Could you check the status of my refund?",
                    "ORD-1003",
                ),
            ]
            for row in tickets:
                db.execute("INSERT INTO tickets VALUES(?,?,?,?,?,?,?,?)", (*row, "new", time.time()))


def _order_data(oid, customer_id, product, product_id, cents, shipment_status, days, late, refund):
    return {
        "id": oid,
        "customer_id": customer_id,
        "product": product,
        "product_id": product_id,
        "total_cents": cents,
        "currency": "USD",
        "shipment_status": shipment_status,
        "delivered_days_ago": days,
        "days_late": late,
        "refund_status": refund,
        "replacement_id": None,
    }


def list_products():
    with connection() as db:
        return [
            dict(row) | {"unlimited": bool(row["unlimited"])}
            for row in db.execute(
                """
                SELECT p.*,i.stock FROM products p
                JOIN inventory i ON i.product_id=p.id
                ORDER BY p.price_cents DESC
                """
            )
        ]


def create_order(customer_id, product_id, quantity=1):
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            """
            SELECT p.*,i.stock FROM products p
            JOIN inventory i ON i.product_id=p.id
            WHERE p.id=?
            """,
            (product_id,),
        ).fetchone()
        if not row:
            raise ValueError("Product not found")
        unlimited = bool(row["unlimited"])
        if not unlimited and row["stock"] < quantity:
            raise ValueError("This product is out of stock")
        if not unlimited:
            db.execute("UPDATE inventory SET stock=stock-? WHERE product_id=?", (quantity, product_id))
        oid = uid("ORD")
        data = _order_data(oid, customer_id, row["name"], row["id"], row["price_cents"] * quantity, "delivered", 0, 0, None)
        data["quantity"] = quantity
        db.execute("INSERT INTO orders VALUES(?,?,?)", (oid, customer_id, json.dumps(data)))
        return data


def create_ticket(customer_id, name, subject, message, order_id):
    tid = uid("T")
    with connection() as db:
        db.execute(
            "INSERT INTO tickets VALUES(?,?,?,?,?,?,?,?)",
            (tid, customer_id, name, subject, message, order_id, "new", time.time()),
        )
    return tid


def ticket(tid):
    with connection() as db:
        row = db.execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone()
        return dict(row) if row else None


def run(rid):
    with connection() as db:
        row = db.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
        if row:
            result = dict(row)
            result["state"] = json.loads(result["state"])
            return result


def public_run(rid):
    result = run(rid)
    if result:
        result.pop("capability", None)
        result["state"].pop("capability", None)
    return result


def create_run(tid):
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute(
            "SELECT id FROM runs WHERE ticket_id=? AND status IN ('queued','running','awaiting_approval','resume_queued')",
            (tid,),
        ).fetchone()
        if existing:
            return existing[0]
        rid = uid("R")
        db.execute(
            "INSERT INTO runs(id,ticket_id,status,capability,created,updated) VALUES(?,?,'queued',?,?,?)",
            (rid, tid, secrets.token_urlsafe(32), time.time(), time.time()),
        )
        db.execute("UPDATE tickets SET status='investigating' WHERE id=?", (tid,))
        return rid


def event(rid, kind, message, data=None):
    with connection() as db:
        if USE_POSTGRES:
            db.execute(
                """
                INSERT INTO events(run_id,kind,message,data,created) VALUES(?,?,?,?,?)
                ON CONFLICT(run_id,kind,message) DO NOTHING
                """,
                (rid, kind, message, json.dumps(data or {}), time.time()),
            )
        else:
            db.execute(
                "INSERT OR IGNORE INTO events(run_id,kind,message,data,created) VALUES(?,?,?,?,?)",
                (rid, kind, message, json.dumps(data or {}), time.time()),
            )


def events(rid, after=0):
    with connection() as db:
        return [
            dict(row) | {"data": json.loads(row["data"])}
            for row in db.execute("SELECT * FROM events WHERE run_id=? AND id>? ORDER BY id", (rid, after))
        ]


def save_state(rid, state, status):
    safe = {k: v for k, v in state.items() if k != "capability"}
    with connection() as db:
        db.execute(
            "UPDATE runs SET state=?,status=?,updated=? WHERE id=?",
            (json.dumps(safe), status, time.time(), rid),
        )
        row = db.execute("SELECT ticket_id FROM runs WHERE id=?", (rid,)).fetchone()
        db.execute("UPDATE tickets SET status=? WHERE id=?", (status, row[0]))


def approve(rid, digest, approved, reviewer):
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
        if not row:
            raise ValueError("Run not found")
        existing = db.execute("SELECT * FROM approvals WHERE run_id=?", (rid,)).fetchone()
        if existing:
            if existing["proposal_hash"] == digest and bool(existing["approved"]) == approved:
                return existing["id"]
            raise ValueError("This run already has a different reviewer decision")
        state = json.loads(row["state"])
        if row["status"] != "awaiting_approval" or proposal_hash(state.get("proposal")) != digest:
            raise ValueError("Proposal changed or run is not awaiting approval")
        aid = uid("A")
        db.execute(
            "INSERT INTO approvals VALUES(?,?,?,?,?,?)",
            (aid, rid, digest, int(approved), reviewer, time.time()),
        )
        db.execute(
            "UPDATE runs SET status='resume_queued',decision=?,updated=? WHERE id=?",
            (json.dumps({"approved": approved, "approval_id": aid}), time.time(), rid),
        )
        return aid


def scoped_order(db, capability):
    row = db.execute(
        "SELECT r.*,t.customer_id,t.order_id FROM runs r JOIN tickets t ON t.id=r.ticket_id WHERE r.capability=?",
        (capability,),
    ).fetchone()
    if not row:
        raise ValueError("Invalid run capability")
    order = db.execute(
        "SELECT data FROM orders WHERE id=? AND customer_id=?", (row["order_id"], row["customer_id"])
    ).fetchone()
    if not order:
        return row, None
    return row, json.loads(order[0])


def _stock_for(db, product_id):
    product = db.execute(
        """
        SELECT p.unlimited,i.stock FROM products p
        JOIN inventory i ON i.product_id=p.id
        WHERE p.id=?
        """,
        (product_id,),
    ).fetchone()
    if not product:
        return 0, False
    return (UNLIMITED_STOCK if product["unlimited"] else product["stock"]), bool(product["unlimited"])


def read_tool(name, capability):
    with connection() as db:
        row, order = scoped_order(db, capability)
        if not order:
            return {"error": "Order unavailable. Ask for a valid order number."}
        if name == "get_order":
            return {
                k: order[k]
                for k in (
                    "id",
                    "product",
                    "product_id",
                    "total_cents",
                    "currency",
                    "delivered_days_ago",
                    "replacement_id",
                )
            }
        if name == "get_shipment":
            return {k: order[k] for k in ("shipment_status", "days_late", "delivered_days_ago")}
        if name == "get_refund_status":
            return {"refund_status": order["refund_status"], "replacement_id": order["replacement_id"]}
        if name == "get_inventory":
            stock, unlimited = _stock_for(db, order["product_id"])
            return {"product_id": order["product_id"], "stock": stock, "unlimited": unlimited}
        if name == "get_ticket_history":
            return {
                "tickets": [
                    dict(r)
                    for r in db.execute(
                        "SELECT id,subject,status FROM tickets WHERE customer_id=? ORDER BY created DESC LIMIT 5",
                        (row["customer_id"],),
                    )
                ]
            }
        raise ValueError("Unknown tool")


def execute_action(capability, approval_id):
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row, order = scoped_order(db, capability)
        approval = db.execute(
            "SELECT * FROM approvals WHERE id=? AND run_id=?", (approval_id, row["id"])
        ).fetchone()
        proposal = json.loads(row["state"]).get("proposal")
        if not approval or not approval["approved"] or proposal_hash(proposal) != approval["proposal_hash"]:
            raise ValueError("A matching reviewer approval is required")
        existing = db.execute("SELECT data FROM receipts WHERE run_id=?", (row["id"],)).fetchone()
        if existing:
            return json.loads(existing[0])
        if row["status"] != "running":
            raise ValueError("Run is not executing")
        if not order or order["refund_status"] or order["replacement_id"]:
            raise ValueError("Order unavailable or already remedied")
        days = order["delivered_days_ago"]
        if order["shipment_status"] != "delivered" or days is None or not 0 <= days <= 30:
            raise ValueError("Order is no longer eligible")
        state = json.loads(row["state"])
        if state.get("intent") != "damaged_item":
            raise ValueError("Only damage cases can receive a remedy")
        stock, unlimited = _stock_for(db, order["product_id"])
        action = proposal["action"]
        receipt = {
            "id": uid("RCPT"),
            "order_id": order["id"],
            "action": action,
            "approval_id": approval_id,
            "simulated": True,
        }
        if action == "replacement" and stock > 0:
            if not unlimited:
                db.execute("UPDATE inventory SET stock=stock-1 WHERE product_id=?", (order["product_id"],))
            order["replacement_id"] = receipt["id"]
            receipt["product"] = order["product"]
        elif action == "refund" and stock == 0 and proposal.get("amount_cents") == order["total_cents"]:
            order["refund_status"] = "pending"
            receipt["amount_cents"] = order["total_cents"]
        else:
            raise ValueError("Stock or refund amount changed; manual review required")
        db.execute("UPDATE orders SET data=? WHERE id=?", (json.dumps(order), order["id"]))
        db.execute(
            "INSERT INTO receipts VALUES(?,?,?,?,?,?)",
            (receipt["id"], row["id"], order["id"], action, json.dumps(receipt), time.time()),
        )
        return receipt
