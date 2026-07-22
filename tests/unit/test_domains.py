from __future__ import annotations

from core.domains import BankingDomain, BANKING_DOMAIN_LABELS, get_domain_label


def test_exactly_sixteen_domains():
    assert len(BankingDomain) == 16


def test_domain_values_are_unique():
    values = [d.value for d in BankingDomain]
    assert len(values) == len(set(values))


def test_every_domain_has_a_label():
    for domain in BankingDomain:
        assert domain in BANKING_DOMAIN_LABELS
        assert isinstance(get_domain_label(domain), str)
        assert get_domain_label(domain).strip() != ""


def test_labels_are_unique():
    labels = list(BANKING_DOMAIN_LABELS.values())
    assert len(labels) == len(set(labels))


def test_expected_domain_set_matches_approved_plan():
    expected = {
        "core_banking",
        "payments",
        "credit_lending",
        "investments_trading",
        "onboarding_identity_access",
        "transaction_processing_reporting",
        "fraud_controls",
        "privacy_data_protection",
        "application_security",
        "infrastructure_api_security",
        "database_controls_sod",
        "change_management",
        "monitoring_observability",
        "business_continuity_dr",
        "model_ai_governance",
        "human_approval_auditability",
    }
    assert {d.value for d in BankingDomain} == expected
