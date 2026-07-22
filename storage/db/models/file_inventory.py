from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from storage.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FileInventoryRecord(Base):
    """One row per discovered file — scanned or skipped. Populated from
    scanners.file_discovery.FileInventoryItem / SkippedFile by
    scanners/scan_orchestrator.py. See that dataclass's docstring for why
    the in-memory and persisted shapes are kept separate."""

    __tablename__ = "file_inventory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("scans.id"), nullable=False, index=True)

    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    detected_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    sensitivity_hint: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # "scanned" | "skipped"
    scan_status: Mapped[str] = mapped_column(String(20), nullable=False)
    skipped_reason: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
