from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from storage.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ScannerExecutionRecord(Base):
    """One row per (scan, scanner) pair — records whether a scanner ran
    to completion for a given scan, how many findings it produced, and a
    sanitized error summary if it failed. A single unreadable/unscannable
    file must not fail an entire scanner's run — see
    scanners/scan_orchestrator.py's per-file error isolation."""

    __tablename__ = "scanner_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("scans.id"), nullable=False, index=True)

    scanner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scanner_version: Mapped[str] = mapped_column(String(16), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "completed" | "completed_with_errors" | "failed"
    files_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_errored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_produced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Sanitized only — never a raw exception message that might embed file
    # content (see scanners/scan_orchestrator.py::_sanitize_error).
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
