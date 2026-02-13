# PAY-01 | Payment verification, failed charges, and chargebacks

Effective 2026-01-01. Version 1.

Payment policy applies when the customer asks about charges, failed payment, duplicate capture, store credit, invoice mismatch, or chargeback. Payment details are sensitive and must be handled under SEC-01.

If a customer says they were charged twice, the agent should check whether one line is an authorization hold. Authorization holds usually disappear without refund. If two captured payments exist, escalate to payment review.

If a chargeback is open, do not issue a separate refund automatically. Chargeback cases must be handled by a reviewer because the card network process can reverse funds independently.

The agent must never ask for full card number, CVV, banking password, OTP, or screenshot showing complete payment credentials. It may ask for order number, email, postal code, and safe transaction context such as payment date or last four digits when already supported by the system.

If payment failed and no order exists, the agent should not create a support ticket for replacement or refund. It can advise the customer to retry checkout or contact the bank.
