from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from assessment.evaluators.control_evaluator import FindingForControlEvaluation, evaluate_all_domains
from controls.catalog import control_for_rule_id, upsert_catalog
from evidence.capture import FindingForEvidence, build_evidence
from governance.approval_workflow import (
    DomainScoreState,
    FinalizationCheckResult,
    FindingReviewDecision,
    FindingReviewState,
    ScoreOverrideDecision,
    check_finalization_policy,
)
from governance.approval_workflow import override_score as _validate_score_override
from governance.approval_workflow import review_finding as _validate_finding_review
from governance.audit_trail import AuditEventInput, build_audit_event
from models.enums import AuditEventType, ConfidenceLevel, Severity
from scanners.scan_orchestrator import ScanResult
from scoring.engine import FindingForScoring, score_all_domains
from scoring.recommendations import FindingForRecommendation, generate_recommendations
from storage.db.models.audit_event import AuditEvent
from storage.db.models.control_evaluation import ControlEvaluation
from storage.db.models.domain_mapping import DomainMappingRecord
from storage.db.models.evidence import Evidence
from storage.db.models.file_inventory import FileInventoryRecord
from storage.db.models.finding import Finding
from storage.db.models.recommendation import Recommendation
from storage.db.models.scan import Scan
from storage.db.models.scanner_execution import ScannerExecutionRecord
from storage.db.models.score import Score

# Phase 2 — Persistence repository (BANKING_PLATFORM_INTEGRATION_PLAN.md
# Phase 2 brief, §9). A thin, explicit mapping from the in-memory
# scanners.scan_orchestrator.ScanResult to the five Phase 2 tables — no
# ORM relationships/cascades are used, so this is easy to unit-test with a
# constructed ScanResult and no live database (see
# tests/unit/test_scan_repository.py, which uses SQLite in-memory for
# fast, dependency-free construction testing; live-PostgreSQL correctness
# is covered separately by tests/integration/test_postgres_persistence.py
# — see that file's own module docstring for whether it actually ran in a
# given test session).


def latest_scores_by_domain(
    session: Session, scan_id: str, domains: Optional[List[str]] = None
) -> Dict[str, Score]:
    """Phase 5 — factored out of GovernanceRepository.check_finalization()
    (Phase 4) so a third call site (the UI service layer, and
    TraceabilityRepository) can share the exact same "which Score row is
    the current one for this domain" rule rather than risking a second,
    subtly different implementation. An override
    (storage/db/repositories.py::GovernanceRepository.override_score())
    always inserts a new row rather than mutating the original, so "latest
    by calculated_at" is what makes an override actually take effect for
    any reader — scoring, finalization, traceability, or the UI. `domains`
    optionally restricts the query to a subset (e.g. one finding's own
    domains); omitted, every domain scored for this scan is considered.
    """
    query = session.query(Score).filter(Score.scan_id == scan_id)
    if domains is not None:
        query = query.filter(Score.domain.in_(domains))
    latest: Dict[str, Score] = {}
    for row in query.all():
        current = latest.get(row.domain)
        if current is None or row.calculated_at >= current.calculated_at:
            latest[row.domain] = row
    return latest


def _domain_coverage(session: Session, scan_id: str) -> tuple[Set[str], Dict[str, int]]:
    """Shared by ScoringRepository and ControlEvaluationRepository (Phase
    4) — both need the same "which domains did at least one scanned file
    actually map to" signal, computed from persisted DomainMappingRecord
    rows, never from findings alone. Kept as one module-level function so
    the two repositories can never compute this differently."""
    mappings = list(session.query(DomainMappingRecord).filter(DomainMappingRecord.scan_id == scan_id).all())
    evaluated_domains = {m.domain for m in mappings}
    files_by_domain: Dict[str, Set[str]] = {}
    for m in mappings:
        files_by_domain.setdefault(m.domain, set()).add(m.file_inventory_id)
    files_evaluated = {domain: len(files) for domain, files in files_by_domain.items()}
    return evaluated_domains, files_evaluated


class ScanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, result: ScanResult) -> Scan:
        summary = result.summary

        scan_row = Scan(
            id=summary.scan_id,
            source_path=summary.source_path,
            source_type=summary.source_type,
            status=summary.status.value,
            total_files_found=summary.total_files_found,
            files_scanned=summary.files_scanned,
            files_skipped=summary.files_skipped,
            total_findings=summary.total_findings,
            truncated=summary.truncated,
            source_hash_before=summary.source_hash_before,
            source_hash_after=summary.source_hash_after,
            integrity_verified=summary.integrity_verified,
            error_message=summary.error_message,
            started_at=summary.started_at,
            completed_at=summary.completed_at,
        )
        self._session.add(scan_row)
        # No relationship()s are declared between these tables (see class
        # docstring — deliberately kept thin/explicit), so SQLAlchemy's
        # unit-of-work has no dependency graph to order inserts by. On
        # SQLite (foreign keys unenforced by default) this went unnoticed;
        # a live PostgreSQL run surfaced a real ForeignKeyViolation without
        # this explicit flush — see PHASE_2_COMPLETION_REPORT.md.
        self._session.flush()

        # `row.id` is a Python-side (mapped_column default=...) value: it is
        # NOT populated until the row is actually flushed — reading it
        # immediately after add() silently returns None (confirmed against
        # a live PostgreSQL run, which is what surfaced this). Collect the
        # (path, row) pairs, flush once, then read every id.
        pending_file_rows: list[tuple[str, FileInventoryRecord]] = []
        for item in result.inventory:
            row = FileInventoryRecord(
                scan_id=summary.scan_id,
                relative_path=item.relative_path,
                file_name=item.file_name,
                extension=item.extension,
                detected_type=item.metadata.get("detected_type"),
                language=item.metadata.get("language"),
                size_bytes=item.size_bytes,
                content_hash=item.content_hash,
                sensitivity_hint=bool(item.metadata.get("sensitivity_hint", False)),
                scan_status="scanned",
            )
            self._session.add(row)
            pending_file_rows.append((item.relative_path, row))

        for item in result.skipped:
            self._session.add(
                FileInventoryRecord(
                    scan_id=summary.scan_id,
                    relative_path=item.relative_path,
                    file_name=item.relative_path.rsplit("/", 1)[-1],
                    extension="",
                    scan_status="skipped",
                    skipped_reason=item.reason.value,
                )
            )

        self._session.flush()
        file_id_by_path: dict[str, str] = {path: row.id for path, row in pending_file_rows}

        for relative_path, mappings in result.domain_mappings.items():
            for mapping in mappings:
                self._session.add(
                    DomainMappingRecord(
                        scan_id=summary.scan_id,
                        file_inventory_id=file_id_by_path.get(relative_path),
                        domain=mapping.domain.value,
                        confidence=mapping.confidence.value,
                        reason=mapping.reason,
                        source=mapping.source.value,
                    )
                )

        for normalized in result.findings:
            raw = normalized.raw
            self._session.add(
                Finding(
                    scan_id=normalized.scan_id,
                    scanner_id=normalized.scanner_id,
                    scanner_version=normalized.scanner_version,
                    rule_id=raw.rule_id,
                    title=raw.title,
                    finding_type=raw.finding_type.value,
                    category=raw.category.value,
                    severity=raw.severity.value,
                    confidence=raw.confidence.value,
                    banking_domains=normalized.banking_domains,
                    source_relative_path=normalized.source_relative_path,
                    line_start=raw.line_start,
                    line_end=raw.line_end,
                    masked_evidence=raw.masked_evidence,
                    description=raw.description,
                    impact=raw.impact,
                    recommended_action=raw.recommended_action,
                    remediation_mode=raw.remediation_mode.value,
                    read_only_confirmation=raw.read_only_confirmation,
                    metadata_json=raw.metadata,
                )
            )

        for execution in result.scanner_executions:
            self._session.add(
                ScannerExecutionRecord(
                    scan_id=summary.scan_id,
                    scanner_id=execution.scanner_id,
                    scanner_version=execution.scanner_version,
                    status=execution.status,
                    files_processed=execution.files_processed,
                    files_errored=execution.files_errored,
                    findings_produced=execution.findings_produced,
                    error_summary=execution.error_summary,
                )
            )

        self._session.commit()
        return scan_row

    def get_scan(self, scan_id: str) -> Scan | None:
        return self._session.get(Scan, scan_id)

    def get_findings(self, scan_id: str) -> list[Finding]:
        return list(
            self._session.query(Finding).filter(Finding.scan_id == scan_id).all()
        )


