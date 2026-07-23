# SYNTHETIC MOCK BANKING SYSTEM — fake core-banking account lookup, not real code.
# Deliberate NEGATIVE example: parameterized query, no secrets, audit call present.
# Expect: no findings from this file.


def get_account_by_id(conn, account_id):
    query = "SELECT id, holder_name, status FROM accounts WHERE id = %s"
    return conn.execute(query, (account_id,))


def close_account(account, actor):
    audit_log("account_closed", user=actor, action="close_account", account_id=account.id)
    account.status = "closed"
    return account


def audit_log(event, user, action, account_id):
    return {"event": event, "user": user, "action": action, "account_id": account_id}
