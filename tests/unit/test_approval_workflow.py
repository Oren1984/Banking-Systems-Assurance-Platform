from __future__ import annotations

import pytest

from core.exceptions import GovernanceError
from governance.approval_workflow import (
    DomainScoreState,
    FindingReviewDecision,
    FindingReviewState,
    ScoreOverrideDecision,
    check_finalization_policy,
    override_score,
    review_finding,
)
from models.enums import DecisionCategory, HumanReviewStatus

# Phase 4 — governance/approval_workflow.py. Pure functions, no database.


def test_review_finding_accepts_approved():
    decision = review_finding(
        FindingReviewDecision(
            finding_id="f1", new_status=HumanReviewStatus.APPROVED, reviewed_by="reviewer@example.com"
        )
    )
    assert decision.new_status == HumanReviewStatus.APPROVED


def test_review_finding_rejects_setting_status_back_to_pending():
    with pytest.raises(GovernanceError):
        review_finding(
            FindingReviewDecision(
                finding_id="f1", new_status=HumanReviewStatus.PENDING, reviewed_by="reviewer@example.com"
            )
        )


def test_review_finding_requires_a_reviewer_identity():
    with pytest.raises(GovernanceError):
        review_finding(
            FindingReviewDecision(finding_id="f1", new_status=HumanReviewStatus.APPROVED, reviewed_by="   ")
        )


def test_review_finding_overridden_requires_a_reason():
    with pytest.raises(GovernanceError):
        review_finding(
            FindingReviewDecision(
                finding_id="f1",
                new_status=HumanReviewStatus.OVERRIDDEN,
                reviewed_by="reviewer@example.com",
                reason="  ",
            )
        )


def test_review_finding_overridden_with_a_reason_succeeds():
    decision = review_finding(
        FindingReviewDecision(
            finding_id="f1",
            new_status=HumanReviewStatus.OVERRIDDEN,
            reviewed_by="reviewer@example.com",
            reason="False positive: test fixture, not a real credential.",
        )
    )
    assert decision.new_status == HumanReviewStatus.OVERRIDDEN


def test_override_score_requires_reviewer_and_reason():
    with pytest.raises(GovernanceError):
        override_score(
            ScoreOverrideDecision(
                original_score_id="s1",
                scan_id="scan-1",
                domain="payments",
                new_decision_category=DecisionCategory.ACCEPTABLE,
                reviewed_by="",
                reason="justified",
            )
        )
    with pytest.raises(GovernanceError):
        override_score(
            ScoreOverrideDecision(
                original_score_id="s1",
                scan_id="scan-1",
                domain="payments",
                new_decision_category=DecisionCategory.ACCEPTABLE,
                reviewed_by="reviewer@example.com",
                reason="   ",
            )
        )


def test_override_score_with_reviewer_and_reason_succeeds():
    decision = override_score(
        ScoreOverrideDecision(
            original_score_id="s1",
            scan_id="scan-1",
            domain="payments",
            new_decision_category=DecisionCategory.ACCEPTABLE,
            reviewed_by="reviewer@example.com",
            reason="Compensating control confirmed out-of-band.",
        )
    )
    assert decision.new_decision_category == DecisionCategory.ACCEPTABLE


def test_finalization_blocked_by_pending_finding_in_critical_risk_domain():
    scores = [DomainScoreState(domain="payments", decision_category=DecisionCategory.CRITICAL_RISK.value)]
    findings = [
        FindingReviewState(
            finding_id="f1", domain_values=["payments"], human_review_status=HumanReviewStatus.PENDING.value
        )
    ]
    result = check_finalization_policy(scores, findings)
    assert result.can_finalize is False
    assert result.blockers[0].domain == "payments"


def test_finalization_not_blocked_when_high_risk_findings_all_reviewed():
    scores = [DomainScoreState(domain="payments", decision_category=DecisionCategory.HIGH_RISK.value)]
    findings = [
        FindingReviewState(
            finding_id="f1", domain_values=["payments"], human_review_status=HumanReviewStatus.APPROVED.value
        )
    ]
    result = check_finalization_policy(scores, findings)
    assert result.can_finalize is True
    assert result.blockers == []


def test_finalization_not_blocked_for_acceptable_domain_regardless_of_review_state():
    scores = [DomainScoreState(domain="payments", decision_category=DecisionCategory.ACCEPTABLE.value)]
    findings = [
        FindingReviewState(
            finding_id="f1", domain_values=["payments"], human_review_status=HumanReviewStatus.PENDING.value
        )
    ]
    result = check_finalization_policy(scores, findings)
    assert result.can_finalize is True


def test_finalization_ignores_pending_findings_in_unrelated_domains():
    scores = [
        DomainScoreState(domain="payments", decision_category=DecisionCategory.CRITICAL_RISK.value),
        DomainScoreState(domain="credit_lending", decision_category=DecisionCategory.ACCEPTABLE.value),
    ]
    findings = [
        FindingReviewState(
            finding_id="f1",
            domain_values=["credit_lending"],
            human_review_status=HumanReviewStatus.PENDING.value,
        )
    ]
    # payments is critical_risk but has no findings mapped to it at all —
    # nothing pending there, so it must not block.
    result = check_finalization_policy(scores, findings)
    assert result.can_finalize is True
