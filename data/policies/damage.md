# DAM-01 | Damaged items, replacement eligibility, and inspection evidence

Effective 2026-01-01. Version 1.

This policy covers items that arrived damaged, defective on arrival, incomplete because of physical breakage, or unusable because the delivered product is not in sellable condition. The customer may not use the exact word "damaged." Phrases such as "it came cracked," "the left side is dead out of the box," "the screen has lines," "the box was crushed and the unit will not turn on," "I need a new one," or "this arrived messed up" should be treated as possible damaged-item reports.

The standard automatic remedy is a replacement when four conditions are true: the order belongs to the requester, the item has been delivered, the issue is reported within 30 calendar days after delivery, and inventory is available for the same SKU. A report on day 30 is still eligible. A report on day 31 or later must be escalated to a human reviewer because the automatic arrival-damage window has expired.

If inventory for the same SKU is zero, the agent should offer or create a refund instead of a replacement. The customer does not need to use the word refund for this path; if the product is damaged and replacement stock is unavailable, refund is the eligible automatic action. Unlimited-stock demo products count as available stock. Low stock should be reserved only when a replacement is actually created, not when a customer merely asks a question.

The agent must not create duplicate actions. If an order already has a replacement, the correct response is to explain that a replacement already exists and provide the current status. If an order already has a refund, the agent should explain that refund status instead of creating a replacement. This applies even if the customer uses different wording such as "send another one too," "the first case was not enough," or "I want a new one and my money back." Duplicate prevention is more important than satisfying a repeated request.

If the item has not been delivered yet, do not use the damaged-item action path. A package that is late, stuck, out for delivery, not scanned, or suspected lost belongs under SHIP-01 unless the customer has actually received the product and can describe damage. If the customer says "it will probably be broken when it gets here," that is speculation, not a damage claim.

The agent may ask for a photo or serial number when a human reviewer will need evidence, but the automatic demo flow should not block a clearly eligible replacement on evidence collection unless the project has been configured to require media uploads. In an interview demo, the important behavior is to show that the system can distinguish eligibility, stock, and duplicate-action constraints.

If the customer asks for a different product, upgraded model, color change, cash refund plus replacement, or delivery to a new address, escalate. Automatic replacements are same-SKU, same-address actions. If the original SKU is discontinued but equivalent stock exists, the system should escalate rather than silently choosing an alternate item.

If the damage could be a safety issue, such as smoke, overheating, exposed battery, sharp glass, chemical leakage, or electrical sparking, the agent should escalate immediately and advise the customer to stop using the item. The agent should not troubleshoot unsafe hardware.

The assistant should be careful with vague statements. "Something is wrong with my headphones" is not enough to create a replacement. A good response asks what happened and whether the product was delivered damaged, failed after use, or is delayed in shipping. Once the customer confirms arrival damage, this policy can be applied.
