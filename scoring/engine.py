from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

from core.domains import BankingDomain
from models.enums import ConfidenceLevel, DecisionCategory, EvidenceCompleteness, Severity

# Phase 3 — Scoring Engine (BANKING_PLATFORM_INTEGRATION_PLAN.md §13's
# Phase 3 entry). Deliberately pure: no database, no I/O — accepts plain
# dataclasses and returns plain dataclasses, so it is fully unit-testable
# without a session. storage/db/repositories.py::ScoringRepository is the
# only place that reads persisted rows and calls into this module.
#
# THE CORE FIX THIS MODULE DELIVERS (BANKING_PLATFORM_INTEGRATION_PLAN.md
# Executive Summary / §9): a domain with zero findings because it was
# never evaluated must resolve to DecisionCategory.INSUFFICIENT_EVIDENCE,
# never to a false "clean" score. The distinguishing signal is
# `evaluated_domains` — the set of domains at least one scanned file was
# actually mapped to (scanners/domain_mapper.py output) — not simply
# "zero findings for this domain".
#
# Mechanism: a weighted-deduction score (pattern from
# AI-Project-Scope-Guard/src/scope_guard/evaluator.py — the weighting/
# threshold/explainability *mechanism* only, never its build/don't-build
# decision semantics, see BANKING_PLATFORM_INTEGRATION_PLAN.md §3) merged
# with per-dimension aggregation adapted from
# ai-project-control-tower/app/audit/scoring.py, plus new confidence/
# evidence-completeness handling neither original engine had.

_SEVERITY_DEDUCTION: Dict[Severity, float] = {
    Severity.CRITICAL: 40.0,
    Severity.HIGH: 25.0,
    Severity.MEDIUM: 12.0,
    Severity.LOW: 5.0,
    Severity.INFO: 1.0,
}

_CONFIDENCE_MULTIPLIER: Dict[ConfidenceLevel, float] = {
    ConfidenceLevel.HIGH: 1.0,
    ConfidenceLevel.MEDIUM: 0.7,
    ConfidenceLevel.LOW: 0.4,
}

_HIGH_RISK_THRESHOLD = 35.0
_REMEDIATION_REQUIRED_THRESHOLD = 55.0
_ACCEPTABLE_WITH_OBSERVATIONS_THRESHOLD = 75.0


@dataclass
class FindingForScoring:
    """The minimal shape scoring needs from a persisted Finding row —
    deliberately not the ORM row itself, so this module never imports
    storage.db.*."""

    rule_id: str
    severity: Severity
    confidence: ConfidenceLevel
    domains: List[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    domain: BankingDomain
    raw_score: float | None
    weighted_score: float | None
    confidence_level: ConfidenceLevel
    evidence_completeness: EvidenceCompleteness
    decision_category: DecisionCategory
    files_evaluated: int
    findings_count: int


def score_all_domains(
    findings: List[FindingForScoring],
    evaluated_domains: Set[str],
    files_evaluated_by_domain: Dict[str, int],
) -> List[ScoreResult]:
    """Score every one of the 16 approved domains — never a subset, so a
    domain that was neither evaluated nor has findings still gets an
    explicit INSUFFICIENT_EVIDENCE row rather than silently having no
    score at all (which would be just as misleading as a false "clean")."""
    return [
        score_domain(
            domain,
            [f for f in findings if domain.value in f.domains],
            evaluated=domain.value in evaluated_domains,
            files_evaluated=files_evaluated_by_domain.get(domain.value, 0),
        )
        for domain in BankingDomain
    ]


def score_domain(
    domain: BankingDomain,
    findings: List[FindingForScoring],
    evaluated: bool,
    files_evaluated: int,
) -> ScoreResult:
    if not evaluated:
        return ScoreResult(
            domain=domain,
            raw_score=None,
            weighted_score=None,
            confidence_level=ConfidenceLevel.LOW,
            evidence_completeness=EvidenceCompleteness.INSUFFICIENT,
            decision_category=DecisionCategory.INSUFFICIENT_EVIDENCE,
            files_evaluated=0,
            findings_count=0,
        )

    evidence_completeness = (
        EvidenceCompleteness.COMPLETE if files_evaluated >= 2 else EvidenceCompleteness.PARTIAL
    )

    if not findings:
        return ScoreResult(
            domain=domain,
            raw_score=100.0,
            weighted_score=100.0,
            confidence_level=_coverage_confidence(files_evaluated),
            evidence_completeness=evidence_completeness,
            decision_category=DecisionCategory.ACCEPTABLE,
            files_evaluated=files_evaluated,
            findings_count=0,
        )

    raw_score = max(0.0, 100.0 - sum(_SEVERITY_DEDUCTION[f.severity] for f in findings))
    weighted_score = max(
        0.0,
        100.0
        - sum(_SEVERITY_DEDUCTION[f.severity] * _CONFIDENCE_MULTIPLIER[f.confidence] for f in findings),
    )

    all_low_confidence = all(f.confidence == ConfidenceLevel.LOW for f in findings)
    any_medium_or_worse = any(
        f.severity in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM) for f in findings
    )
    if all_low_confidence and any_medium_or_worse:
        # The evidence exists, but the platform's own confidence in every
        # contributing finding is too low to trust an automated verdict —
        # route to a human rather than assert a possibly-wrong score.
        decision_category = DecisionCategory.MANUAL_REVIEW_REQUIRED
    elif any(f.severity == Severity.CRITICAL for f in findings):
        decision_category = DecisionCategory.CRITICAL_RISK
    elif weighted_score < _HIGH_RISK_THRESHOLD:
        decision_category = DecisionCategory.HIGH_RISK
    elif weighted_score < _REMEDIATION_REQUIRED_THRESHOLD:
        decision_category = DecisionCategory.REMEDIATION_REQUIRED
    elif weighted_score < _ACCEPTABLE_WITH_OBSERVATIONS_THRESHOLD:
        decision_category = DecisionCategory.ACCEPTABLE_WITH_OBSERVATIONS
    else:
        decision_category = DecisionCategory.ACCEPTABLE

    return ScoreResult(
        domain=domain,
        raw_score=raw_score,
        weighted_score=weighted_score,
        confidence_level=_finding_confidence(findings),
        evidence_completeness=evidence_completeness,
        decision_category=decision_category,
        files_evaluated=files_evaluated,
        findings_count=len(findings),
    )


def _coverage_confidence(files_evaluated: int) -> ConfidenceLevel:
    if files_evaluated >= 3:
        return ConfidenceLevel.HIGH
    if files_evaluated >= 1:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _finding_confidence(findings: List[FindingForScoring]) -> ConfidenceLevel:
    """A domain score's confidence reflects the weakest link: if any
    contributing finding is only LOW confidence, the aggregate score
    should not be presented as HIGH confidence."""
    levels = {f.confidence for f in findings}
    if ConfidenceLevel.LOW in levels:
        return ConfidenceLevel.LOW
    if ConfidenceLevel.MEDIUM in levels:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.HIGH
