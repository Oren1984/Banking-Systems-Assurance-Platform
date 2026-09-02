# SYNTHETIC REFERENCE BANKING SYSTEM — fake payment processor, not real code.
# Deliberate positive example: parameterized queries, masked logging, review-trail call
# present on a sensitive operation. Expect: no findings from this file.
import logging

logger = logging.getLogger("reference_payments")


def process_card_payment(card_token, amount, conn):
    logger.info("processing payment amount=%s", amount)
    query = "INSERT INTO payments (token, amount) VALUES (%s, %s)"
    conn.execute(query, (card_token, amount))
    return {"status": "approved"}


def reverse_transfer(payment_id, actor, conn):
    audit_log("payment_reversed", user=actor, action="reverse_transfer", payment_id=payment_id)
    query = "UPDATE payments SET status = %s WHERE id = %s"
    conn.execute(query, ("reversed", payment_id))
    return {"status": "reversed"}


def audit_log(event, user, action, payment_id):
    return {"event": event, "user": user, "action": action, "payment_id": payment_id}
