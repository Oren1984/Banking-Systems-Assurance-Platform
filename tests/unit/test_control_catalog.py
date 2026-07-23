from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from controls.catalog import (
    CONTROL_CATALOG,
    applies_to_domain,
    control_for_rule_id,
    controls_for_domain,
    upsert_catalog,
)
from core.domains import BankingDomain
from models.enums import ControlType
from storage.db.base import Base
from storage.db.models.control import Control

# Phase 3 — controls/catalog.py. Two things must hold for the platform to
# trust this module: rule_id -> control lookup must be correct (it drives
# the Evidence/Recommendation control_id linkage in
# storage/db/repositories.py::ScoringRepository), and upsert_catalog() must
# be safe to call on every startup without ever duplicating rows.


def test_control_for_rule_id_matches_by_prefix():
    definition = control_for_rule_id("SECRET-001")
    assert definition is not None
    assert definition.control_id == "CTRL-SECRET-001"


def test_control_for_rule_id_returns_none_for_unmapped_prefix():
    assert control_for_rule_id("UNKNOWN-999") is None


def test_every_catalog_entry_has_a_unique_control_id_and_rule_prefix():
    control_ids = [c.control_id for c in CONTROL_CATALOG]
    rule_prefixes = [c.rule_prefix for c in CONTROL_CATALOG]
    assert len(control_ids) == len(set(control_ids))
    assert len(rule_prefixes) == len(set(rule_prefixes))


def test_every_catalog_entry_is_technical_not_regulatory():
    # BANKING_PLATFORM_INTEGRATION_PLAN.md §16 open question #4 is still
    # open — this catalog must never silently claim regulatory authority.
    with Session(create_engine("sqlite:///:memory:")) as session:
        Base.metadata.create_all(session.get_bind())
        rows = upsert_catalog(session)
        assert len(rows) == len(CONTROL_CATALOG)
        for row in rows:
            assert row.control_type == ControlType.TECHNICAL.value


def test_upsert_catalog_is_idempotent_and_does_not_duplicate_rows():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        upsert_catalog(session)
        session.commit()
        upsert_catalog(session)
        session.commit()

        all_rows = session.query(Control).all()
        assert len(all_rows) == len(CONTROL_CATALOG)


def test_upsert_catalog_updates_existing_row_fields_on_second_call():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        upsert_catalog(session)
        session.commit()

        row = session.query(Control).filter(Control.control_id == "CTRL-SECRET-001").one()
        row.title = "stale title that should be overwritten"
        session.commit()

        upsert_catalog(session)
        session.commit()

        refreshed = session.query(Control).filter(Control.control_id == "CTRL-SECRET-001").one()
        assert refreshed.title == "No hardcoded secrets or credentials in source"


# Phase 4 — applies_to_domain()/controls_for_domain(), added to support
# assessment/evaluators/control_evaluator.py and the knowledge_base/
# controls/ manifest generator.


def test_cross_cutting_control_applies_to_every_domain():
    secret_control = control_for_rule_id("SECRET-001")
    for domain in BankingDomain:
        assert applies_to_domain(secret_control, domain.value)


def test_domain_specific_control_applies_only_to_its_own_domain():
    audit_control = control_for_rule_id("AUDIT-001")
    assert applies_to_domain(audit_control, "human_approval_auditability")
    for domain in BankingDomain:
        if domain.value != "human_approval_auditability":
            assert not applies_to_domain(audit_control, domain.value)


def test_controls_for_domain_always_includes_the_four_cross_cutting_controls():
    cross_cutting_ids = {"CTRL-SECRET-001", "CTRL-PII-001", "CTRL-LOG-001", "CTRL-SKIP-001"}
    for domain in BankingDomain:
        ids = {c.control_id for c in controls_for_domain(domain.value)}
        assert cross_cutting_ids <= ids


def test_every_domain_has_at_least_one_applicable_control():
    for domain in BankingDomain:
        assert len(controls_for_domain(domain.value)) >= 1
