from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from assessment.engine import run_assessment
from core.config import Settings
from core.exceptions import AssessmentError
from models.enums import AuditEventType, HumanReviewStatus
from storage.db.base import Base

# Phase 4 — assessment/engine.py::run_assessment(). In-memory SQLite
# construction/shape test, mirroring tests/unit/test_scan_repository.py and
# tests/unit/test_scoring_repository.py's own approach — proves the full
# ingest -> scan -> persist -> score -> control-evaluate -> audit-trail
# orchestration is correctly wired without needing a live PostgreSQL
# server. Live-PostgreSQL coverage is
# tests/integration/test_postgres_phase4_assessment.py.


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=[str(tmp_path)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
    )


def _project_with_a_secret(tmp_path):
    project = tmp_path / "project"
    (project / "app" / "payments").mkdir(parents=True)
    (project / "app" / "payments" / "processor.py").write_text('API_KEY = "hunter2value123"\n')
    return project


def test_run_assessment_produces_all_expected_artifacts(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    project = _project_with_a_secret(tmp_path)
    with Session(engine) as session:
        result = run_assessment(str(project), _settings(tmp_path), session)

        assert len(result.scores) == 16
        assert len(result.control_evaluations) >= 1
        assert len(result.evidence) >= 1
        assert len(result.recommendations) >= 1
        assert len(result.findings) >= 1
        assert len(result.audit_events) == 4


def test_run_assessment_never_leaks_the_raw_secret_anywhere(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    project = _project_with_a_secret(tmp_path)
    with Session(engine) as session:
        result = run_assessment(str(project), _settings(tmp_path), session)

        for e in result.evidence:
            assert "hunter2value123" not in e.content
        for r in result.recommendations:
            assert "hunter2value123" not in r.text
        for a in result.audit_events:
            assert "hunter2value123" not in a.summary
            assert "hunter2value123" not in str(a.payload)


def test_run_assessment_audit_trail_records_all_four_stages_in_order(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    project = _project_with_a_secret(tmp_path)
    with Session(engine) as session:
        result = run_assessment(str(project), _settings(tmp_path), session)
        event_types = [e.event_type for e in result.audit_events]
        assert event_types == [
            AuditEventType.SCAN_PERSISTED.value,
            AuditEventType.SCORING_COMPLETED.value,
            AuditEventType.CONTROL_EVALUATION_COMPLETED.value,
            AuditEventType.ASSESSMENT_COMPLETED.value,
        ]


def test_run_assessment_findings_default_to_pending_review(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    project = _project_with_a_secret(tmp_path)
    with Session(engine) as session:
        result = run_assessment(str(project), _settings(tmp_path), session)
        for f in result.findings:
            assert f.human_review_status == HumanReviewStatus.PENDING.value


def test_run_assessment_flags_untouched_domains_as_insufficient_evidence(tmp_path):
    from core.domains import BankingDomain
    from models.enums import DecisionCategory

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    project = _project_with_a_secret(tmp_path)
    with Session(engine) as session:
        result = run_assessment(str(project), _settings(tmp_path), session)
        by_domain = {s.domain: s for s in result.scores}
        untouched = by_domain[BankingDomain.INVESTMENTS_TRADING.value]
        assert untouched.decision_category == DecisionCategory.INSUFFICIENT_EVIDENCE.value


def test_run_assessment_raises_assessment_error_for_a_nonexistent_path(tmp_path):
    settings = _settings(tmp_path)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        with pytest.raises(AssessmentError):
            run_assessment(str(tmp_path / "does-not-exist"), settings, session)
