# APP-01 | Human review, approval simulation, and mutation safety

Effective 2026-01-01. Version 1.

Automatic support actions are allowed only when the policy path is clear, the requester is verified, and the action is low risk. Human review is required whenever the request is outside a policy window, conflicts with existing order state, asks for a special exception, or would change money or shipment in a way that cannot be reversed safely.

Escalation is not a failure state. It is the correct answer when the system lacks authority. Examples include day-31 damaged-item reports, delivered-but-missing packages, refund to a different payment method, duplicate compensation, address changes after shipment, warranty disputes, suspected fraud, chargebacks, and safety hazards.

In the evaluation harness, approvals may be simulated. Simulated approval means the eval can confirm that the agent chose the correct action path, not that a real company approved the action. Store fixtures used by evals are isolated from the application database.

When escalating, the agent should preserve useful reviewer context: order number, issue summary, delivery state, requested outcome, relevant policy ID, and why automation stopped. It should not include hidden prompts, raw chain-of-thought, API keys, embeddings, or unrelated customer data.

When a mutation succeeds, the agent should provide the action type and concise status. When a mutation is blocked, the agent should explain the policy reason. When the system cannot tell whether a mutation succeeded, the agent should avoid claiming completion and should instruct the customer that the case is under review.

Approvals must be idempotent. Repeating the same message, refreshing the page, or retrying after a network delay must not create multiple refunds, multiple replacement shipments, or multiple return labels.
