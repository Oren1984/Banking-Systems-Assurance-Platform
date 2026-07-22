from __future__ import annotations

from core.domains import BankingDomain
from models.enums import ConfidenceLevel, DecisionCategory, EvidenceCompleteness, Severity
from scoring.engine import FindingForScoring, score_all_domains, score_domain

# The single most important test in this file: the core fix
# BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 3 names as its expected
# output — a domain with zero findings because it was never evaluated
# must resolve to INSUFFICIENT_EVIDENCE, never a false "clean" score.


def test_unevaluated_domain_is_insufficient_evidence_not_clean():
    result = score_domain(BankingDomain.PAYMENTS, findings=[], evaluated=False, files_evaluated=0)
    assert result.decision_category == DecisionCategory.INSUFFICIENT_EVIDENCE
    assert result.evidence_completeness == EvidenceCompleteness.INSUFFICIENT
    assert result.raw_score is None
    assert result.weighted_score is None


def test_evaluated_domain_with_zero_findings_is_acceptable_not_insufficient():
    # The critical boundary case: same "zero findings" outcome as the
    # test above, but this domain WAS evaluated — must NOT be flagged
    # insufficient_evidence.
    result = score_domain(BankingDomain.PAYMENTS, findings=[], evaluated=True, files_evaluated=3)
    assert result.decision_category == DecisionCategory.ACCEPTABLE
    assert result.evidence_completeness != EvidenceCompleteness.INSUFFICIENT
    assert result.raw_score == 100.0
    assert result.weighted_score == 100.0


def test_evaluated_domain_with_only_one_file_is_partial_evidence():
    result = score_domain(BankingDomain.PAYMENTS, findings=[], evaluated=True, files_evaluated=1)
    assert result.evidence_completeness == EvidenceCompleteness.PARTIAL


def test_critical_finding_forces_critical_risk_regardless_of_score():
    findings = [
        FindingForScoring(
            rule_id="SECRET-001", severity=Severity.CRITICAL, confidence=ConfidenceLevel.HIGH, domains=["payments"]
        )
    ]
    result = score_domain(BankingDomain.PAYMENTS, findings, evaluated=True, files_evaluated=5)
    assert result.decision_category == DecisionCategory.CRITICAL_RISK


def test_all_low_confidence_findings_route_to_manual_review():
    findings = [
        FindingForScoring(
            rule_id="AUDIT-002", severity=Severity.MEDIUM, confidence=ConfidenceLevel.LOW, domains=["payments"]
        )
    ]
    result = score_domain(BankingDomain.PAYMENTS, findings, evaluated=True, files_evaluated=2)
    assert result.decision_category == DecisionCategory.MANUAL_REVIEW_REQUIRED


def test_high_severity_high_confidence_finding_reduces_score():
    findings = [
        FindingForScoring(
            rule_id="SECRET-001", severity=Severity.HIGH, confidence=ConfidenceLevel.HIGH, domains=["payments"]
        )
    ]
    result = score_domain(BankingDomain.PAYMENTS, findings, evaluated=True, files_evaluated=5)
    assert result.raw_score == 75.0
    assert result.weighted_score == 75.0  # HIGH confidence multiplier is 1.0, no discount
    # Exactly 75 falls on the ACCEPTABLE_WITH_OBSERVATIONS/ACCEPTABLE boundary
    # (the threshold check is strictly "< 75") — lands in ACCEPTABLE.
    assert result.decision_category == DecisionCategory.ACCEPTABLE


def test_score_just_below_acceptable_with_observations_threshold():
    findings = [
        FindingForScoring(rule_id="SECRET-001", severity=Severity.HIGH, confidence=ConfidenceLevel.HIGH, domains=["payments"]),
        FindingForScoring(rule_id="PII-EMAIL", severity=Severity.LOW, confidence=ConfidenceLevel.HIGH, domains=["payments"]),
    ]
    result = score_domain(BankingDomain.PAYMENTS, findings, evaluated=True, files_evaluated=5)
    assert result.weighted_score == 70.0  # 100 - 25 - 5
    assert result.decision_category == DecisionCategory.ACCEPTABLE_WITH_OBSERVATIONS


def test_low_confidence_finding_is_discounted_in_weighted_score_but_not_raw_score():
    findings = [
        FindingForScoring(
            rule_id="PII-EMAIL", severity=Severity.HIGH, confidence=ConfidenceLevel.LOW, domains=["payments"]
        )
    ]
    result = score_domain(BankingDomain.PAYMENTS, findings, evaluated=True, files_evaluated=5)
    assert result.raw_score == 75.0
    assert result.weighted_score == 90.0  # 100 - (25 * 0.4)
    assert result.weighted_score > result.raw_score


def test_score_never_goes_below_zero():
    findings = [
        FindingForScoring(rule_id="X-1", severity=Severity.CRITICAL, confidence=ConfidenceLevel.HIGH, domains=["payments"])
        for _ in range(10)
    ]
    result = score_domain(BankingDomain.PAYMENTS, findings, evaluated=True, files_evaluated=5)
    assert result.raw_score == 0.0
    assert result.weighted_score == 0.0


def test_domain_confidence_reflects_weakest_contributing_finding():
    findings = [
        FindingForScoring(rule_id="A", severity=Severity.LOW, confidence=ConfidenceLevel.HIGH, domains=["payments"]),
        FindingForScoring(rule_id="B", severity=Severity.LOW, confidence=ConfidenceLevel.LOW, domains=["payments"]),
    ]
    result = score_domain(BankingDomain.PAYMENTS, findings, evaluated=True, files_evaluated=5)
    assert result.confidence_level == ConfidenceLevel.LOW


def test_score_all_domains_scores_all_sixteen_including_untouched_ones():
    findings = [
        FindingForScoring(rule_id="SECRET-001", severity=Severity.HIGH, confidence=ConfidenceLevel.HIGH, domains=["payments"])
    ]
    results = score_all_domains(findings, evaluated_domains={"payments"}, files_evaluated_by_domain={"payments": 3})
    assert len(results) == 16
    by_domain = {r.domain: r for r in results}
    assert by_domain[BankingDomain.PAYMENTS].decision_category != DecisionCategory.INSUFFICIENT_EVIDENCE
    # Every domain other than "payments" was never evaluated in this scan.
    for domain, result in by_domain.items():
        if domain != BankingDomain.PAYMENTS:
            assert result.decision_category == DecisionCategory.INSUFFICIENT_EVIDENCE


def test_finding_only_counts_toward_domains_it_is_actually_mapped_to():
    findings = [
        FindingForScoring(rule_id="SECRET-001", severity=Severity.CRITICAL, confidence=ConfidenceLevel.HIGH, domains=["payments"])
    ]
    results = score_all_domains(
        findings,
        evaluated_domains={"payments", "credit_lending"},
        files_evaluated_by_domain={"payments": 2, "credit_lending": 2},
    )
    by_domain = {r.domain: r for r in results}
    assert by_domain[BankingDomain.PAYMENTS].decision_category == DecisionCategory.CRITICAL_RISK
    assert by_domain[BankingDomain.CREDIT_LENDING].decision_category == DecisionCategory.ACCEPTABLE
    assert by_domain[BankingDomain.CREDIT_LENDING].findings_count == 0
