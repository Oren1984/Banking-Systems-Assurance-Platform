# SYNTHETIC MOCK BANKING SYSTEM — fake payment processor, not real code.
# Deliberately planted findings for Phase 5 demonstration — see
# docs/mock_banking_planted_findings.md for the full inventory.
import logging

logger = logging.getLogger("mock_payments")

payment_gateway_api_key = "sk-fake-demo-gateway-key-abcXYZ123demo"  # expect SECRET-001


def process_card_payment(card_number, cvv, amount):
    # Intentionally unsafe: sensitive fields passed directly to a logging call — expect LOG-001 (CRITICAL).
    logger.info(f"processing payment card_number={card_number} cvv={cvv} amount={amount}")
    return {"status": "approved"}
