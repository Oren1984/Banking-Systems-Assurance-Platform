from __future__ import annotations

from storage.db.session import check_database_connectivity

# Post-Phase-6 hardening recap — item 1 (Database health visibility).
# check_database_connectivity() is a UI status-indicator probe, deliberately
# independent of the shared, cached engine (get_engine/get_sessionmaker) so
# it never raises and never shares state with the rest of the application.


def test_returns_false_when_database_url_is_none():
    assert check_database_connectivity(None) is False


def test_returns_false_when_database_url_is_empty_string():
    assert check_database_connectivity("") is False


def test_returns_true_for_a_reachable_sqlite_database(tmp_path):
    db_path = tmp_path / "connectivity_check.db"
    assert check_database_connectivity(f"sqlite:///{db_path}") is True


def test_returns_false_for_an_unreachable_postgres_url():
    # Port 1 is not a routable PostgreSQL listener; a 1-second connect_timeout
    # keeps this test fast rather than hanging on a TCP-level timeout.
    unreachable_url = "postgresql://baduser:badpass@127.0.0.1:1/nonexistent_db"
    assert check_database_connectivity(unreachable_url, timeout_seconds=1) is False


def test_returns_false_for_a_malformed_database_url():
    assert check_database_connectivity("not-a-valid-url") is False
