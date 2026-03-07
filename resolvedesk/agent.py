import time
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from resolvedesk import mcp_client, providers, retrieval, store


class State(TypedDict, total=False):
    run_id: str
    message: str
    capability: str
    mode: str
    intent: str
    policies: list
    evidence: dict
    proposal: dict
    metrics: list
    tool_calls: int
    decision: dict
    receipt: dict
    status: str
    started: float
    automated_ms: float


def allowed_action(intent, facts):
    if facts.get("error") or not facts.get("id") or intent == "unknown":
        return "clarify"
    if intent == "damaged_item":
        days = facts.get("delivered_days_ago")
        if facts.get("refund_status") or facts.get("replacement_id"):
            return "escalate"
        if facts.get("shipment_status") != "delivered" or days is None or not 0 <= days <= 30:
            return "escalate"
        return "replacement" if facts.get("stock", 0) > 0 else "refund"
    if intent == "delayed_delivery":
        return (
            "answer"
            if facts.get("shipment_status") == "in_transit" and facts.get("days_late", 0) <= 3
            else "escalate"
        )
    if intent == "refund_status":
        return "answer" if facts.get("refund_status") in ("pending", "completed") else "escalate"
    return "clarify"


def build_graph(checkpointer):
    def classify(state):
        value, metric = providers.classify(state["message"], state["mode"])
        store.event(
            state["run_id"],
            "classify",
            "Request classified",
            {"intent": value["intent"], "provider": metric["provider"]},
        )
        return {"intent": value["intent"], "metrics": [metric]}

    def retrieve(state):
        docs = retrieval.retrieve(state["message"] + " " + state["intent"])
        store.event(
            state["run_id"], "retrieve", "Relevant policies retrieved", {"sources": [p["id"] for p in docs]}
        )
        return {"policies": docs}

    def investigate(state):
        tools = ["get_order"]
        if state["intent"] == "damaged_item":
            tools += ["get_shipment", "get_refund_status", "get_inventory"]
        elif state["intent"] == "delayed_delivery":
            tools += ["get_shipment"]
        elif state["intent"] == "refund_status":
            tools += ["get_refund_status"]
        for attempt in range(2):
            try:
                results = mcp_client.invoke([(name, {"capability": state["capability"]}) for name in tools])
                break
            except Exception:
                if attempt == 1:
                    raise RuntimeError("Commerce tools unavailable after two attempts") from None
        facts = {}
        for name, result in results.items():
            facts.update(result)
            store.event(state["run_id"], "tool", name, result)
        return {"evidence": facts, "tool_calls": len(tools) * (attempt + 1)}

    def propose(state):
        action = allowed_action(state["intent"], state["evidence"])
        proposal, metric = providers.propose(
            state["message"], state["intent"], state["evidence"], state["policies"], state["mode"], action
        )
        valid_ids = {p["id"] for p in state["policies"]}
        if (
            proposal["action"] != action
            or not proposal["citations"]
            or not set(proposal["citations"]) <= valid_ids
        ):
            proposal = {
                "action": "escalate",
                "explanation": "The generated proposal failed policy or citation validation.",
                "customer_response": "A support specialist needs to review this request.",
                "citations": [],
            }
            store.event(state["run_id"], "validation", "Proposal rejected by deterministic checks")
        else:
            store.event(state["run_id"], "validation", "Proposal passed policy and citation-ID checks")
        proposal["order_id"] = state["evidence"].get("id")
        proposal["amount_cents"] = (
            state["evidence"].get("total_cents") if proposal["action"] == "refund" else None
        )
        return {
            "proposal": proposal,
            "metrics": state["metrics"] + [metric],
            "automated_ms": (time.time() - state["started"]) * 1000,
        }

    def approval(state):
        decision = interrupt(
            {"proposal": state["proposal"], "proposal_hash": store.proposal_hash(state["proposal"])}
        )
        return {"decision": decision}

    def execute(state):
        if not state["decision"]["approved"]:
            store.event(state["run_id"], "approval", "Reviewer rejected the proposal")
            return {"status": "rejected"}
        started = time.time()
        try:
            result = mcp_client.invoke(
                [
                    (
                        "execute_approved_resolution",
                        {"capability": state["capability"], "approval_id": state["decision"]["approval_id"]},
                    )
                ]
            )
            receipt = result["execute_approved_resolution"]
            # Read back the resulting ledger through MCP before declaring completion.
            verified = mcp_client.invoke([("get_refund_status", {"capability": state["capability"]})])[
                "get_refund_status"
            ]
            ok = (
                verified.get("replacement_id") == receipt["id"]
                if receipt["action"] == "replacement"
                else verified.get("refund_status") == "pending"
            )
            if not ok:
                raise ValueError("Post-action verification failed")
            store.event(state["run_id"], "receipt", "Approved action executed and verified", receipt)
            return {
                "receipt": receipt,
                "status": "resolved",
                "tool_calls": state["tool_calls"] + 2,
                "automated_ms": state["automated_ms"] + (time.time() - started) * 1000,
            }
        except Exception:
            store.event(state["run_id"], "escalation", "Execution requires manual review; no automatic retry")
            return {"status": "escalated"}

    def complete(state):
        action = state["proposal"]["action"]
        status = state.get("status") or {
            "answer": "resolved",
            "clarify": "needs_information",
            "escalate": "escalated",
        }.get(action, "resolved")
        store.event(state["run_id"], "complete", "Investigation finished", {"status": status})
        return {"status": status}

    graph = StateGraph(State)
    for name, node in [
        ("classify", classify),
        ("retrieve", retrieve),
        ("investigate", investigate),
        ("propose", propose),
        ("approval", approval),
        ("execute", execute),
        ("complete", complete),
    ]:
        graph.add_node(name, node)
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "retrieve")
    graph.add_edge("retrieve", "investigate")
    graph.add_edge("investigate", "propose")
    graph.add_conditional_edges(
        "propose",
        lambda s: "approval" if s["proposal"]["action"] in ("refund", "replacement") else "complete",
    )
    graph.add_edge("approval", "execute")
    graph.add_edge("execute", "complete")
    graph.add_edge("complete", END)
    return graph.compile(checkpointer=checkpointer)
