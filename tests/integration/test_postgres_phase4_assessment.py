from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from assessment.engine import run_assessment
from assessment.traceability import TraceabilityRepository
from core.config import Settings
from core.domains import BankingDomain
from governance.approval_workflow import FindingReviewDecision
from models.enums import DecisionCategory, HumanReviewStatus
from storage.db.repositories import GovernanceRepository

# Live PostgreSQL/pgvector integration test for Phase 4
# (BANKING_PLATFORM_INTEGRATION_PLAN.md §13 Phase 4 completion criterion:
# a full assessment run completes end-to-end against a real database).
# Mirrors tests/integration/test_postgres_persistence.py and
# tests/integration/test_postgres_phase3_scoring.py's pattern exactly:
# SKIPPED — not silently passed — when DATABASE_URL is not set.

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


def test_phase4_tables_exist(engine):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
        ).fetchall()
    table_names = {r[0] for r in rows}
    assert {"audit_events", "control_evaluations"} <= table_names


def test_full_assessment_against_live_postgres(tmp_path, engine):
    project = tmp_path / "project"
    (project / "app" / "payments").mkdir(parents=True)
    (project / "app" / "payments" / "processor.py").write_text('API_KEY = "hunter2value123"\n')
    settings = _settings(tmp_path)

    with Session(engine) as session:
        result = run_assessment(str(project), settings, session)

        assert len(result.scores) == 16
        assert len(result.control_evaluations) >= 1
        assert len(result.audit_events) == 4
        for e in result.evidence:
            assert "hunter2value123" not in e.content

        by_domain = {s.domain: s for s in result.scores}
        assert (
            by_domain[BankingDomain.INVESTMENTS_TRADING.value].decision_category
            == DecisionCategory.INSUFFICIENT_EVIDENCE.value
        )

        finding = result.findings[0]
        trace = TraceabilityRepository(session).trace_finding(finding.id)
        assert trace is not None
        assert "CTRL-SECRET-001" in trace.control_ids
        assert trace.domain_scores

        governance = GovernanceRepository(session)
        reviewed = governance.review_finding(
            FindingReviewDecision(
                finding_id=finding.id,
                new_status=HumanReviewStatus.APPROVED,
                reviewed_by="reviewer@example.com",
            )
        )
        assert reviewed.human_review_status == HumanReviewStatus.APPROVED.value

        audit_events = governance._audit.get_for_scan(result.scan_id)
        assert any(e.event_type == "finding_reviewed" for e in audit_events)
