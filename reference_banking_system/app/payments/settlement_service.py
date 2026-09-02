# SYNTHETIC REFERENCE BANKING SYSTEM — fake settlement batch service, not real code.
# Deliberate positive example: parameterized query, no secrets. Expect: no findings.


def run_settlement_batch(batch_id, conn):
    query = "SELECT id, amount, status FROM settlements WHERE batch_id = %s AND status = %s"
    return conn.execute(query, (batch_id, "pending"))
