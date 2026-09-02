# SYNTHETIC REFERENCE BANKING SYSTEM — fake account statement generator, not real code.
# Deliberate positive example: parameterized query, no PII exposure. Expect: no findings.


def generate_statement(conn, account_id, period_start, period_end):
    query = (
        "SELECT posted_at, description, amount FROM transactions "
        "WHERE account_id = %s AND posted_at BETWEEN %s AND %s"
    )
    return conn.execute(query, (account_id, period_start, period_end))
