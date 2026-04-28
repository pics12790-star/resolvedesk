# ResolveDesk

An evidence-backed customer support workspace built with **FastAPI, LangGraph, Gemini, MCP, React, and RAG**. It investigates delivery, damage, and refund-status tickets, proposes cited resolutions, and executes reviewer-approved remedies in a simulated store.

![ResolveDesk workspace](docs/design/desktop.png)

## Architecture

```mermaid
flowchart LR
  UI[React support workspace] --> API[FastAPI + SSE]
  API --> Jobs[Persisted job queue]
  Jobs --> Graph[LangGraph worker]
  Graph --> Gemini[Gemini structured output]
  Graph --> RAG[Versioned policy retrieval]
  Graph --> MCP[MCP stdio client / server]
  MCP --> Store[Transactional simulated store]
  Graph --> Approval[Durable approval interrupt]
  Approval --> API
  Graph --> Checkpoints[SQLite checkpoints]
  Eval[Evaluation harness] --> Graph
  Eval --> Judge[Optional GPT-4o judge]
  Eval --> Reports[JSONL traces + JSON metrics + Markdown]
```

- **LangGraph:** conditional investigation, policy checks, saved checkpoints, approval interrupt/resume, and post-action verification.
- **Gemini:** intent classification and structured, grounded resolution drafting. Deterministic code constrains allowed actions.
- **MCP:** actual JSON-RPC over stdio to a separate Python server; order, shipment, refund, inventory, history, and approved-resolution tools.
- **RAG:** Hybrid BM25 plus locally cached sentence-transformer embeddings over four versioned policy sections, fused with reciprocal rank fusion. If the embedding model is unavailable, retrieval falls back to the existing TF-IDF ranking. Citations resolve to exact source IDs and content hashes.
- **SQLite:** durable app records, transactions, idempotent receipts, and graph checkpoints. Each evaluation uses an isolated temporary database.
- **FastAPI:** cookie sessions, role/ownership checks, reconnectable event streams, ticket APIs, approval endpoints, and evaluation reports. API reference: `/docs`.

## Why this is not just a chatbot

ResolveDesk uses LLMs for bounded judgment, then surrounds them with deterministic product logic. The model classifies intent and drafts a grounded response, but code decides which actions are allowed, validates citations against retrieved policy IDs, blocks mutations until reviewer approval, and rechecks store state before executing anything.

That means the demo shows a real support workflow rather than a free-form chat box: tickets, evidence, policy retrieval, MCP tool calls, approval interrupts, receipts, audit events, and evaluation reports are all first-class product surfaces.

## Demo flow

Recommended short demo video or GIF: `Start investigation -> timeline -> cited policy -> approve replacement -> verified receipt`. If you record one, save it as `docs/design/demo.gif` and replace the screenshot strip below with the GIF.

| Inbox and evidence | Approval gate |
| --- | --- |
| ![Support inbox with ticket evidence](docs/design/inbox.png) | ![Reviewer approval state](docs/design/approval.png) |

| Verified receipt | Evaluation reports |
| --- | --- |
| ![Verified replacement receipt](docs/design/receipt.png) | ![Evaluation reports screen](docs/design/evaluations.png) |

## Try the workflow

1. Open the damaged-headphones ticket and click **Start investigation**.
2. Follow classification, policy retrieval, and MCP order/inventory checks.
3. Read the proposed replacement and cited damage policy.
4. **Approve replacement** as Jordan Smith. The app executes and verifies a simulated replacement, then displays its receipt.
5. Run the same ticket again: the existing remedy prevents a second replacement.
6. Investigate the delivery and refund-status tickets for read-only resolutions.
7. Switch demo identity to a customer to verify ticket isolation. Customers cannot approve actions.

New tickets created in reviewer mode explicitly belong to Maya Chen (`ORD-1001`). Alex owns `ORD-1002`; Priya owns `ORD-1003`. Order IDs embedded in message text never determine account scope.

## Safety model

- **Proposal hash binding:** reviewer decisions are tied to the complete proposal hash, so editing the proposed action, amount, or cited result invalidates the approval.
- **Run-scoped capabilities:** MCP tools receive a random internal capability for the support run, not customer-supplied IDs. The tool server resolves the authorized order and customer from that capability.
- **Transactional execution:** the store rechecks ownership, delivery window, inventory, prior remedies, and exact refund amount in the same transaction that writes the receipt.
- **Idempotent receipts:** each run can create only one receipt, and existing order remedies prevent duplicate refunds or replacements across runs.
- **Post-action verification:** after a mutation, the worker reads the ledger back through MCP before declaring the run resolved. Verification failures escalate instead of retrying blindly.
- **Visible failures:** missing credentials, model errors, unavailable tools, and rejected validations remain visible states rather than silently falling back to fake AI.

## Run locally

Requirements: Python 3.12+, Node.js 20+, and uv (or pip).

