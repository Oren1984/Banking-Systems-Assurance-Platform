# SYNTHETIC MOCK BANKING SYSTEM — fake core-banking account service, not real code.
# Deliberately planted findings for Phase 5 demonstration — see
# docs/mock_banking_planted_findings.md for the full inventory.

DB_PASSWORD = "fake_demo_secret_pw_9f2c"  # pragma: allowlist secret (synthetic) — expect SECRET-001


def get_account_by_holder_name(conn, holder_name):
    # Intentionally unsafe: string-concatenated SQL — expect SQL-001.
    query = "SELECT * FROM accounts WHERE holder_name = '" + holder_name + "'"
    return conn.execute(query)


def withdraw(account, amount):
    # Intentionally missing a nearby audit call on a sensitive operation — expect AUDIT-002.
    account.balance -= amount
    return account.balance
