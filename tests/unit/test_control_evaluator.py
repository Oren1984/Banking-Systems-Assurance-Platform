from __future__ import annotations

from assessment.evaluators.control_evaluator import (
    FindingForControlEvaluation,
    domain_coverage_manifest,
    evaluate_all_domains,
    evaluate_domain,
)
from controls.catalog import CONTROL_CATALOG
from core.domains import BankingDomain
from models.enums import ControlEvaluationStatus

# Phase 4 — assessment/evaluators/control_evaluator.py. Pure function, no
# database. Mirrors tests/unit/test_scoring_engine.py's approach: the core
# fix (a domain never evaluated must never resolve to a false SATISFIED)
# is the single most important thing this test file must prove.


def test_unevaluated_domain_resolves_every_applicable_control_to_insufficient_evidence():
    results = evaluate_domain(BankingDomain.PAYMENTS, findings=[], evaluated=False)
    assert len(results) >= 1
    for r in results:
        assert r.status == ControlEvaluationStatus.INSUFFICIENT_EVIDENCE
        assert r.finding_ids == []


def test_evaluated_domain_with_no_matching_findings_is_satisfied_not_insufficient():
    results = evaluate_domain(BankingDomain.PAYMENTS, findings=[], evaluated=True)
    assert results
    for r in results:
        assert r.status == ControlEvaluationStatus.SATISFIED


def test_evaluated_domain_with_a_matching_finding_is_a_gap():
    findings = [
        FindingForControlEvaluation(finding_id="f1", rule_id="SECRET-001", domains=["payments"])
    ]
    results = evaluate_domain(BankingDomain.PAYMENTS, findings, evaluated=True)
    by_control = {r.control_id: r for r in results}
    assert by_control["CTRL-SECRET-001"].status == ControlEvaluationStatus.GAP
    assert by_control["CTRL-SECRET-001"].finding_ids == ["f1"]
    # An unrelated cross-cutting control in the same domain is unaffected.
    assert by_control["CTRL-PII-001"].status == ControlEvaluationStatus.SATISFIED


def test_evaluate_all_domains_covers_all_sixteen():
    results = evaluate_all_domains([], evaluated_domains=set())
    domains_covered = {r.domain for r in results}
    assert domains_covered == set(BankingDomain)


def test_evaluate_all_domains_only_the_evaluated_domain_gets_satisfied_or_gap():
    findings = [
        FindingForControlEvaluation(finding_id="f1", rule_id="SECRET-001", domains=["payments"])
    ]
    results = evaluate_all_domains(findings, evaluated_domains={"payments"})
    by_domain: dict = {}
    for r in results:
        by_domain.setdefault(r.domain, []).append(r)

    for r in by_domain[BankingDomain.PAYMENTS]:
        assert r.status != ControlEvaluationStatus.INSUFFICIENT_EVIDENCE

    for domain, rows in by_domain.items():
        if domain != BankingDomain.PAYMENTS:
            for r in rows:
                assert r.status == ControlEvaluationStatus.INSUFFICIENT_EVIDENCE


def test_finding_only_affects_control_evaluations_for_domains_it_is_mapped_to():
    findings = [
        FindingForControlEvaluation(finding_id="f1", rule_id="SECRET-001", domains=["payments"])
    ]
    results = evaluate_all_domains(findings, evaluated_domains={"payments", "credit_lending"})
    by_domain: dict = {}
    for r in results:
        by_domain.setdefault(r.domain, []).append(r)

    credit_rows = by_domain[BankingDomain.CREDIT_LENDING]
    for r in credit_rows:
        assert r.status == ControlEvaluationStatus.SATISFIED
        assert r.finding_ids == []


def test_domain_coverage_manifest_covers_all_sixteen_domains_with_at_least_one_control():
    manifest = domain_coverage_manifest()
    assert set(manifest.keys()) == {d.value for d in BankingDomain}
    for domain, control_ids in manifest.items():
        assert len(control_ids) >= 1, f"domain {domain!r} has no applicable control"


def test_domain_coverage_manifest_control_ids_are_real_catalog_entries():
    manifest = domain_coverage_manifest()
    all_control_ids = {c.control_id for c in CONTROL_CATALOG}
    for control_ids in manifest.values():
        assert set(control_ids) <= all_control_ids
