from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from core.config import Settings
from core.exceptions import AssessmentError
from governance.audit_trail import AuditEventInput
from models.enums import AuditEventType
from scanners.scan_orchestrator import ScanResult, run_scan
from scanners.source_ingestion import SourceHandle, ingest_local_directory, ingest_zip_archive
from storage.db.models.audit_event import AuditEvent
from storage.db.models.control_evaluation import ControlEvaluation
from storage.db.models.evidence import Evidence
from storage.db.models.finding import Finding
from storage.db.models.recommendation import Recommendation
from storage.db.models.scan import Scan
from storage.db.models.score import Score
from storage.db.repositories import AuditRepository, ControlEvaluationRepository, ScanRepository, ScoringRepository

# Phase 4 — Assessment orchestration engine
# (BANKING_PLATFORM_INTEGRATION_PLAN.md §13 Phase 4: "assessment/engine.py",
# adapted from ai-project-control-tower/app/audit/audit_engine.py, generalized
# from hardcoded "agent classes" — see BANKING_PLATFORM_INTEGRATION_PLAN.md
# §3). This module adds no new business logic of its own: it is a thin,
# read-only orchestration of Phase 2/3/4 repositories that already exist
# and are already independently tested — `ScanRepository`, `ScoringRepository`,
# `ControlEvaluationRepository`, `AuditRepository`. Deterministic logic
# (scanning, scoring, control evaluation) remains the sole authority;
# nothing here calls an LLM/RAG component or makes a decision an evaluator
# didn't already make.
#
# READ-ONLY GUARANTEE: this function's only filesystem interaction is via
# `scanners/source_ingestion.py` (already covered by
# tests/security/test_scan_no_source_modification.py's hash-comparison
# proof) — it never opens a target file in write mode, and it introduces
# no new filesystem or network access of its own. See
# tests/security/test_assessment_no_source_modification.py for the
# Phase 4 extension of that same proof to this orchestration layer.


@dataclass
class AssessmentResult:
    scan_id: str
    scan_row: Scan
    scores: List[Score]
    control_evaluations: List[ControlEvaluation]
    evidence: List[Evidence]
    recommendations: List[Recommendation]
    findings: List[Finding]
    audit_events: List[AuditEvent]
    # Only populated by run_assessment() (a scan freshly executed in this
    # call) — None when reassembled from persisted rows by
    # load_assessment_result(), since the original in-memory ScanResult
    # (inventory, skipped-file list, per-scanner execution detail) is not
    # reconstructible from the database alone. Nothing in this module or
    # in reporting/assessment_report_exporter.py reads this field — it
    # exists for a caller (e.g. a UI page) that specifically wants the
    # richer Phase 2 scan detail right after a fresh run.
    scan_result: Optional[ScanResult] = None


