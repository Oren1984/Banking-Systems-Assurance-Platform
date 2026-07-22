# SYNTHETIC TEST FIXTURE — fake banking account service, not real code.

DB_PASSWORD = "fake_super_secret_pw_1"  # pragma: allowlist secret (synthetic)

CUSTOMER_SUPPORT_EMAIL = "support@example-fake-bank.test"


def get_account_by_name(conn, account_holder_name):
    # Intentionally unsafe: string-concatenated SQL for scanner detection.
    query = "SELECT * FROM accounts WHERE holder_name = '" + account_holder_name + "'"
    return conn.execute(query)


def transfer_funds(from_account, to_account, amount):
    # Intentionally missing an audit call — sensitive operation, no audit_log/log_audit call.
    from_account.balance -= amount
    to_account.balance += amount
    return True


def withdraw(account, amount):
    account.balance -= amount
    return account.balance
