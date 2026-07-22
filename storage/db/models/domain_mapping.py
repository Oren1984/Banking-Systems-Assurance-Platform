from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from storage.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DomainMappingRecord(Base):
    """One row per (file, banking domain) association produced by
    scanners/domain_mapper.py. A single file may have several rows (it can
    map to more than one domain), each with its own confidence/evidence."""

    __tablename__ = "domain_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("scans.id"), nullable=False, index=True)
    file_inventory_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("file_inventory.id"), nullable=True, index=True
    )

    domain: Mapped[str] = mapped_column(String(64), nullable=False)  # core.domains.BankingDomain value
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)  # models.enums.ConfidenceLevel value
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # models.enums.MappingSource value

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
