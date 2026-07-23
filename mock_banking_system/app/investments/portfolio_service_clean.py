# SYNTHETIC MOCK BANKING SYSTEM — fake investments/trading portfolio service, not real code.
# Deliberate NEGATIVE example: parameterized query.
# Expect: no findings from this file.


def find_portfolio_by_owner(conn, owner_id):
    query = "SELECT id, owner_id, value FROM portfolios WHERE owner_id = %s"
    return conn.execute(query, (owner_id,))
