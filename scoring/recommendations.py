from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from models.enums import RecommendationSource, RecommendationStatus, Severity

# Phase 3 — Recommendation generation (BANKING_PLATFORM_INTEGRATION_PLAN.md
# §11: "Recommendation ... promoted to its own entity to support
# prioritization/status independent of the finding"). Deterministic and
# template-based only — Phase 3 has no AI/LLM component, so
# `source` is always RecommendationSource.DETERMINISTIC_TEMPLATE (see
# models/enums.py's docstring for why that field exists at all). Pure
# function, no database — mirrors scoring/engine.py's design.
#
# Deterministic and reproducible: the same finding always produces the
# same recommendation text, byte-for-byte — required by the Phase 3
# brief's "Be reproducible where deterministic templates are used".


@dataclass
class FindingForRecommendation:
    finding_id: str  # the *persisted* Finding row's real id (see storage/db/repositories.py)
    rule_id: str
    title: str
    severity: Severity
    recommended_action: str
    source_relative_path: str
    line_start: int
    domains: List[str] = field(default_factory=list)
    control_id: Optional[str] = None  # matched Control's DB id, if any (controls/catalog.py)


@dataclass
class RecommendationResult:
    finding_id: str
    control_id: Optional[str]
    text: str
    priority: str  # models.enums.Severity value
    status: str = RecommendationStatus.OPEN.value
    source: str = RecommendationSource.DETERMINISTIC_TEMPLATE.value


def generate_recommendations(
    findings: List[FindingForRecommendation],
) -> List[RecommendationResult]:
    return [_recommendation_for(f) for f in findings]


def _recommendation_for(finding: FindingForRecommendation) -> RecommendationResult:
    domain_note = f" (banking domains: {', '.join(finding.domains)})" if finding.domains else ""
    text = (
        f"[{finding.rule_id}] {finding.title} — {finding.source_relative_path}:"
        f"{finding.line_start}{domain_note}. {finding.recommended_action}"
    )
    return RecommendationResult(
        finding_id=finding.finding_id,
        control_id=finding.control_id,
        text=text,
        priority=finding.severity.value,
        status=RecommendationStatus.OPEN.value,
        source=RecommendationSource.DETERMINISTIC_TEMPLATE.value,
    )
