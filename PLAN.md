# ResolveDesk — Customer Support Resolution Agent

Project directory: `K:\ai-projects-for-portfolio\gptone`

## Outcome

Build a portfolio application that investigates ecommerce support tickets using retrieved policies and live order data, proposes a cited resolution, and executes approved actions in a simulated store. Include an evaluation dashboard that compares a basic RAG baseline with the full agent workflow.

Planning estimate: 4–6 weeks part-time, depending on experience and UI scope. External payment processing and real customer communications are outside the MVP.

## MVP boundaries

Support three ticket types:

1. Delayed delivery: inspect tracking and delivery policy; explain status or propose escalation.
2. Damaged item: inspect order eligibility and replacement inventory; propose a replacement or refund.
3. Refund status: inspect the refund ledger; explain status without creating a second refund.

Use one synthetic store, one currency, seeded customer accounts, products, inventory, orders, shipments, and refunds. Define explicit policy rules and effective dates. Include ineligible and ambiguous cases. The demo customer is authenticated through a seeded identity; ticket text must never select an arbitrary customer account.

## Demo experience

- Ticket inbox with filters for new, investigating, awaiting approval, resolved, and escalated tickets.
- Ticket detail showing the customer request, relevant order facts, policy citations, and proposed action.
- Live activity feed showing factual steps, tool results, and brief decision summaries, without exposing private model reasoning.
- Reviewer panel showing action type, order, amount or replacement item, policy basis, and approve/reject controls.
- Resolution receipt and audit history after execution.
- Evaluation page comparing baseline and agent quality, latency, and cost on a fixed dataset.
- Resettable demo data with three prepared scenarios and the option to enter another ticket.

## Stack and responsibilities

- FastAPI: authenticated APIs, ticket intake, run creation/status, SSE events, reviewer decisions, and evaluation summaries.
- LangGraph: typed workflow state, conditional investigation, bounded tool use, checkpoints, approval interrupts, and resumption.
- Python MCP server: typed store tools backed by the simulated commerce database.
- PostgreSQL with pgvector: application records, policy chunks/vectors, audit records, and graph checkpoints in separate logical tables.
- RAG: Markdown policies with section identifiers, metadata filtering, keyword/vector retrieval, and citations. Add reranking only if evaluation justifies it.
- Model adapter: configurable chat and embedding providers, with per-run model/version and token accounting.
- Ragas plus deterministic domain checks: retrieval/faithfulness evaluation and executable checks of policy, actions, and outcomes.
- React with TypeScript and Vite: frontend. FastAPI owns backend behavior; a second backend framework is unnecessary for this scope.
- Docker Compose: reproducible local database, API, MCP server, worker, and frontend.

Pin supported versions during implementation after checking official documentation.

## Workflow

Ticket intake → classify intent → retrieve policies → inspect order through MCP → assess missing evidence → propose resolution → validate eligibility → pause for approval if a mutation is needed → execute approved action → verify resulting store state → draft response → complete or escalate.

Read-only answers can complete without approval. Missing information produces a clarification request. Exhausted investigation budgets or unresolved contradictions produce escalation. Invalid model output receives one bounded repair attempt before escalation. Retry transient read failures; mutations use idempotency keys and persisted execution receipts.

Graph state includes ticket/customer IDs, intent, retrieved policy references, verified order facts, tool observations, proposed action, validation results, approval status, execution receipt, and run budget. Enforce a configurable maximum tool-call count and timeout per run.

The model proposes actions. Deterministic application code checks identity, ownership, eligibility, amounts, stock, allowed action types, and approval before execution. Revalidate mutable facts at execution time. Tie approval to the exact persisted proposal; changing it invalidates approval.

## MCP tools

Read tools:

- `get_order(order_id)`
- `get_shipment(order_id)`
- `get_refund_status(order_id)`
- `get_inventory(product_id)`
- `get_ticket_history(customer_id)`

Mutation tools:

- `create_replacement(order_id, item_id, approval_id, idempotency_key)`
- `issue_refund(order_id, amount, approval_id, idempotency_key)`
- `create_escalation(ticket_id, reason, idempotency_key)`

Use validated schemas and structured errors. Enforce access and approval within the server-side execution boundary, not merely through model instructions. Customer scope comes from trusted run context. Only reviewer-approved refunds/replacements change the simulated ledger; no real funds move. Do not send external messages in the MVP.

## API surface

- `POST /tickets`, `GET /tickets`, `GET /tickets/{id}`
- `POST /tickets/{id}/runs` returning a durable run ID
- `GET /runs/{id}` and `GET /runs/{id}/events` for status and reconnectable SSE
- `POST /runs/{id}/approval` for authorized approve/reject decisions
- `GET /runs/{id}/audit`
- `GET /evaluations` and `GET /evaluations/{id}`
- `GET /health`

