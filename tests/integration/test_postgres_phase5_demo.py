from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
import ui.services.assessment_service as svc
from core.config import Settings
from models.enums import DecisionCategory, HumanReviewStatus
from scripts.seed_mock_banking_demo import seed

# Live PostgreSQL/pgvector integration test for Phase 5
# (BANKING_PLATFORM_INTEGRATION_PLAN.md §13 Phase 5 completion gate: "Live
# PostgreSQL tests pass"). Mirrors tests/integration/test_postgres_phase3_
# scoring.py and test_postgres_phase4_assessment.py's pattern exactly:
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
        report_output_dir=str(tmp_path / "reports"),
        database_url=DATABASE_URL,
        allowed_scan_paths=[str(Path(__file__).resolve().parents[2])],
    )


def test_seed_mock_banking_demo_against_live_postgres(tmp_path, engine):
    settings = _settings(tmp_path)
    with Session(engine) as session:
        result = seed(settings=settings, session=session)

    assert result["findings_count"] == 42
    assert result["scores_count"] == 16
    assert result["control_evaluations_count"] == 68

    export_dir = Path(settings.report_output_dir) / "mock_banking_demo"
    assert (export_dir / "latest_assessment.json").exists()
    assert (export_dir / "latest_assessment.md").exists()


def test_ui_service_layer_full_governance_workflow_against_live_postgres(tmp_path):
    settings = _settings(tmp_path)
    result = svc.run_new_assessment(settings, settings.mock_banking_system_path)
    assert len(result.scores) == 16

    scores = svc.get_scores(settings, result.scan_id)
    critical = next(s for s in scores if s.decision_category == DecisionCategory.CRITICAL_RISK.value)

    check_before = svc.check_finalization(settings, result.scan_id)
    assert check_before.can_finalize is False

    new_score = svc.override_score(
        settings,
        critical.id,
        result.scan_id,
        critical.domain,
        DecisionCategory.ACCEPTABLE,
        "reviewer@example.com",
        "Compensating control verified out-of-band for this integration test.",
    )
    assert new_score.override_of == critical.id

    history = svc.get_score_history(settings, result.scan_id, critical.domain)
    assert len(history) == 2

    domain_findings = [f for f in result.findings if critical.domain in (f.banking_domains or [])]
    for f in domain_findings:
        reviewed = svc.review_finding(settings, f.id, HumanReviewStatus.APPROVED, "reviewer@example.com")
        assert reviewed.human_review_status == HumanReviewStatus.APPROVED.value

    audit_events = svc.get_audit_trail(settings, result.scan_id)
    assert any(e.event_type == "score_overridden" for e in audit_events)
    assert any(e.event_type == "finding_reviewed" for e in audit_events)

    exports = svc.export_assessment(settings, result.scan_id)
    assert exports is not None
    for content in exports.values():
        assert "fake_demo_secret_pw_9f2c" not in content