class ScoringRepository:
    """
    Phase 3 — reads already-persisted Finding/DomainMappingRecord rows for
    a scan (never the in-memory ScanResult — see scoring/engine.py's
    module docstring for why this is deliberately DB-driven, not fused
    into ScanRepository.save()), calls the pure scoring/evidence/
    recommendation functions, and persists Score/Evidence/Recommendation
    rows plus the (idempotently upserted) Control catalog.

    Kept as a separate class from ScanRepository, and callable at any
    time after a scan is persisted — not automatically invoked by
    ScanRepository.save() — per the Phase 3 brief's explicit "Separate:
    1. Deterministic scanning 2. Evidence retrieval 3. AI interpretation
    4. Recommendation generation 5. Human review... do not merge these
    into an opaque autonomous flow."
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def score_scan(self, scan_id: str) -> List[Score]:
        """Run scoring only (no evidence/recommendations) — used when only
        the domain decision categories are needed."""
        findings = self._findings_for_scan(scan_id)
        evaluated_domains, files_evaluated = _domain_coverage(self._session, scan_id)

        scoring_inputs = [
            FindingForScoring(
                rule_id=f.rule_id,
                severity=Severity(f.severity),
                confidence=ConfidenceLevel(f.confidence),
                domains=list(f.banking_domains or []),
            )
            for f in findings
        ]
        results = score_all_domains(scoring_inputs, evaluated_domains, files_evaluated)

        score_rows = [
            Score(
                scan_id=scan_id,
                domain=r.domain.value,
                raw_score=r.raw_score,
                weighted_score=r.weighted_score,
                confidence_level=r.confidence_level.value,
                evidence_completeness=r.evidence_completeness.value,
                decision_category=r.decision_category.value,
                files_evaluated=r.files_evaluated,
                findings_count=r.findings_count,
            )
            for r in results
        ]
        self._session.add_all(score_rows)
        self._session.flush()
        return score_rows

    def score_and_generate(self, scan_id: str) -> Dict[str, list]:
        """Full Phase 3 post-scan pipeline: ensure the control catalog
        exists, score every domain, capture evidence, and generate
        recommendations — all from already-persisted Finding rows."""
        control_rows = upsert_catalog(self._session)
        control_id_by_control_id = {c.control_id: c.id for c in control_rows}

        findings = self._findings_for_scan(scan_id)
        score_rows = self.score_scan(scan_id)

        def matched_control_db_id(rule_id: str) -> Optional[str]:
            definition = control_for_rule_id(rule_id)
            if definition is None:
                return None
            return control_id_by_control_id.get(definition.control_id)

        evidence_inputs = [
            FindingForEvidence(
                finding_id=f.id,
                masked_evidence=f.masked_evidence,
                source_relative_path=f.source_relative_path,
                line_start=f.line_start,
                line_end=f.line_end,
                control_id=matched_control_db_id(f.rule_id),
            )
            for f in findings
        ]
        evidence_rows = [
            Evidence(
                finding_id=e.finding_id,
                control_id=e.control_id,
                evidence_type=e.evidence_type,
                content=e.content,
                source_reference=e.source_reference,
                retrieved_via=e.retrieved_via,
            )
            for e in build_evidence(evidence_inputs)
        ]
        self._session.add_all(evidence_rows)

        recommendation_inputs = [
            FindingForRecommendation(
                finding_id=f.id,
                rule_id=f.rule_id,
                title=f.title,
                severity=Severity(f.severity),
                recommended_action=f.recommended_action,
                source_relative_path=f.source_relative_path,
                line_start=f.line_start,
                domains=list(f.banking_domains or []),
                control_id=matched_control_db_id(f.rule_id),
            )
            for f in findings
        ]
        recommendation_rows = [
            Recommendation(
                finding_id=r.finding_id,
                scan_id=scan_id,
                control_id=r.control_id,
                text=r.text,
                priority=r.priority,
                status=r.status,
                source=r.source,
            )
            for r in generate_recommendations(recommendation_inputs)
        ]
        self._session.add_all(recommendation_rows)

        self._session.flush()
        self._session.commit()
        return {
            "controls": control_rows,
            "scores": score_rows,
            "evidence": evidence_rows,
            "recommendations": recommendation_rows,
        }

    def get_scores(self, scan_id: str) -> List[Score]:
        return list(self._session.query(Score).filter(Score.scan_id == scan_id).all())

    def get_recommendations(self, scan_id: str) -> List[Recommendation]:
        return list(
            self._session.query(Recommendation).filter(Recommendation.scan_id == scan_id).all()
        )

    def get_evidence_for_finding(self, finding_id: str) -> List[Evidence]:
        return list(
            self._session.query(Evidence).filter(Evidence.finding_id == finding_id).all()
        )

    def get_evidence_for_scan(self, scan_id: str) -> List[Evidence]:
        """Phase 5 — every Evidence row for every Finding belonging to one
        scan, via a join through Finding.scan_id (Evidence itself has no
        scan_id column — see storage/db/models/evidence.py). Used to
        reassemble a full AssessmentResult for an already-persisted scan
        (assessment/engine.py::load_assessment_result()) without re-running
        anything."""
        return list(
            self._session.query(Evidence)
            .join(Finding, Evidence.finding_id == Finding.id)
            .filter(Finding.scan_id == scan_id)
            .all()
        )

    def review_recommendation(
        self, recommendation_id: str, status: str, reviewed_by: str
    ) -> Optional[Recommendation]:
        """Human review action on a single recommendation — approve
        (`accepted`), reject (`rejected`), or defer (`deferred`). This is
        the minimal human-review support the Phase 3 brief requires; the
        full governance/approval_workflow.py audit-trail module remains
        Phase 5 scope, unbuilt."""
        from datetime import datetime, timezone

        row = self._session.get(Recommendation, recommendation_id)
        if row is None:
            return None
        row.status = status
        row.reviewed_by = reviewed_by
        row.reviewed_at = datetime.now(timezone.utc)
        self._session.flush()
        self._session.commit()
        return row

    def _findings_for_scan(self, scan_id: str) -> List[Finding]:
        return list(self._session.query(Finding).filter(Finding.scan_id == scan_id).all())


class ControlEvaluationRepository:
    """
    Phase 4 — persists assessment/evaluators/control_evaluator.py's pure
    per-(domain, control) evaluation results for a scan. Reads the same
    already-persisted Finding/DomainMappingRecord rows ScoringRepository
    reads (never the in-memory ScanResult), for the same "no
    ForeignKeyViolation surprises, no drift from what was actually
    persisted" reasons documented on ScanRepository and ScoringRepository.

    Kept as a separate class, callable at any time after a scan is
    persisted — same "do not merge into an opaque autonomous flow" design
    rule ScoringRepository's own docstring states.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def evaluate_and_persist(self, scan_id: str) -> List[ControlEvaluation]:
        control_rows = upsert_catalog(self._session)
        control_db_id_by_catalog_id = {c.control_id: c.id for c in control_rows}

        findings = list(self._session.query(Finding).filter(Finding.scan_id == scan_id).all())
        evaluated_domains, _ = _domain_coverage(self._session, scan_id)

        evaluation_inputs = [
            FindingForControlEvaluation(
                finding_id=f.id, rule_id=f.rule_id, domains=list(f.banking_domains or [])
            )
            for f in findings
        ]
        results = evaluate_all_domains(evaluation_inputs, evaluated_domains)

        rows = [
            ControlEvaluation(
                scan_id=scan_id,
                control_id=control_db_id_by_catalog_id.get(r.control_id) if r.control_id else None,
                domain=r.domain.value,
                status=r.status.value,
                finding_ids=r.finding_ids,
            )
            for r in results
        ]
        self._session.add_all(rows)
        self._session.flush()
        self._session.commit()
        return rows

    def get_for_scan(self, scan_id: str) -> List[ControlEvaluation]:
        return list(
            self._session.query(ControlEvaluation).filter(ControlEvaluation.scan_id == scan_id).all()
        )


