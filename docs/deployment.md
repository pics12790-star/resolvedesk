# Deploy the interactive walkthrough

The public walkthrough uses the same React components and styles as the full application. It replays saved Luna investigations entirely in the browser. FastAPI, Qdrant, database hosting, and model credentials are not required.

## Vercel

1. Import `spiderkd/resolvedesk` into Vercel.
2. Keep **Root Directory** at the repository root (`./`). The committed `vercel.json` supplies the install command, build command, and output directory. Use the **Other** framework preset if Vercel asks.
3. Deploy. No environment variables or API keys are needed.

The configuration runs:

These overrides use Vercel's documented [project configuration](https://vercel.com/docs/project-configuration/vercel-json).

```text
Install: npm --prefix apps/web ci
Build:   npm --prefix apps/web run build:walkthrough
Output:  apps/web/dist-walkthrough
```

Only the built frontend and the public JSON fixtures are published. The Python backend, runtime databases, recordings, local credentials, and other repository folders are not part of this output directory. Browser state belongs to each visitor's browser; **Reset workspace** restores the starting inbox. This is a sample workspace, not a shared service or a production authentication system.

The existing Inter font is served locally with its SIL Open Font License, so the workspace does not depend on a Google Fonts request to render correctly.

## Preview locally

```powershell
cd apps/web
npm ci
npm run build:walkthrough
npm run preview:walkthrough
```

For development, use `npm run dev:walkthrough`. The browser makes no `/api` requests in this mode. The smaller sidebar label and footer identify saved-run replay; the main workspace retains the real application's layout and controls.

### Included interactions

- Start investigations and follow replayed classification, policy retrieval, order checks, and validation.
- Inspect expandable order evidence, policy citations, response drafts, and recorded run metrics.
- Approve a replacement or refund, reject a proposal, and inspect a simulated receipt.
- Run an enquiry again without creating a second remedy for the same order.
- Use **Add enquiry** to choose replacement, delivery, refund-status, refund-approval, or escalation workflows. Edit the subject/message and optionally create a sample order using the existing product picker. The selected saved workflow determines the result; edited text is not sent to a model.
- Search, sort, filter by status, and switch reviewer/customer identities. Customers see their own enquiries and cannot approve proposals or access evaluations.
- Browse both saved evaluation reports, all case results and judge scores, and the policy library.
- Refresh during an investigation or after a decision. Progress and decisions persist in browser storage when available.

Approval, purchase, and refund controls change browser sample data only. Historical model metrics describe the captured runs; replay duration is accelerated and is not a new benchmark. Evaluation metrics are loaded from saved benchmark reports rather than recomputed.

## Keep the full app separate

```powershell
cd apps/web
npm run build
cd ../..
.venv/Scripts/python.exe -m uvicorn resolvedesk.api:app --host 127.0.0.1 --port 8000
```

The normal build writes to `apps/web/dist`, continues using FastAPI and server-sent events, and does not include walkthrough fixtures or the replay adapter. The walkthrough writes to `dist-walkthrough`. Neither requires changes to the backend. The existing Dockerfile remains the full application deployment path; Render is an optional host, not a dependency of the Vercel demo.

## Maintain the saved data

```powershell
.venv/Scripts/python.exe scripts/export_walkthrough.py
```

The exporter reads the saved evaluation traces and, when present locally, the successful Luna video capture. It writes display-only allowlisted data to `demo/`: five workflow fixtures, the policy library, and two evaluation reports. Normal builds use the committed fixtures and do not need Python or the local capture.

Do not copy raw traces into the public folder. The exporter deliberately excludes run capabilities, session data, approval IDs, proposal hashes, credentials, raw model responses, and provider response IDs. Regenerate and review the JSON when the source data or public scenario set changes.
