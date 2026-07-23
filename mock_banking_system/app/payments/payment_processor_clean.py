# SYNTHETIC MOCK BANKING SYSTEM — fake payment processor, not real code.
# Deliberate NEGATIVE example: no secrets, masked logging, parameterized query.
# Expect: no findings from this file.
import logging

logger = logging.getLogger("mock_payments")


def process_card_payment(card_number_last4, amount, conn):
    logger.info("processing payment amount=%s", amount)
    query = "INSERT INTO payments (last4, amount) VALUES (%s, %s)"
    conn.execute(query, (card_number_last4, amount))
    return {"status": "approved"}
