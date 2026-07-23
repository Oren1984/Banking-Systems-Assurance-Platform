# SYNTHETIC MOCK BANKING SYSTEM — fake AML/fraud screening service, not real code.
# Deliberately planted finding — see docs/mock_banking_planted_findings.md.


def flag_suspicious_transfer(conn, account_id):
    # Intentionally unsafe: SQL built via %-style formatting — expect SQL-003.
    query = "SELECT * FROM transfers WHERE account_id = %s" % account_id
    return conn.execute(query)
