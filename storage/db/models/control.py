from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from storage.db.base import Base

# Phase 3 — Control model (BANKING_PLATFORM_INTEGRATION_PLAN.md §11:
# "Control (new — no existing analog in any of the three repos)").
#
# IMPORTANT SCOPING NOTE: the rows seeded into this table by
# controls/catalog.py are illustrative, engineering-derived technical
# controls tied 1:1 to the Phase 2 deterministic scanner categories (e.g.
# "source must not contain hardcoded secrets" <-> scanners/rules/
# secret_scanner.py). They are NOT a banking regulatory control library.
# Authoring that library requires banking/compliance domain expertise
# beyond this engineering phase's scope — see
# BANKING_PLATFORM_INTEGRATION_PLAN.md §16, open question #4, which
# remains open. Every seeded control's control_type is
# models.enums.ControlType.TECHNICAL for exactly this reason.


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Control(Base):
    __tablename__ = "controls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # Stable, human-assigned identifier (e.g. "CTRL-SECRET-001") — distinct
    # from the surrogate `id` primary key, used for cross-referencing in
    # documentation, exports, and source_reference fields elsewhere.
    control_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    domain: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # core.domains.BankingDomain value, or None if cross-cutting
    subdomain: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    control_type: Mapped[str] = mapped_column(String(32), nullable=False)  # models.enums.ControlType

    # Where this control's requirement comes from — for the Phase 3 seed
    # catalog, a scanner rule_id prefix (e.g. "SECRET-*"); in a future
    # domain-authored library, a policy/standard document reference.
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)

    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Empty list = applies universally, not restricted to specific domains.
    applies_to_domains: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
