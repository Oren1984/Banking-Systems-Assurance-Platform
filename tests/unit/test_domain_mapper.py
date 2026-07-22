from __future__ import annotations

from core.domains import BankingDomain
from models.enums import ConfidenceLevel
from scanners.domain_mapper import all_domains_available, map_file_to_domains
from scanners.file_classifier import classify_file


def test_all_sixteen_domains_remain_available():
    domains = all_domains_available()
    assert len(domains) == 16
    assert len(set(domains)) == 16
    assert set(domains) == set(BankingDomain)


def test_mapping_output_only_uses_approved_domains():
    classification = classify_file("app/payments/processor.py", ".py")
    mappings = map_file_to_domains("app/payments/processor.py", classification)
    for m in mappings:
        assert isinstance(m.domain, BankingDomain)
        assert m.domain in BankingDomain


def test_payment_file_maps_to_payments_domain_with_high_confidence():
    classification = classify_file("app/payments/processor.py", ".py")
    mappings = map_file_to_domains("app/payments/processor.py", classification)
    payments_mappings = [m for m in mappings if m.domain == BankingDomain.PAYMENTS]
    assert len(payments_mappings) == 1
    assert payments_mappings[0].confidence == ConfidenceLevel.HIGH
    assert payments_mappings[0].reason
    assert payments_mappings[0].source


def test_credit_file_maps_to_credit_lending_domain():
    classification = classify_file("app/credit/loan_approval.py", ".py")
    mappings = map_file_to_domains("app/credit/loan_approval.py", classification)
    assert any(m.domain == BankingDomain.CREDIT_LENDING for m in mappings)


def test_unknown_content_maps_to_no_domains_safely():
    classification = classify_file("README.md", ".md")
    mappings = map_file_to_domains("README.md", classification)
    assert mappings == []


def test_terminology_hint_produces_low_confidence_mapping():
    classification = classify_file("app/fraud/detector.py", ".py")
    mappings = map_file_to_domains("app/fraud/detector.py", classification)
    fraud_mappings = [m for m in mappings if m.domain == BankingDomain.FRAUD_CONTROLS]
    assert len(fraud_mappings) == 1
    assert fraud_mappings[0].confidence == ConfidenceLevel.LOW


def test_a_file_can_map_to_multiple_domains():
    classification = classify_file("app/payments/audit_config.py", ".py")
    # "audit" hint (in file_classifier) + payment path both fire.
    mappings = map_file_to_domains("app/payments/audit_config.py", classification)
    domains = {m.domain for m in mappings}
    assert BankingDomain.PAYMENTS in domains
