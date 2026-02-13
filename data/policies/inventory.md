# INV-01 | Product stock, unlimited demo items, and reservation behavior

Effective 2026-01-01. Version 1.

Inventory determines whether an eligible damaged item can receive a replacement. A product with stock greater than zero is available. A product marked unlimited is available for replacement without decrementing finite stock. A product with stock zero and not unlimited is unavailable, so the damaged-item fallback is refund under DAM-01.

Stock should be checked at the moment an action is created, not only when the ticket is opened. This prevents stale UI state from creating promises the backend cannot keep. If stock changes between the customer's first message and final approval, the backend decision wins.

Demo products can include both finite-stock and unlimited-stock items. This makes the interview flow easier: some products show realistic scarcity and one or two products always allow successful replacement. Seeded demo data should be labeled clearly enough that the presenter can explain which path they are showing.

The agent should not reveal supplier quantities, warehouse allocation, cost, margin, or reorder dates. It may say that replacement stock is available or unavailable for the customer's item.

If the customer asks for a different SKU because the original is out of stock, escalate. The automatic system should not substitute products unless the business has a specific equivalence rule.
