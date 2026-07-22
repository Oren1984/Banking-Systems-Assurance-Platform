from __future__ import annotations

from dataclasses import dataclass

from core.domains import BankingDomain
from models.enums import ConfidenceLevel, MappingSource
from scanners.file_classifier import ClassificationResult

# Phase 2 — Mapping to the 16 Banking Domains
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2 brief, §5). Uses only
# core.domains.BankingDomain — the single canonical 16-domain definition
# from Phase 1. No domain is renamed, added, merged, or removed here.
#
# Deterministic evidence only: file/directory names, classification
# category flags (already keyword-derived in file_classifier.py), and
# known banking terminology. Every mapping states its confidence and the
# evidence it was derived from — low-confidence matches are never
# presented as settled fact.


@dataclass(frozen=True)
class DomainMapping:
    domain: BankingDomain
    confidence: ConfidenceLevel
    reason: str
    source: MappingSource


# Category flag (from file_classifier.ClassificationResult) -> banking domain(s).
# Each entry maps one deterministic classification signal to a domain with a
# confidence level reflecting how specific that signal is.
_FLAG_TO_DOMAIN: dict[str, tuple[BankingDomain, ConfidenceLevel]] = {
    "payment_related": (BankingDomain.PAYMENTS, ConfidenceLevel.HIGH),
    "account_related": (BankingDomain.CORE_BANKING, ConfidenceLevel.MEDIUM),
    "credit_lending_related": (BankingDomain.CREDIT_LENDING, ConfidenceLevel.HIGH),
    "investment_related": (BankingDomain.INVESTMENTS_TRADING, ConfidenceLevel.HIGH),
    "customer_identity_related": (BankingDomain.ONBOARDING_IDENTITY_ACCESS, ConfidenceLevel.HIGH),
    "auth_config": (BankingDomain.ONBOARDING_IDENTITY_ACCESS, ConfidenceLevel.MEDIUM),
    "audit_related": (BankingDomain.HUMAN_APPROVAL_AUDITABILITY, ConfidenceLevel.HIGH),
    "logging_config": (BankingDomain.MONITORING_OBSERVABILITY, ConfidenceLevel.MEDIUM),
    "monitoring_config": (BankingDomain.MONITORING_OBSERVABILITY, ConfidenceLevel.HIGH),
    "data_governance_related": (BankingDomain.PRIVACY_DATA_PROTECTION, ConfidenceLevel.MEDIUM),
    "security_controls": (BankingDomain.APPLICATION_SECURITY, ConfidenceLevel.MEDIUM),
    "database_schema_or_migration": (BankingDomain.DATABASE_CONTROLS_SOD, ConfidenceLevel.MEDIUM),
    "api_definition": (BankingDomain.INFRASTRUCTURE_API_SECURITY, ConfidenceLevel.MEDIUM),
    "is_infrastructure_as_code": (BankingDomain.INFRASTRUCTURE_API_SECURITY, ConfidenceLevel.MEDIUM),
    "is_deployment_or_environment": (BankingDomain.CHANGE_MANAGEMENT, ConfidenceLevel.LOW),
}

# Direct banking-terminology hints checked against the file's relative path,
# independent of file_classifier's flags — a second, lower-weight signal
# source (MappingSource.BANKING_TERMINOLOGY vs. the flag-based mappings'
# MappingSource.SCANNER_RESULT).
_TERMINOLOGY_HINTS: dict[str, BankingDomain] = {
    "fraud": BankingDomain.FRAUD_CONTROLS,
    "aml": BankingDomain.FRAUD_CONTROLS,
    "sanctions": BankingDomain.FRAUD_CONTROLS,
    "reconcil": BankingDomain.TRANSACTION_PROCESSING_REPORTING,
    "ledger": BankingDomain.TRANSACTION_PROCESSING_REPORTING,
    "disaster_recovery": BankingDomain.BUSINESS_CONTINUITY_DR,
    "backup": BankingDomain.BUSINESS_CONTINUITY_DR,
    "failover": BankingDomain.BUSINESS_CONTINUITY_DR,
    "model_governance": BankingDomain.MODEL_AI_GOVERNANCE,
    "ml_model": BankingDomain.MODEL_AI_GOVERNANCE,
}


def map_file_to_domains(
    relative_path: str, classification: ClassificationResult
) -> list[DomainMapping]:
    """
    Deterministically map one discovered file to zero or more banking
    domains, each with its own confidence and evidence trail. A file may
    legitimately map to multiple domains (e.g. a payments audit-log
    config maps to both PAYMENTS and HUMAN_APPROVAL_AUDITABILITY).
    """
    mappings: list[DomainMapping] = []
    seen: set[BankingDomain] = set()

    for flag_name, is_set in classification.category_flags.items():
        if not is_set:
            continue
        mapping = _FLAG_TO_DOMAIN.get(flag_name)
        if mapping is None:
            continue
        domain, confidence = mapping
        if domain in seen:
            continue
        seen.add(domain)
        mappings.append(
            DomainMapping(
                domain=domain,
                confidence=confidence,
                reason=f"classification flag '{flag_name}' was set for this file",
                source=MappingSource.SCANNER_RESULT,
            )
        )

    path_lower = relative_path.lower()
    for keyword, domain in _TERMINOLOGY_HINTS.items():
        if keyword not in path_lower or domain in seen:
            continue
        seen.add(domain)
        mappings.append(
            DomainMapping(
                domain=domain,
                confidence=ConfidenceLevel.LOW,
                reason=f"path contains banking terminology keyword '{keyword}'",
                source=MappingSource.BANKING_TERMINOLOGY,
            )
        )

    return mappings


def all_domains_available() -> tuple[BankingDomain, ...]:
    """Convenience accessor used by tests to prove all 16 domains remain
    reachable through this module without duplicating the enum."""
    return tuple(BankingDomain)
