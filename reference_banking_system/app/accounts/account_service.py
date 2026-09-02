# SYNTHETIC REFERENCE BANKING SYSTEM — fake core-banking account service, not real code.
# Deliberate positive example: parameterized query, review-trail call present on a sensitive
# operation. Expect: no findings from this file.


def get_account_balance(conn, account_id):
    query = "SELECT id, holder_name, balance FROM accounts WHERE id = %s"
    return conn.execute(query, (account_id,))


def withdraw(account, amount, actor, conn):
    audit_log("funds_withdrawn", user=actor, action="withdraw", account_id=account.id)
    query = "UPDATE accounts SET balance = balance - %s WHERE id = %s"
    conn.execute(query, (amount, account.id))
    return {"status": "completed"}


def audit_log(event, user, action, account_id):
    return {"event": event, "user": user, "action": action, "account_id": account_id}
