from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core.exceptions import GovernanceError
from models.enums import DecisionCategory, HumanReviewStatus

# Phase 4 — Human-in-the-loop review/override workflow
# (BANKING_PLATFORM_INTEGRATION_PLAN.md §13 Phase 4:
# "governance/approval_workflow.py"). Pure functions, no database — mirrors
# scoring/engine.py and evidence/capture.py's design:
# storage/db/repositories.py::GovernanceRepository is the only place that
# applies the decisions this module validates.
#
# Two review surfaces already existed from Phase 3: Finding.human_review_status
# and Recommendation.status/reviewed_by/reviewed_at
# (storage/db/repositories.py::ScoringRepository.review_recommendation()).
# Phase 4 adds the third — Score overriding — and the actual governance gap
# Phase 3 left open: a policy deciding whether an assessment's results may
# be treated as final, given the current review state.


_VALID_FINDING_REVIEW_STATUSES = {
    HumanReviewStatus.APPROVED,
    HumanReviewStatus.REJECTED,
    HumanReviewStatus.OVERRIDDEN,
}


@dataclass
class FindingReviewDecision:
    finding_id: str
    new_status: HumanReviewStatus
    reviewed_by: str
    reason: Optional[str] = None


def review_finding(decision: FindingReviewDecision) -> FindingReviewDecision:
    """Validate a proposed Finding review action. Raises GovernanceError —
    never silently accepts — an invalid transition."""
    if not decision.reviewed_by.strip():
        raise GovernanceError("a finding review action must record a reviewer identity")
    if decision.new_status not in _VALID_FINDING_REVIEW_STATUSES:
        raise GovernanceError(
            f"cannot set a finding's human_review_status to {decision.new_status.value!r} via a "
            "review action — only approved, rejected, or overridden are valid outcomes of a "
            "review (pending is the system default, never a reviewer's chosen outcome)"
        )
    if decision.new_status == HumanReviewStatus.OVERRIDDEN and not (decision.reason or "").strip():
        raise GovernanceError("overriding a finding requires a non-empty reason")
    return decision


@dataclass
class ScoreOverrideDecision:
    original_score_id: str
    scan_id: str
    domain: str
    new_decision_category: DecisionCategory
    reviewed_by: str
    reason: str
    new_weighted_score: Optional[float] = None


def override_score(decision: ScoreOverrideDecision) -> ScoreOverrideDecision:
    """Validate a proposed Score override. Always requires a
    justification, never a bare category change — a human asserting a
    different verdict than the deterministic engine computed must say
    why, so the override is itself auditable."""
    if not decision.reviewed_by.strip():
        raise GovernanceError("a score override must record a reviewer identity")
    if not decision.reason.strip():
        raise GovernanceError("a score override requires a non-empty reason")
    return decision


@dataclass
class FindingReviewState:
    """The minimal shape this module needs from a persisted Finding row —
    deliberately not the ORM row itself, matching every other Phase 3/4
    assessment module's pure-input design."""

    finding_id: str
    domain_values: List[str]
    human_review_status: str  # models.enums.HumanReviewStatus value


@dataclass
class DomainScoreState:
    domain: str
    decision_category: str  # models.enums.DecisionCategory value


@dataclass
class FinalizationBlocker:
    domain: str
    reason: str


@dataclass
class FinalizationCheckResult:
    can_finalize: bool
    blockers: List[FinalizationBlocker] = field(default_factory=list)


_BLOCKING_DECISION_CATEGORIES = {DecisionCategory.CRITICAL_RISK, DecisionCategory.HIGH_RISK}


def check_finalization_policy(
    scores: List[DomainScoreState],
    findings: List[FindingReviewState],
) -> FinalizationCheckResult:
    """
    Policy: an assessment may not be marked final while any domain scored
    CRITICAL_RISK or HIGH_RISK still has at least one contributing finding
    whose human_review_status is PENDING. A domain scored
    REMEDIATION_REQUIRED or better does not block finalization regardless
    of review state; a blocking-severity domain whose findings have all
    reached a terminal review state (approved/rejected/overridden) does
    not block either — the policy gates on *pending review of the risk*,
    not on the risk itself being resolved (resolving it is a remediation
    decision outside this platform's scope — see
    RemediationMode.ADVISORY_ONLY).
    """
    blockers: List[FinalizationBlocker] = []
    blocking_domains = {
        s.domain for s in scores if DecisionCategory(s.decision_category) in _BLOCKING_DECISION_CATEGORIES
    }
    for domain in sorted(blocking_domains):
        pending = [
            f.finding_id
            for f in findings
            if domain in f.domain_values and f.human_review_status == HumanReviewStatus.PENDING.value
        ]
        if pending:
            blockers.append(
                FinalizationBlocker(
                    domain=domain,
                    reason=(
                        f"domain '{domain}' is high/critical risk and has {len(pending)} finding(s) "
                        "still pending human review"
                    ),
                )
            )
    return FinalizationCheckResult(can_finalize=not blockers, blockers=blockers)


__all__ = [
    "FindingReviewDecision",
    "review_finding",
    "ScoreOverrideDecision",
    "override_score",
    "FindingReviewState",
    "DomainScoreState",
    "FinalizationBlocker",
    "FinalizationCheckResult",
    "check_finalization_policy",
]
