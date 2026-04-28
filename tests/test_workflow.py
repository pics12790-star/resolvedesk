import json
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from resolvedesk import store
from resolvedesk.agent import build_graph, allowed_action


def start(tid="T-1001"):
    rid = store.create_run(tid)
    row = store.run(rid)
    ticket = store.ticket(tid)
    graph = build_graph(InMemorySaver())
    cfg = {"configurable": {"thread_id": rid}}
    import time

    graph.invoke(
        {
            "run_id": rid,
            "message": ticket["message"],
            "mode": "demo",
            "capability": row["capability"],
            "started": time.time(),
        },
        cfg,
    )
    return rid, graph, cfg


def decide(rid, graph, cfg, approve=True):
    state = dict(graph.get_state(cfg).values)
    store.save_state(rid, state, "awaiting_approval")
    aid = store.approve(rid, store.proposal_hash(state["proposal"]), approve, "reviewer")
    with store.connection() as db:
        db.execute("UPDATE runs SET status='running' WHERE id=?", (rid,))
    graph.invoke(Command(resume={"approved": approve, "approval_id": aid}), cfg)
    return dict(graph.get_state(cfg).values), aid


def test_approval_and_idempotent_receipt():
    rid, graph, cfg = start()
    assert graph.get_state(cfg).next == ("approval",)
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0
    state, aid = decide(rid, graph, cfg)
    assert state["status"] == "resolved"
    repeat = store.execute_action(store.run(rid)["capability"], aid)
    assert repeat == state["receipt"]
    with store.connection() as db:
        assert db.execute("SELECT stock FROM inventory WHERE product_id='P-1'").fetchone()[0] == 7
        assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 1


def test_rejection_never_mutates():
    rid, graph, cfg = start()
    state, aid = decide(rid, graph, cfg, False)
    assert state["status"] == "rejected"
    with pytest.raises(ValueError):
        store.execute_action(store.run(rid)["capability"], aid)
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0


def test_stale_inventory_escalates():
    rid, graph, cfg = start()
    with store.connection() as db:
        db.execute("UPDATE inventory SET stock=0 WHERE product_id='P-1'")
    state, _ = decide(rid, graph, cfg)
    assert state["status"] == "escalated"
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0


def test_cross_customer_capability_hides_order():
    tid = store.create_ticket("C-2", "Alex", "Damage", "My item is damaged", "ORD-1001")
    rid, graph, cfg = start(tid)
    state = graph.get_state(cfg).values
    assert state["proposal"]["action"] == "clarify"
    assert "product" not in state["evidence"]


def test_changed_proposal_invalidates_approval():
    rid, graph, cfg = start()
    state = dict(graph.get_state(cfg).values)
    store.save_state(rid, state, "awaiting_approval")
    digest = store.proposal_hash(state["proposal"])
    aid = store.approve(rid, digest, True, "reviewer")
    state["proposal"]["amount_cents"] = 999999
    store.save_state(rid, state, "running")
    with pytest.raises(ValueError):
        store.execute_action(store.run(rid)["capability"], aid)


def test_refund_status_does_not_refund_twice():
    _, graph, cfg = start("T-1003")
    assert graph.get_state(cfg).values["proposal"]["action"] == "answer"
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0


def test_refund_amount_is_exact():
    with store.connection() as db:
        db.execute("UPDATE inventory SET stock=0 WHERE product_id='P-1'")
    rid, graph, cfg = start()
    state, _ = decide(rid, graph, cfg)
    assert state["receipt"]["amount_cents"] == 12900
    with store.connection() as db:
        order = json.loads(db.execute("SELECT data FROM orders WHERE id='ORD-1001'").fetchone()[0])
        assert order["refund_status"] == "pending"


@pytest.mark.parametrize(
    "days,action", [(0, "replacement"), (30, "replacement"), (31, "escalate"), (-1, "escalate")]
)
def test_damage_window(days, action):
    assert (
        allowed_action(
            "damaged_item",
            {"id": "1", "shipment_status": "delivered", "delivered_days_ago": days, "stock": 1},
        )
        == action
    )


def test_only_one_active_run():
    assert store.create_run("T-1001") == store.create_run("T-1001")
