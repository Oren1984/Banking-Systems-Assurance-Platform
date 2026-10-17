from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

# Additive-migration check for 0004_auth_users, on a disposable database:
#   1. migrate to the pre-auth head (a14a5514b9ab) and insert history;
#   2. upgrade to head — `users` appears, existing rows are untouched;
#   3. downgrade one step — only `users` disappears, history still intact.
# Runs on SQLite by default; set AUTH_MIGRATION_TEST_DATABASE_URL to run the
# same sequence against a disposable PostgreSQL database instead (never
# point it at a database whose data you need — step 3 drops `users`).

REPO_ROOT = Path(__file__).resolve().parents[2]
PRE_AUTH_HEAD = "a14a5514b9ab"


@pytest.fixture()
def database_url(tmp_path, monkeypatch):
    url = os.environ.get("AUTH_MIGRATION_TEST_DATABASE_URL") or f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)  # alembic/env.py reads Settings()
    return url


def _config() -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return cfg


def _history(engine):
    with engine.connect() as conn:
        scans = conn.execute(text("SELECT id, source_path, total_findings FROM scans ORDER BY id")).fetchall()
        events = conn.execute(text("SELECT id, event_type, actor FROM audit_events ORDER BY id")).fetchall()
    return scans, events


def test_auth_migration_is_additive_and_reversible(database_url):
    cfg = _config()
    command.upgrade(cfg, PRE_AUTH_HEAD)
    engine = create_engine(database_url)
    try:
        assert not inspect(engine).has_table("users")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO scans (id, source_path, source_type, status, total_files_found, files_scanned, "
                    "files_skipped, total_findings, truncated, integrity_verified, created_at) VALUES "
                    "('scan-history-1', '/scan-targets/mock_banking_system', 'directory', 'completed', 10, 10, 0, 42, "
                    "false, true, CURRENT_TIMESTAMP)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO audit_events (id, scan_id, event_type, actor, summary, payload, created_at) VALUES "
                    "('evt-history-1', 'scan-history-1', 'finding_reviewed', 'demo-reviewer@example.com', "
                    "'pre-auth review', '{}', CURRENT_TIMESTAMP)"
                )
            )
        before = _history(engine)

        command.upgrade(cfg, "head")
        insp = inspect(engine)
        assert insp.has_table("users")
        assert {c["name"] for c in insp.get_columns("users")} >= {
            "username",
            "password_hash",
            "role",
            "is_active",
            "session_version",
            "locked_until",
        }
        assert _history(engine) == before

        command.upgrade(cfg, "head")  # idempotent re-run is a no-op

        command.downgrade(cfg, PRE_AUTH_HEAD)
        assert not inspect(engine).has_table("users")
        assert _history(engine) == before
    finally:
        engine.dispose()
