from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from storage.db.base import Base

# Phase 4 — Audit Event model (BANKING_PLATFORM_INTEGRATION_PLAN.md §13
# Phase 4: "models/audit_event.py"). An append-only log of every
# governance-relevant action: scan persistence, scoring/control-evaluation
# runs, and every human review/override decision.
#
# APPEND-ONLY BY CONSTRUCTION: this model defines no `updated_at` column,
# and storage/db/repositories.py::AuditRepository exposes only a `record()`
# method — no update or delete method exists anywhere in this codebase for
# this table. An audit trail that could be edited or removed after the
# fact would not be an audit trail; see governance/audit_trail.py's own
# module docstring for the same point applied to how events are built.
#
# `summary` and `payload` are sanitized before this row is ever
# constructed (governance/audit_trail.py::build_audit_event() runs
# governance/report_sanitizer.py::sanitize_report() on every free-text
# value) — this table must never be the place a raw secret or unmasked
# evidence value first reaches persistent storage.


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # Nullable: not every governance event is scoped to one scan (none are
    # today, but a future platform-level event — e.g. a retention sweep —
    # would not have a single scan_id to attach to).
    scan_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("scans.id"), nullable=True, index=True)

    event_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)  # models.enums.AuditEventType

    # "system" for automated pipeline steps (scan persisted, scoring run);
    # a reviewer identity string for human actions (approve/reject/override).
    actor: Mapped[str] = mapped_column(String(128), nullable=False)

    summary: Mapped[str] = mapped_column(Text, nullable=False)  # sanitized, human-readable
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # sanitized, structured detail

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
