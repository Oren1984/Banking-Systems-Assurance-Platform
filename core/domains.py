from __future__ import annotations

from enum import Enum


class BankingDomain(str, Enum):
    """
    The 16 approved banking and financial assurance domains.

    This is the single canonical definition of platform scope. Every other
    module (models, scoring, reports, controls, mock data, UI) must import
    this enum rather than defining its own domain list — see
    BANKING_PLATFORM_INTEGRATION_PLAN.md Part A §1 (approved plan revision):
    "Do not define duplicate domain lists in multiple files."

    Populating the actual control library content for each domain is a
    later-phase, domain-expert-driven workstream (see
    BANKING_PLATFORM_INTEGRATION_PLAN.md §16, open question #4) — this enum
    defines the *shape* of platform scope only, not control content.
    """

    CORE_BANKING = "core_banking"
    PAYMENTS = "payments"
    CREDIT_LENDING = "credit_lending"
    INVESTMENTS_TRADING = "investments_trading"
    ONBOARDING_IDENTITY_ACCESS = "onboarding_identity_access"
    TRANSACTION_PROCESSING_REPORTING = "transaction_processing_reporting"
    FRAUD_CONTROLS = "fraud_controls"
    PRIVACY_DATA_PROTECTION = "privacy_data_protection"
    APPLICATION_SECURITY = "application_security"
    INFRASTRUCTURE_API_SECURITY = "infrastructure_api_security"
    DATABASE_CONTROLS_SOD = "database_controls_sod"
    CHANGE_MANAGEMENT = "change_management"
    MONITORING_OBSERVABILITY = "monitoring_observability"
    BUSINESS_CONTINUITY_DR = "business_continuity_dr"
    MODEL_AI_GOVERNANCE = "model_ai_governance"
    HUMAN_APPROVAL_AUDITABILITY = "human_approval_auditability"


# Human-readable display labels, keyed by enum member. Kept alongside the
# enum (not derived from it) so labels can be refined without touching the
# stable machine-readable values used in the database and API.
BANKING_DOMAIN_LABELS: dict[BankingDomain, str] = {
    BankingDomain.CORE_BANKING: "Core Banking and Account Management",
    BankingDomain.PAYMENTS: "Payments",
    BankingDomain.CREDIT_LENDING: "Credit and Lending",
    BankingDomain.INVESTMENTS_TRADING: "Investments and Trading-Related Systems",
    BankingDomain.ONBOARDING_IDENTITY_ACCESS: "Customer Onboarding, Identity, and Access",
    BankingDomain.TRANSACTION_PROCESSING_REPORTING: "Transaction Processing and Financial Reporting",
    BankingDomain.FRAUD_CONTROLS: "Fraud-Related Controls",
    BankingDomain.PRIVACY_DATA_PROTECTION: "Privacy and Data Protection",
    BankingDomain.APPLICATION_SECURITY: "Application Security",
    BankingDomain.INFRASTRUCTURE_API_SECURITY: "Infrastructure and API Security",
    BankingDomain.DATABASE_CONTROLS_SOD: "Database Controls and Segregation of Duties",
    BankingDomain.CHANGE_MANAGEMENT: "Change Management",
    BankingDomain.MONITORING_OBSERVABILITY: "Monitoring and Observability",
    BankingDomain.BUSINESS_CONTINUITY_DR: "Business Continuity and Disaster Recovery",
    BankingDomain.MODEL_AI_GOVERNANCE: "Model and AI Governance",
    BankingDomain.HUMAN_APPROVAL_AUDITABILITY: "Human Approval Controls and Auditability",
}


def get_domain_label(domain: BankingDomain) -> str:
    return BANKING_DOMAIN_LABELS[domain]


__all__ = ["BankingDomain", "BANKING_DOMAIN_LABELS", "get_domain_label"]
