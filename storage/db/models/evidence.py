from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from storage.db.base import Base

# Phase 3 — Evidence model (BANKING_PLATFORM_INTEGRATION_PLAN.md §11).
#
# `control_id` is a deliberate, documented addition beyond §11's literal
# field list (`id, finding_id, evidence_type, content, source_reference,
# retrieved_via, captured_at`) — required for the traceability the Phase 3
# brief demands ("Rule or control identifier" on every persisted record).
# Safe to add because Evidence is a net-new Phase 3 table with no Phase 1/2
# schema to preserve compatibility with.
#
# `content` MUST always be sanitized/masked text — in Phase 3 this is
# always a copy of Finding.masked_evidence (which itself is guaranteed
# never to be raw, see storage/db/models/finding.py's module docstring).
# Never populate this column from RawFinding.evidence.


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    finding_id: Mapped[str] = mapped_column(String(36), ForeignKey("findings.id"), nullable=False, index=True)
    control_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("controls.id"), nullable=True, index=True)

    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)  # models.enums.EvidenceType
    content: Mapped[str] = mapped_column(Text, nullable=False)  # sanitized only — see module docstring
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)  # "relative_path:line_start-line_end"
    retrieved_via: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # future RAG chunk_id; unused in Phase 3

    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
