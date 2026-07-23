from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from storage.db.models.control import Control
from storage.db.models.control_evaluation import ControlEvaluation
from storage.db.models.evidence import Evidence
from storage.db.models.finding import Finding
from storage.db.models.recommendation import Recommendation

# Phase 4 — Traceability query service (BANKING_PLATFORM_INTEGRATION_PLAN.md
# Phase 4 requirement: "every finding can be traced from: source file or
# artifact -> scanner rule -> banking domain -> control -> evidence ->
# score -> recommendation"). Read-only: this module issues SELECT queries
# only, never an INSERT/UPDATE/DELETE — it exists to make an already-true
# fact (the chain already threads through Finding/Evidence/Score/
# Recommendation's foreign keys and shared fields, see storage/db/models/*)
# explicit and directly queryable for one finding at a time, rather than
# requiring a caller to know which four tables to join and how.


@dataclass
class TraceabilityRecord:
    finding_id: str
    scan_id: str
    source_relative_path: str
    line_start: int
    line_end: int
    rule_id: str
    scanner_id: str
    banking_domains: List[str]
    control_ids: List[str] = field(default_factory=list)  # catalog control_id strings (e.g. "CTRL-SECRET-001")
    control_evaluation_statuses: Dict[str, str] = field(default_factory=dict)  # domain -> ControlEvaluationStatus value
    evidence_ids: List[str] = field(default_factory=list)
    domain_scores: Dict[str, dict] = field(default_factory=dict)  # domain -> {decision_category, weighted_score, confidence_level}
    recommendation_ids: List[str] = field(default_factory=list)


class TraceabilityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def trace_finding(self, finding_id: str) -> Optional[TraceabilityRecord]:
        finding = self._session.get(Finding, finding_id)
        if finding is None:
            return None

        domains = list(finding.banking_domains or [])

        evidence_rows = list(self._session.query(Evidence).filter(Evidence.finding_id == finding_id).all())
        control_db_ids = sorted({e.control_id for e in evidence_rows if e.control_id})
        control_ids: List[str] = []
        if control_db_ids:
            controls = self._session.query(Control).filter(Control.id.in_(control_db_ids)).all()
            control_ids = sorted(c.control_id for c in controls)

        recommendation_rows = list(
            self._session.query(Recommendation).filter(Recommendation.finding_id == finding_id).all()
        )

        domain_scores = self._latest_domain_scores(finding.scan_id, domains) if domains else {}
        control_evaluation_statuses = self._control_evaluation_statuses_for_finding(finding.scan_id, finding_id)

        return TraceabilityRecord(
            finding_id=finding.id,
            scan_id=finding.scan_id,
            source_relative_path=finding.source_relative_path,
            line_start=finding.line_start,
            line_end=finding.line_end,
            rule_id=finding.rule_id,
            scanner_id=finding.scanner_id,
            banking_domains=domains,
            control_ids=control_ids,
            control_evaluation_statuses=control_evaluation_statuses,
            evidence_ids=[e.id for e in evidence_rows],
            domain_scores=domain_scores,
            recommendation_ids=[r.id for r in recommendation_rows],
        )

    def _latest_domain_scores(self, scan_id: str, domains: List[str]) -> Dict[str, dict]:
        from storage.db.repositories import latest_scores_by_domain

        latest_by_domain = latest_scores_by_domain(self._session, scan_id, domains)
        return {
            domain: {
                "decision_category": row.decision_category,
                "weighted_score": row.weighted_score,
                "confidence_level": row.confidence_level,
            }
            for domain, row in latest_by_domain.items()
        }

    def _control_evaluation_statuses_for_finding(self, scan_id: str, finding_id: str) -> Dict[str, str]:
        # Only the ControlEvaluation rows this specific finding actually
        # contributed to (i.e. it appears in that row's finding_ids,
        # meaning it caused a GAP) — precise per-finding traceability
        # rather than every control evaluated for the finding's domains.
        rows = list(self._session.query(ControlEvaluation).filter(ControlEvaluation.scan_id == scan_id).all())
        return {row.domain: row.status for row in rows if finding_id in (row.finding_ids or [])}


__all__ = ["TraceabilityRecord", "TraceabilityRepository"]