Use a worker that claims persisted jobs rather than tying the entire graph run to an HTTP request. Persist events with sequence IDs so the UI can reconnect. Prevent duplicate active runs and duplicate approval handling.

## Evaluation design

Create 90 manually reviewed labeled cases: 60 development cases and 30 held-out cases. Balance the three intents and include missing facts, ineligibility, ambiguous wording, tool failures, duplicate submissions, malicious instructions embedded in ticket text, and cross-customer requests. Split by scenario family to reduce leakage.

Each case records fixture IDs, expected intent, required policy sections, expected resolution or escalation, permitted actions, and expected final store state. Reset store fixtures before every case. Agent action cases use an explicitly simulated reviewer decision. Keep judge results separate from deterministic checks.

Compare:

1. Basic RAG: ticket plus retrieved policy produces a recommendation.
2. Agent: policy retrieval plus live store tools and approved action execution.

Report both on shared recommendation/citation tasks. Report action completion separately because the RAG baseline cannot execute actions. Add a fixed-context tool-data baseline later if needed to isolate orchestration improvements from access to additional information.

Metrics:

- Correct resolution rate against case labels.
- End-to-end action success measured from final store state.
- Policy violation, unauthorized action, and duplicate mutation counts.
- Retrieval recall@k against labeled policy sections.
- Citation support and Ragas faithfulness; inspect sampled judge disagreements manually.
- Clarification/escalation correctness.
- Tool schema/argument validity and tool error recovery rate.
- p50/p95 automated run latency, excluding human approval waiting time; report approval wait separately.
- Input/output tokens, model-call count, tool-call count, and estimated model cost per case using recorded pricing assumptions.

Initial acceptance targets, not claimed results: at least 85% correct resolution on held-out cases; zero unauthorized or duplicate mutations in the test suite; all mutating actions linked to an audit receipt and valid approval. Report sample sizes and repeated-run variability. Record real measurements before writing résumé claims.

## Build sequence

### Phase 1 — Domain and API foundation

Define policy rules, seed the store, build ticket/order models and APIs, add seeded customer/reviewer authentication, and draft evaluation labels. Exit when three representative tickets and their expected outcomes can be reproduced from clean fixtures.

### Phase 2 — RAG baseline

Ingest versioned policies, implement retrieval and citation formatting, and run the baseline evaluation. Exit when every citation resolves to a stored policy section and baseline results are saved.

### Phase 3 — MCP and LangGraph investigation

Implement read tools, graph state, investigation routing, bounded retries, checkpoints, and clarification/escalation. Exit when the three intents retrieve live store facts and produce valid proposals.

### Phase 4 — Approval and reliable actions

Add reviewer interruption/resumption, deterministic eligibility validation, approved mutation tools, idempotency, and post-action verification. Exit when rejection, repeated approval, stale inventory, and worker restart scenarios preserve correct store state.

### Phase 5 — Product interface and observability

Build inbox, ticket detail, streamed activity, evidence panel, approval controls, receipts, and run metrics. Exit when a user can complete the seeded scenarios through the UI and reconnect to an active run.

### Phase 6 — Evaluation and portfolio packaging

Run held-out evaluation, inspect failures, publish a comparison report, package Docker startup and CI checks, and record a short demo. Exit when a fresh checkout can launch from documented steps and every reported résumé metric is traceable to a saved evaluation run.

## Suggested repository layout

```text
gptone/
  apps/api/
  apps/web/
  services/store_mcp/
  packages/agent/
  packages/retrieval/
  data/policies/
  data/fixtures/
  evals/cases/
  evals/reports/
  tests/
  docs/
  compose.yaml
  README.md
  PLAN.md
```

## Verification priorities

- Unit checks for policy eligibility, ownership, monetary calculations, and action validation.
- Integration checks for MCP schemas, workflow transitions, checkpoint resumption, and approval binding.
- Failure tests for timeouts, stale facts, duplicate requests, worker restarts, and untrusted ticket instructions.
- UI end-to-end checks for read-only resolution, approved replacement/refund, and rejected proposal.
- Offline evaluation in a separate reproducible command; keep paid model evaluations distinct from fast CI tests.

## Stretch features after the MVP

Hybrid retrieval tuning and reranking, multi-store isolation, a real sandbox commerce integration, redacted trace export, or regression checks across model versions. Add features in response to measured weaknesses. Avoid introducing multiple autonomous agents before the single workflow works reliably.

## Portfolio deliverables

A working demo, clean repository, architecture diagram, reproducible fixtures, labeled evaluation set, baseline-versus-agent report, documented failure cases, and a 2–3 minute walkthrough. A résumé bullet should describe the workflow and its actual measured quality, latency, and reliability results.