def run_assessment(
    source_path: str,
    settings: Settings,
    session: Session,
    is_archive: bool = False,
) -> AssessmentResult:
    """
    Full read-only assessment pipeline for one target: ingest -> scan ->
    persist -> score + capture evidence + generate recommendations ->
    evaluate controls per domain -> record an audit trail entry for each
    stage. Never invoked implicitly by any other module — an operator or
    API caller explicitly starts an assessment, matching the Phase 3
    brief's "do not merge into an opaque autonomous flow" rule that
    ScoringRepository's own docstring already establishes.

    Raises AssessmentError if the underlying scan could not run at all
    (see scanners/scan_orchestrator.py::run_scan()'s own contract — it
    does not raise for per-file/per-scanner failures, only for a failure
    that prevents scanning entirely).
    """
    try:
        handle: SourceHandle = (
            ingest_zip_archive(source_path, settings)
            if is_archive
            else ingest_local_directory(source_path, settings)
        )
    except Exception as exc:
        raise AssessmentError(f"assessment could not run: source ingestion failed: {exc}") from exc

    try:
        scan_result = run_scan(handle, settings)
    except Exception as exc:
        raise AssessmentError(f"assessment could not run: scan failed: {exc}") from exc
    finally:
        handle.cleanup()

    scan_repo = ScanRepository(session)
    scan_row = scan_repo.save(scan_result)

    audit_repo = AuditRepository(session)
    audit_events: List[AuditEvent] = [
        audit_repo.record(
            AuditEventInput(
                event_type=AuditEventType.SCAN_PERSISTED,
                actor="system",
                scan_id=scan_row.id,
                summary=f"Scan persisted: {scan_result.summary.total_findings} finding(s) across {scan_result.summary.files_scanned} file(s)",
                payload={
                    "status": scan_result.summary.status.value,
                    "integrity_verified": scan_result.summary.integrity_verified,
                },
            )
        )
    ]

    scoring_repo = ScoringRepository(session)
    scoring_output = scoring_repo.score_and_generate(scan_row.id)
    audit_events.append(
        audit_repo.record(
            AuditEventInput(
                event_type=AuditEventType.SCORING_COMPLETED,
                actor="system",
                scan_id=scan_row.id,
                summary=(
                    f"Scoring completed: {len(scoring_output['scores'])} domain score(s), "
                    f"{len(scoring_output['evidence'])} evidence row(s), "
                    f"{len(scoring_output['recommendations'])} recommendation(s)"
                ),
                payload={"domain_count": len(scoring_output["scores"])},
            )
        )
    )

    control_eval_repo = ControlEvaluationRepository(session)
    control_evaluations = control_eval_repo.evaluate_and_persist(scan_row.id)
    audit_events.append(
        audit_repo.record(
            AuditEventInput(
                event_type=AuditEventType.CONTROL_EVALUATION_COMPLETED,
                actor="system",
                scan_id=scan_row.id,
                summary=f"Control evaluation completed: {len(control_evaluations)} (domain, control) result(s)",
                payload={"evaluation_count": len(control_evaluations)},
            )
        )
    )

    findings = scan_repo.get_findings(scan_row.id)

    audit_events.append(
        audit_repo.record(
            AuditEventInput(
                event_type=AuditEventType.ASSESSMENT_COMPLETED,
                actor="system",
                scan_id=scan_row.id,
                summary=f"Assessment completed for scan {scan_row.id}",
                payload={
                    "findings_count": len(findings),
                    "scores_count": len(scoring_output["scores"]),
                    "control_evaluations_count": len(control_evaluations),
                    "recommendations_count": len(scoring_output["recommendations"]),
                },
            )
        )
    )

    return AssessmentResult(
        scan_id=scan_row.id,
        scan_result=scan_result,
        scan_row=scan_row,
        scores=scoring_output["scores"],
        control_evaluations=control_evaluations,
        evidence=scoring_output["evidence"],
        recommendations=scoring_output["recommendations"],
        findings=findings,
        audit_events=audit_events,
    )


def load_assessment_result(session: Session, scan_id: str) -> Optional[AssessmentResult]:
    """
    Phase 5 — reassemble an AssessmentResult purely from already-persisted
    rows, for a scan `run_assessment()` produced in an earlier call (or an
    earlier process — a Streamlit UI page rerun, for instance). Issues
    only SELECT queries; never re-scans, re-scores, or re-evaluates
    anything, and never mutates the scan it reads. Returns None if no
    `Scan` row with this id exists.
    """
    scan_repo = ScanRepository(session)
    scan_row = scan_repo.get_scan(scan_id)
    if scan_row is None:
        return None

    scoring_repo = ScoringRepository(session)
    control_eval_repo = ControlEvaluationRepository(session)
    audit_repo = AuditRepository(session)

    return AssessmentResult(
        scan_id=scan_id,
        scan_row=scan_row,
        scores=scoring_repo.get_scores(scan_id),
        control_evaluations=control_eval_repo.get_for_scan(scan_id),
        evidence=scoring_repo.get_evidence_for_scan(scan_id),
        recommendations=scoring_repo.get_recommendations(scan_id),
        findings=scan_repo.get_findings(scan_id),
        audit_events=audit_repo.get_for_scan(scan_id),
    )


__all__ = ["AssessmentResult", "run_assessment", "load_assessment_result"]
