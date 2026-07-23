from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from assessment.engine import AssessmentResult, load_assessment_result, run_assessment
from assessment.traceability import TraceabilityRecord, TraceabilityRepository
from core.config import Settings
from governance.approval_workflow import FinalizationCheckResult, FindingReviewDecision, ScoreOverrideDecision
from models.enums import DecisionCategory, HumanReviewStatus
from reporting.assessment_report_exporter import (
    to_assessment_json,
    to_assessment_markdown,
    to_findings_csv,
    to_scores_csv,
)
from storage.db.base import Base
from storage.db.models.audit_event import AuditEvent
from storage.db.models.finding import Finding
from storage.db.models.recommendation import Recommendation
from storage.db.models.scan import Scan
from storage.db.models.score import Score
from storage.db.repositories import (
    AuditRepository,
    ControlEvaluationRepository,
    GovernanceRepository,
    ScanRepository,
    ScoringRepository,
)

# Phase 5 — UI service layer (BANKING_PLATFORM_INTEGRATION_PLAN.md §5.2's
# illustrative `ui/services/api_client.py` — renamed here because this
# platform has no FastAPI-backed assessment API for the UI to call
# through; `ui/streamlit_app.py` talks to the same SQLAlchemy repositories
# every other Phase 2-4 caller uses, directly. See docs/architecture.md's
# "Structural deviations" section for the same kind of documented
# departure from the illustrative tree Phase 1 already established.
#
# DELIBERATELY NO STREAMLIT IMPORT HERE. Every function in this module is
# plain Python, fully unit-testable without a running Streamlit process —
# `ui/streamlit_app.py` is the only place `import streamlit` appears. This
# is what "UI-facing service logic" testing (this phase's own requirement)
# actually tests: this module, not the rendering code.
#
# Each function opens and closes its own session — there is no shared,
# cached session across Streamlit reruns (Streamlit reruns the whole
# script top-to-bottom on every interaction; a long-lived session would
# risk stale reads/writes across reruns). This mirrors
# scripts/seed_mock_banking_demo.py's own "construct a fresh session,
# never reuse a cached one" design for the same reason.


@dataclass
class ScanSummaryRow:
    scan_id: str
    source_path: str
    status: str
    total_findings: int
    integrity_verified: bool
    created_at: str


def _session(settings: Settings) -> Session:
    # expire_on_commit=False is deliberate: every function in this module
    # commits at least once (inside the repository it calls) and then
    # closes its session before returning ORM objects to the Streamlit
    # caller. With SQLAlchemy's default expire_on_commit=True, those
    # objects' attributes would be expired by the commit and require a
    # fresh DB round-trip on first access — which then fails with
    # DetachedInstanceError because the session is already closed by the
    # time the caller reads them. This keeps already-loaded attribute
    # values usable after close() without needing a live session.
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def run_new_assessment(settings: Settings, source_path: str, is_archive: bool = False) -> AssessmentResult:
    session = _session(settings)
    try:
        return run_assessment(source_path, settings, session, is_archive=is_archive)
    finally:
        session.close()


def list_recent_scans(settings: Settings, limit: int = 20) -> List[ScanSummaryRow]:
    session = _session(settings)
    try:
        rows = session.query(Scan).order_by(Scan.created_at.desc()).limit(limit).all()
        return [
            ScanSummaryRow(
                scan_id=r.id,
                source_path=r.source_path,
                status=r.status,
                total_findings=r.total_findings,
                integrity_verified=r.integrity_verified,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in rows
        ]
    finally:
        session.close()


def get_assessment(settings: Settings, scan_id: str) -> Optional[AssessmentResult]:
    session = _session(settings)
    try:
        return load_assessment_result(session, scan_id)
    finally:
        session.close()


def get_findings(settings: Settings, scan_id: str) -> List[Finding]:
    session = _session(settings)
    try:
        return ScanRepository(session).get_findings(scan_id)
    finally:
        session.close()


def get_scores(settings: Settings, scan_id: str) -> List[Score]:
    session = _session(settings)
    try:
        return ScoringRepository(session).get_scores(scan_id)
    finally:
        session.close()


def get_score_history(settings: Settings, scan_id: str, domain: str) -> List[Score]:
    session = _session(settings)
    try:
        return GovernanceRepository(session).get_score_history(scan_id, domain)
    finally:
        session.close()


def get_control_evaluations(settings: Settings, scan_id: str):
    session = _session(settings)
    try:
        return ControlEvaluationRepository(session).get_for_scan(scan_id)
    finally:
        session.close()


def get_recommendations(settings: Settings, scan_id: str) -> List[Recommendation]:
    session = _session(settings)
    try:
        return ScoringRepository(session).get_recommendations(scan_id)
    finally:
        session.close()


def get_audit_trail(settings: Settings, scan_id: str) -> List[AuditEvent]:
    session = _session(settings)
    try:
        return AuditRepository(session).get_for_scan(scan_id)
    finally:
        session.close()


def trace_finding(settings: Settings, finding_id: str) -> Optional[TraceabilityRecord]:
    session = _session(settings)
    try:
        return TraceabilityRepository(session).trace_finding(finding_id)
    finally:
        session.close()


def review_finding(
    settings: Settings,
    finding_id: str,
    new_status: HumanReviewStatus,
    reviewed_by: str,
    reason: Optional[str] = None,
) -> Optional[Finding]:
    session = _session(settings)
    try:
        repo = GovernanceRepository(session)
        result = repo.review_finding(
            FindingReviewDecision(
                finding_id=finding_id, new_status=new_status, reviewed_by=reviewed_by, reason=reason
            )
        )
        session.commit()
        return result
    finally:
        session.close()


def override_score(
    settings: Settings,
    original_score_id: str,
    scan_id: str,
    domain: str,
    new_decision_category: DecisionCategory,
    reviewed_by: str,
    reason: str,
    new_weighted_score: Optional[float] = None,
) -> Optional[Score]:
    session = _session(settings)
    try:
        repo = GovernanceRepository(session)
        result = repo.override_score(
            ScoreOverrideDecision(
                original_score_id=original_score_id,
                scan_id=scan_id,
                domain=domain,
                new_decision_category=new_decision_category,
                reviewed_by=reviewed_by,
                reason=reason,
                new_weighted_score=new_weighted_score,
            )
        )
        session.commit()
        return result
    finally:
        session.close()


def check_finalization(settings: Settings, scan_id: str) -> FinalizationCheckResult:
    session = _session(settings)
    try:
        return GovernanceRepository(session).check_finalization(scan_id)
    finally:
        session.close()


def export_assessment(settings: Settings, scan_id: str) -> Optional[Dict[str, str]]:
    """Every export format the UI offers, for one already-assessed scan.
    Returns None if the scan does not exist."""
    session = _session(settings)
    try:
        result = load_assessment_result(session, scan_id)
        if result is None:
            return None
        return {
            "json": to_assessment_json(result),
            "markdown": to_assessment_markdown(result),
            "findings_csv": to_findings_csv(result),
            "scores_csv": to_scores_csv(result),
        }
    finally:
        session.close()


__all__ = [
    "ScanSummaryRow",
    "run_new_assessment",
    "list_recent_scans",
    "get_assessment",
    "get_findings",
    "get_scores",
    "get_score_history",
    "get_control_evaluations",
    "get_recommendations",
    "get_audit_trail",
    "trace_finding",
    "review_finding",
    "override_score",
    "check_finalization",
    "export_assessment",
]
