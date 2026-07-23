from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from core.config import Settings
from core.domains import BankingDomain
from models.enums import DecisionCategory
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory
from storage.db.repositories import ScanRepository, ScoringRepository

# Live PostgreSQL/pgvector integration test for Phase 3
# (BANKING_PLATFORM_INTEGRATION_PLAN.md §13 Phase 3 completion criterion:
# "Alembic migration applies cleanly to a fresh local database"). Mirrors
# tests/integration/test_postgres_persistence.py's pattern for Phase 2:
# SKIPPED — not silently passed — when DATABASE_URL is not set.
#
# This proves what the in-memory-SQLite tests in
# tests/unit/test_scoring_repository.py cannot: that
# alembic/versions/0002_phase3_controls_evidence_scoring.py's tables and
# foreign keys (controls -> evidence/recommendations, scores -> scans,
# scores.override_of -> scores) actually apply and are enforced by a real
# database, not just accepted silently the way SQLite accepts unenforced
# FKs by default.

DATABASE_URL = os.environ.get("DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set — no live PostgreSQL/pgvector server available in this run",
)


@pytest.fixture()
def engine():
    eng = create_engine(DATABASE_URL, pool_pre_ping=True)
    yield eng
    eng.dispose()


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=[str(tmp_path)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
        database_url=DATABASE_URL,
    )


def test_phase3_tables_exist(engine):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
        ).fetchall()
    table_names = {r[0] for r in rows}
    assert {"controls", "scores", "evidence", "recommendations"} <= table_names


def test_findings_table_has_phase3_human_review_columns(engine):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'findings'"
            )
        ).fetchall()
    column_names = {r[0] for r in rows}
    assert {"human_review_status", "reviewed_by", "reviewed_at"} <= column_names


def test_score_and_generate_persists_against_live_postgres(tmp_path, engine):
    project = tmp_path / "project"
    (project / "app" / "payments").mkdir(parents=True)
    (project / "app" / "payments" / "processor.py").write_text(
        'API_KEY = "hunter2value123"\n'
    )
    settings = _settings(tmp_path)

    handle = ingest_local_directory(str(project), settings)
    try:
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    with Session(engine) as session:
        ScanRepository(session).save(result)

    with Session(engine) as session:
        scoring_repo = ScoringRepository(session)
        output = scoring_repo.score_and_generate(result.summary.scan_id)
        assert len(output["scores"]) == 16
        assert len(output["evidence"]) >= 1
        assert len(output["recommendations"]) >= 1
        for evidence_row in output["evidence"]:
            assert "hunter2value123" not in evidence_row.content

    with Session(engine) as verify_session:
        scoring_repo = ScoringRepository(verify_session)
        scores = scoring_repo.get_scores(result.summary.scan_id)
        by_domain = {s.domain: s for s in scores}
        assert (
            by_domain[BankingDomain.INVESTMENTS_TRADING.value].decision_category
            == DecisionCategory.INSUFFICIENT_EVIDENCE.value
        )