class AuditRepository:
    """
    Phase 4 — persists governance/audit_trail.py's pure event-building
    output. The only class in this codebase that writes to the
    `audit_events` table; exposes exactly one write method (`record`) plus
    read accessors — no update or delete method exists anywhere, by
    design (see storage/db/models/audit_event.py's own module docstring).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, event: AuditEventInput) -> AuditEvent:
        built = build_audit_event(event)
        row = AuditEvent(
            scan_id=built.scan_id,
            event_type=built.event_type,
            actor=built.actor,
            summary=built.summary,
            payload=built.payload,
        )
        self._session.add(row)
        self._session.flush()
        self._session.commit()
        return row

    def get_for_scan(self, scan_id: str) -> List[AuditEvent]:
        return list(
            self._session.query(AuditEvent)
            .filter(AuditEvent.scan_id == scan_id)
            .order_by(AuditEvent.created_at)
            .all()
        )

    def get_all(self) -> List[AuditEvent]:
        return list(self._session.query(AuditEvent).order_by(AuditEvent.created_at).all())


class GovernanceRepository:
    """
    Phase 4 — applies governance/approval_workflow.py's validated human
    review/override decisions and records an AuditEvent for every action.
    Never applies an unvalidated decision: every method calls the pure
    validator first and lets GovernanceError propagate rather than
    persisting a rejected transition.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditRepository(session)

    def review_finding(self, decision: FindingReviewDecision) -> Optional[Finding]:
        validated = _validate_finding_review(decision)
        row = self._session.get(Finding, validated.finding_id)
        if row is None:
            return None
        row.human_review_status = validated.new_status.value
        row.reviewed_by = validated.reviewed_by
        row.reviewed_at = datetime.now(timezone.utc)
        self._session.flush()
        self._audit.record(
            AuditEventInput(
                event_type=AuditEventType.FINDING_REVIEWED,
                actor=validated.reviewed_by,
                scan_id=row.scan_id,
                summary=f"Finding {row.id} reviewed: {validated.new_status.value}",
                payload={
                    "finding_id": row.id,
                    "new_status": validated.new_status.value,
                    "reason": validated.reason or "",
                },
            )
        )
        return row

    def override_score(self, decision: ScoreOverrideDecision) -> Optional[Score]:
        validated = _validate_score_override(decision)
        original = self._session.get(Score, validated.original_score_id)
        if original is None:
            return None
        new_row = Score(
            scan_id=validated.scan_id,
            domain=validated.domain,
            raw_score=original.raw_score,
            weighted_score=(
                validated.new_weighted_score
                if validated.new_weighted_score is not None
                else original.weighted_score
            ),
            confidence_level=original.confidence_level,
            evidence_completeness=original.evidence_completeness,
            decision_category=validated.new_decision_category.value,
            files_evaluated=original.files_evaluated,
            findings_count=original.findings_count,
            override_of=original.id,
        )
        self._session.add(new_row)
        self._session.flush()
        self._audit.record(
            AuditEventInput(
                event_type=AuditEventType.SCORE_OVERRIDDEN,
                actor=validated.reviewed_by,
                scan_id=validated.scan_id,
                summary=(
                    f"Score for domain '{validated.domain}' overridden to "
                    f"{validated.new_decision_category.value}"
                ),
                payload={
                    "original_score_id": original.id,
                    "new_score_id": new_row.id,
                    "domain": validated.domain,
                    "reason": validated.reason,
                },
            )
        )
        return new_row

    def check_finalization(self, scan_id: str) -> FinalizationCheckResult:
        """Read-only policy check — never mutates anything. See
        governance/approval_workflow.py::check_finalization_policy()'s own
        docstring for exactly what blocks finalization."""
        latest_by_domain = latest_scores_by_domain(self._session, scan_id)
        findings = list(self._session.query(Finding).filter(Finding.scan_id == scan_id).all())

        score_states = [
            DomainScoreState(domain=s.domain, decision_category=s.decision_category)
            for s in latest_by_domain.values()
        ]
        finding_states = [
            FindingReviewState(
                finding_id=f.id,
                domain_values=list(f.banking_domains or []),
                human_review_status=f.human_review_status,
            )
            for f in findings
        ]
        return check_finalization_policy(score_states, finding_states)

    def get_score_history(self, scan_id: str, domain: str) -> List[Score]:
        """Every Score row ever calculated for one (scan, domain) pair,
        oldest first — the original deterministic-engine result plus any
        subsequent overrides, each linked to its predecessor via
        `override_of`. Never mutates or deletes a row; this is purely a
        read of history, used by the UI to render an override's lineage
        without ever losing the original score (BANKING_PLATFORM_INTEGRATION_PLAN.md's
        "historical scores must never be mutated" constraint)."""
        return list(
            self._session.query(Score)
            .filter(Score.scan_id == scan_id, Score.domain == domain)
            .order_by(Score.calculated_at)
            .all()
        )
