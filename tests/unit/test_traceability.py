from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from assessment.engine import run_assessment
from assessment.traceability import TraceabilityRepository
from core.config import Settings
from storage.db.base import Base

# Phase 4 — assessment/traceability.py. In-memory SQLite test, same
# pattern as tests/unit/test_scoring_repository.py — proves the full
# source file -> scanner rule -> banking domain -> control -> evidence ->
# score -> recommendation chain is actually queryable end to end for one
# finding, not just true "in theory" across four separate tables.


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=[str(tmp_path)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
    )


def _run_assessment(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    project = tmp_path / "project"
    (project / "app" / "payments").mkdir(parents=True)
    (project / "app" / "payments" / "processor.py").write_text('API_KEY = "hunter2value123"\n')
    session = Session(engine)
    result = run_assessment(str(project), _settings(tmp_path), session)
    return session, result


def test_trace_finding_returns_none_for_unknown_id(tmp_path):
    session, _ = _run_assessment(tmp_path)
    assert TraceabilityRepository(session).trace_finding("does-not-exist") is None


def test_trace_finding_returns_the_full_chain(tmp_path):
    session, result = _run_assessment(tmp_path)
    finding = result.findings[0]

    record = TraceabilityRepository(session).trace_finding(finding.id)

    assert record is not None
    assert record.finding_id == finding.id
    assert record.rule_id == "SECRET-001"
    assert "payments" in record.banking_domains
    assert "CTRL-SECRET-001" in record.control_ids
    assert len(record.evidence_ids) >= 1
    assert len(record.recommendation_ids) >= 1
    assert "payments" in record.domain_scores
    assert record.domain_scores["payments"]["decision_category"]
    assert record.control_evaluation_statuses.get("payments") == "gap"


def test_trace_finding_source_location_matches_the_persisted_finding(tmp_path):
    session, result = _run_assessment(tmp_path)
    finding = result.findings[0]
    record = TraceabilityRepository(session).trace_finding(finding.id)
    assert record.source_relative_path == finding.source_relative_path
    assert record.line_start == finding.line_start


def test_trace_finding_domain_scores_only_include_the_findings_own_domains(tmp_path):
    session, result = _run_assessment(tmp_path)
    finding = result.findings[0]
    record = TraceabilityRepository(session).trace_finding(finding.id)
    assert set(record.domain_scores.keys()) <= set(record.banking_domains)