```powershell
cd K:\ai-projects-for-portfolio\gptone
uv sync --python 3.12
Copy-Item .env.example .env  # Only on a fresh checkout; don't overwrite existing credentials.
# Edit .env: set GEMINI_API_KEY. Never commit this file.
cd apps/web
npm ci
npm run build
cd ../..
uv run python -m uvicorn resolvedesk.api:app --host 127.0.0.1 --port 8000
```

Open **http://localhost:8000**. The FastAPI server serves the built frontend and starts one background worker. You can also run `./start.ps1` after installing dependencies. On this workstation a project-local Python 3.12 runtime is available under `runtime/python`; the existing `.venv` can run directly.

For frontend development, start the API and run `npm run dev` from `apps/web`; Vite proxies `/api` to FastAPI. The project deliberately uses React/Vite, not Next.js.

For an explicitly offline fixture demo, set `AGENT_MODE=demo`. The interface and reports label this as deterministic demo mode. Missing or rejected Gemini credentials do **not** silently fall back to simulated AI.

## Evaluate

The dataset contains 90 synthetic cases in 30 scenario families, with three surface variants per family. Family-level split: 60 development cases and 30 held-out cases. These are developer-authored fixtures, **not an independently human-reviewed benchmark**.

```powershell
# Fast tests: no model calls, real MCP subprocesses
uv run pytest -q
uv run ruff check resolvedesk evals tests

# Full deterministic workflow regression set
uv run python -m evals.run --mode demo

# One live Gemini case per family (30 total), paced for modest quotas
uv run python -m evals.run --mode gemini --limit 30 --workers 2 --interval 8

# Full 90-case Gemini run
uv run python -m evals.run --mode gemini --workers 2 --interval 8

# Retrieval-only Gemini baseline; no live store evidence
uv run python -m evals.run --mode gemini --baseline --limit 30 --workers 2 --interval 8

# Optional GPT-4o API judging, requires OPENAI_API_KEY
uv run python -m evals.run --mode gemini --judge gpt-4o --limit 30
```

Each run writes `evals/reports/<run-id>/config.json`, `results.jsonl`, `summary.json`, and `report.md`. Results include proposals, source texts, tool events, token counts, latency, actual store state, and errors. The UI reads these files. No API keys or capabilities are written to evaluation reports.

Measures include resolution accuracy, intent accuracy, retrieval recall@3, citation-ID validity, action success, unauthorized/duplicate mutations, p50/p95 latency, and token consumption. GPT-4o can separately score semantic faithfulness, citation support, helpfulness, and resolution correctness. Missing judgments are reported as **not run**, never fabricated. Optional price settings enable per-call cost estimates; absent prices mean unavailable, not free.

At the user's request, the initial qualitative review is performed by Codex and saved separately. **It is not a GPT-4o API evaluation.**

## Known limitations

- Demo identity switching is intentionally public for local testing. It is not production authentication.
- The default local store is SQLite. `DATABASE_URL` enables Postgres/Neon, but multi-worker production deployment is not the default path.
- Orders, payments, shipments, refunds, and replacement receipts are simulated fixtures. No real customer or commerce systems are mutated.
- The evaluation dataset is synthetic and developer-authored. It is useful for regression testing, not a human-reviewed production benchmark.
- Customer messages are sent to the configured model provider during live investigations. The included fixtures are synthetic.
- The local demo should be bound to loopback. Add real identity, secure cookies, rate limiting, deployment hardening, and secret management before exposing it publicly.

## Reliability notes

- Reviewer decisions bind to a hash of the complete proposal. Changing it invalidates approval.
- Store transactions recheck ownership, delivery window, inventory, prior remedies, and exact refund amount.
- A unique receipt per run and existing-order remedy checks prevent duplicate actions, including across different runs.
- The MCP server derives the order/customer from a random internal run capability, not model-selected customer IDs.
- Failed mutation verification escalates instead of retrying blindly. Model failures remain visible failures.
- The worker resumes interrupted jobs from checkpoints on restart. Run only one API worker per store; do not use `--workers` greater than one for Uvicorn.

## Changes from the initial plan

The first runnable implementation uses SQLite instead of PostgreSQL/pgvector, and a single in-process worker thread consuming a persisted queue instead of a separately deployed worker service. The GPT-4o evaluator uses a typed custom rubric rather than Ragas. These choices make the whole project runnable locally while retaining real LangGraph, MCP, live Gemini calls, saved evaluations, and transactional approval behavior. PostgreSQL, Ragas comparison, and production authentication remain follow-up work, not completed features.

## Repository

- `resolvedesk/`: API, worker, graph, model adapter, retrieval, MCP, and store.
- `apps/web/`: React/TypeScript interface.
- `data/policies/`: versioned policy corpus.
- `evals/cases/`: labeled synthetic cases.
- `evals/reports/`: saved runs and Codex review.
- `tests/`: authorization, policy, MCP, approval, idempotency, and recovery checks.
- `docs/`: design evidence and architecture notes.

## Official references

[LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [MCP Python SDK](https://py.sdk.modelcontextprotocol.io/), [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output), [OpenAI structured outputs](https://platform.openai.com/docs/guides/structured-outputs).
