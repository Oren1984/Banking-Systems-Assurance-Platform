from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from storage.db.base import Base

# Phase 2 persistence — one row per scan run
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2 brief, §9). Adapted in
# spirit from ai-project-control-tower/app/db/models/audit_run.py (that
# repository's closest analog), rebuilt against this platform's own
# scanners/scan_orchestrator.py flow rather than copied directly.


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # Never the raw local filesystem path from an untrusted caller by
    # default — orchestrator stores the *resolved, allowlist-validated*
    # path here. Still local-machine-specific, so exports prefer relative
    # paths (see reporting/scan_report_exporter.py).
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "directory" | "archive"

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")

    total_files_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Read-only integrity proof (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2
    # brief, §8 step 11): hash of the full source tree before and after
    # scanning. integrity_verified is False until both hashes are computed
    # and compared equal.
    source_hash_before: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_hash_after: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    integrity_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
