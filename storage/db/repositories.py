from __future__ import annotations

from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from controls.catalog import control_for_rule_id, upsert_catalog
from evidence.capture import FindingForEvidence, build_evidence
from models.enums import ConfidenceLevel, Severity
from scanners.scan_orchestrator import ScanResult
from scoring.engine import FindingForScoring, score_all_domains
from scoring.recommendations import FindingForRecommendation, generate_recommendations
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
        evaluated_domains, files_evaluated = self._domain_coverage(scan_id)

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

    def _domain_coverage(self, scan_id: str) -> tuple[Set[str], Dict[str, int]]:
        mappings = list(
            self._session.query(DomainMappingRecord)
            .filter(DomainMappingRecord.scan_id == scan_id)
            .all()
        )
        evaluated_domains = {m.domain for m in mappings}
        files_by_domain: Dict[str, Set[str]] = {}
        for m in mappings:
            files_by_domain.setdefault(m.domain, set()).add(m.file_inventory_id)
        files_evaluated = {domain: len(files) for domain, files in files_by_domain.items()}
        return evaluated_domains, files_evaluated
