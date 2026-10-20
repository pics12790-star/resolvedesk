"""Export display-only walkthrough fixtures. Never export raw agent state or capabilities."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo"
REPORTS = ROOT / "evals/reports"
REPORT = REPORTS / "20261007T174736-luna"
rows = {
    r["case_id"]: r
    for r in map(json.loads, (REPORT / "results.jsonl").read_text(encoding="utf-8").splitlines())
}


def write(path, data):
    target = OUT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fields(data, names):
    return {k: data[k] for k in names if k in data}


SAFE_EVIDENCE = "id product product_id total_cents currency delivered_days_ago replacement_id shipment_status days_late refund_status stock unlimited refund_amount_cents".split()
SAFE_EVENT = (
    SAFE_EVIDENCE
    + "intent provider sources proposal_hash status action amount_cents order_id simulated".split()
)
POLICY = "id title text version score sha256 retrieval".split()
METRIC = "provider model input_tokens output_tokens latency_ms estimated_cost_usd".split()
PROPOSAL = "action explanation customer_response citations order_id amount_cents".split()
RECEIPT = "id order_id action simulated product amount_cents".split()

specs = [
    ("replacement", "Damaged item · replacement", "My headphones arrived damaged", "damage-stock-1", "maya"),
    ("delivery", "Delivery enquiry", "Where is my delivery?", "shipping-two-days-1", "alex"),
    ("refund-status", "Refund status enquiry", "Has my refund been processed?", "refund-pending-1", "priya"),
    (
        "refund",
        "Damaged item · refund approval",
        "Damaged headphones — request a refund",
        "damage-no-stock-1",
        "maya",
    ),
    (
        "escalation",
        "Delivered but missing · escalation",
        "Delivered, but my parcel is missing",
        "shipping-disputed-1",
        "alex",
    ),
]
manifest = []
for i, (sid, label, subject, case, owner) in enumerate(specs, 1):
    source = rows[case]
    state = source["state"]
    # Prefer the live browser run for the replacement workflow, when available.
    live = ROOT / "runtime/readme-luna/capture/workflow.json"
    if sid == "replacement" and live.exists():
        captured = json.loads(live.read_text(encoding="utf-8"))
        state, events = captured["run"]["state"], captured["audit"]
        message = state["message"].split("\n", 1)[-1]
        origin = "Live Luna workflow recorded 2026-10-20"
    else:
        events, message = source["events"], state["message"]
        origin = f"Saved benchmark case {case} · 2026-10-07"
    evidence = fields(state.get("evidence", {}), SAFE_EVIDENCE)
    oid = f"ORD-{1000 + i}"
    old_oid = evidence.get("id", state["proposal"].get("order_id", ""))

    def bind(value):
        if isinstance(value, dict):
            return {k: bind(v) for k, v in value.items()}
        if isinstance(value, list):
            return [bind(v) for v in value]
        return oid if value == old_oid else value

    evidence = bind(evidence)
    evidence["id"] = oid
    investigation = []
    for event in events:
        if event["kind"] in ("receipt", "complete", "approval", "error"):
            continue
        investigation.append(
            {
                "kind": event["kind"],
                "message": event["message"],
                "data": bind(fields(event.get("data", {}), SAFE_EVENT)),
            }
        )
    payload = {
        "id": sid,
        "label": label,
        "subject": subject,
        "message": message,
        "owner": owner,
        "source": origin,
        "order": {
            **evidence,
            "shipment_status": evidence.get("shipment_status", "delivered"),
            "refund_status": evidence.get("refund_status"),
            "replacement_id": None,
        },
        "state": {
            "intent": state["intent"],
            "policies": [fields(p, POLICY) for p in state["policies"]],
            "evidence": evidence,
            "proposal": bind(fields(state["proposal"], PROPOSAL)),
            "metrics": [fields(m, METRIC) for m in state.get("metrics", [])],
            "tool_calls": state.get("tool_calls", 0),
            "automated_ms": state.get("automated_ms", 0),
        },
        "investigation": investigation,
        "receipt": bind(fields(state.get("receipt", {}), RECEIPT)) or None,
        "status": state.get("status", "resolved"),
    }
    write(f"workflows/{sid}.json", payload)
    manifest.append(fields(payload, ["id", "label", "subject", "message", "owner", "source"]))
write("workflows/index.json", manifest)

policies = []
for path in sorted((ROOT / "data/policies").glob("*.md")):
    text = path.read_text(encoding="utf-8")
    heading, body = text.split("\n", 1)
    pid, title = heading.lstrip("# ").split(" | ", 1)
    policies.append(
        {
            "id": pid,
            "title": title,
            "text": body.strip(),
            "version": 1,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
    )
write("policies.json", policies)

summaries = []
for directory in sorted(REPORTS.iterdir(), reverse=True):
    if not (directory / "summary.json").exists() or not (directory / "results.jsonl").exists():
        continue
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    summaries.append(summary)
    safe_rows = []
    for line in (directory / "results.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        safe = fields(
            row,
            [
                "case_id",
                "split",
                "family",
                "expected_action",
                "actual_action",
                "correct",
                "intent_correct",
                "retrieval_hit",
                "retrieval_rank",
                "retrieval_method",
                "citation_ids_valid",
                "citation_precision",
                "action_success",
                "unauthorized_mutations",
                "duplicate_mutations",
                "latency_ms",
            ],
        )
        if row.get("judge"):
            safe["judge"] = fields(row["judge"], ["model", "scores"])
        safe_rows.append(safe)
    write(f"evaluations/{directory.name}.json", safe_rows)
write("evaluations/index.json", summaries)
print(f"Exported {len(manifest)} workflows, {len(policies)} policies, {len(summaries)} evaluation reports")
