# SYNTHETIC MOCK BANKING SYSTEM — fake transaction/ledger reconciliation job, not real code.
# Deliberately planted finding — see docs/mock_banking_planted_findings.md.


def find_unreconciled_entries(conn, batch_id):
    # Intentionally unsafe: string-concatenated SQL — expect SQL-001.
    query = "SELECT * FROM ledger_entries WHERE batch_id = '" + batch_id + "'"
    return conn.execute(query)
