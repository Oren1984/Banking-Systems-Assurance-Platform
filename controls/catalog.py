from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.enums import ControlType
from storage.db.models.control import Control

# Phase 3 — Control catalog (BANKING_PLATFORM_INTEGRATION_PLAN.md §11,
# Included list: "controls/*").
#
# NOT A REGULATORY CONTROL LIBRARY. Every control below is an illustrative,
# engineering-derived technical control mapped 1:1 to a Phase 2 deterministic
# scanner category (`scanners/rules/*.py`). Authoring a real banking
# regulatory/compliance control library requires domain expertise beyond
# this engineering phase's scope — see BANKING_PLATFORM_INTEGRATION_PLAN.md
# §16, open question #4, which remains open. Every entry's control_type is
# ControlType.TECHNICAL for exactly this reason; the platform never claims
# regulatory compliance from these (see governance/report_sanitizer.py and
# docs/security_boundaries.md).


@dataclass(frozen=True)
class ControlDefinition:
    control_id: str
    title: str
    description: str
    source_reference: str  # human-readable provenance, stored on the Control row
    rule_prefix: str  # e.g. "SECRET-" — matched against Finding.rule_id by control_for_rule_id()
    weight: float = 1.0
    domain: str | None = None
    subdomain: str | None = None
    applies_to_domains: List[str] = field(default_factory=list)


CONTROL_CATALOG: tuple[ControlDefinition, ...] = (
    ControlDefinition(
        control_id="CTRL-SECRET-001",
        title="No hardcoded secrets or credentials in source",
        description=(
            "Source code, configuration, and scripts must not contain hardcoded API keys, "
            "passwords, tokens, private keys, or connection-string credentials."
        ),
        source_reference="scanners/rules/secret_scanner.py",
        rule_prefix="SECRET-",
        weight=2.0,
    ),
    ControlDefinition(
        control_id="CTRL-PII-001",
        title="No unnecessary sensitive/PII data in source or fixtures",
        description=(
            "Source, configuration, and test fixtures should not contain patterns resembling "
            "real customer PII (national ID, card/account numbers, DOB, contact details)."
        ),
        source_reference="scanners/rules/pii_scanner.py",
        rule_prefix="PII-",
        weight=1.5,
    ),
    ControlDefinition(
        control_id="CTRL-LOG-001",
        title="Sensitive data must not be logged",
        description="Logging statements must not include passwords, tokens, PII, or card data.",
        source_reference="scanners/rules/unsafe_logging_scanner.py",
        rule_prefix="LOG-",
        weight=1.5,
    ),
    ControlDefinition(
        control_id="CTRL-AUDIT-001",
        title="Sensitive operations must be auditable",
        description=(
            "Audit logging must not be disabled; sensitive operations should have an "
            "identifiable audit trail with actor, action, and timestamp."
        ),
        source_reference="scanners/rules/audit_scanner.py",
        rule_prefix="AUDIT-",
        weight=1.5,
        domain="human_approval_auditability",
    ),
    ControlDefinition(
        control_id="CTRL-PERM-001",
        title="Access permissions must follow least privilege",
        description="Wildcard IAM policies, admin-by-default roles, and public/anonymous access flags should not be present.",
        source_reference="scanners/rules/permission_scanner.py",
        rule_prefix="PERM-",
        weight=2.0,
        domain="application_security",
    ),
    ControlDefinition(
        control_id="CTRL-SQL-001",
        title="SQL must be parameterized and non-destructive by default",
        description="SQL must not be built via string concatenation/interpolation, and destructive statements must not appear in ordinary source.",
        source_reference="scanners/rules/sql_scanner.py",
        rule_prefix="SQL-",
        weight=2.0,
        domain="database_controls_sod",
    ),
    ControlDefinition(
        control_id="CTRL-CFG-001",
        title="Configuration must be secure by default",
        description="Debug mode, disabled TLS verification, disabled auth/encryption, permissive CORS, and default weak credentials must not be present.",
        source_reference="scanners/rules/insecure_config_scanner.py",
        rule_prefix="CFG-",
        weight=1.5,
        domain="infrastructure_api_security",
    ),
    ControlDefinition(
        control_id="CTRL-SKIP-001",
        title="Sensitive-looking unscanned files must be reviewed",
        description="Files skipped during discovery whose name suggests sensitive content should be manually reviewed rather than silently ignored.",
        source_reference="scanners/rules/unsupported_file_scanner.py",
        rule_prefix="SKIP-",
        weight=0.5,
    ),
)


def upsert_catalog(session: Session) -> List[Control]:
    """
    Idempotently insert or update the Phase 3 illustrative control catalog.
    Safe to call repeatedly (e.g. on every application startup) — matches
    by `control_id`, never creates duplicates.
    """
    rows: List[Control] = []
    for definition in CONTROL_CATALOG:
        existing = session.execute(
            select(Control).where(Control.control_id == definition.control_id)
        ).scalar_one_or_none()
        if existing is not None:
            existing.title = definition.title
            existing.description = definition.description
            existing.source_reference = definition.source_reference
            existing.weight = definition.weight
            existing.domain = definition.domain
            existing.subdomain = definition.subdomain
            existing.applies_to_domains = list(definition.applies_to_domains)
            rows.append(existing)
            continue
        row = Control(
            control_id=definition.control_id,
            title=definition.title,
            description=definition.description,
            control_type=ControlType.TECHNICAL.value,
            source_reference=definition.source_reference,
            weight=definition.weight,
            domain=definition.domain,
            subdomain=definition.subdomain,
            applies_to_domains=list(definition.applies_to_domains),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def control_for_rule_id(rule_id: str) -> ControlDefinition | None:
    """Match a scanner finding's rule_id (e.g. 'SECRET-001') to the
    catalog control whose rule_prefix covers it. Pure lookup, no database
    access — used by scoring/engine.py and evidence/capture.py to
    annotate in-memory findings before persistence."""
    for definition in CONTROL_CATALOG:
        if rule_id.startswith(definition.rule_prefix):
            return definition
    return None
