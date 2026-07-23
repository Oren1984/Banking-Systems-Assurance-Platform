# SYNTHETIC MOCK BANKING SYSTEM — fake investments/trading portfolio service, not real code.
# Deliberately planted findings — see docs/mock_banking_planted_findings.md.


def override_trade_limit(trade_id, new_limit):
    # Intentionally missing a nearby audit call on a sensitive operation — expect AUDIT-002.
    return {"trade_id": trade_id, "new_limit": new_limit}


def find_portfolio_by_owner(conn, owner_name):
    # Intentionally unsafe: f-string-interpolated SQL — expect SQL-002.
    query = f"SELECT * FROM portfolios WHERE owner_name = '{owner_name}'"
    return conn.execute(query)
