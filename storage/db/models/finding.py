from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from storage.db.base import Base

# Phase 2 — Structured Finding Model, persisted form
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2 brief, §7). Adapted from
# the shape of ai-project-control-tower/app/db/models/finding.py
# (`category`, `severity`, `title`, `description`, `evidence`,
# `recommendation`, `file_path`, `line_number`) and extended with
# `confidence`, `banking_domains`, `finding_type`, `remediation_mode`, and
# `read_only_confirmation` — none of which existed in the source schema
# (see BANKING_PLATFORM_INTEGRATION_PLAN.md §11 for why `confidence` in
# particular was flagged as the platform's most important structural gap).
#
# DELIBERATE DEVIATION FROM A LITERAL FIELD-FOR-FIELD MAPPING: the brief's
# field list includes both `evidence` and `masked_evidence`. This table
# stores ONLY `masked_evidence` — there is no raw-`evidence` column. Raw,
# unmasked evidence exists solely in scanners/rules/base.py::RawFinding,
# in memory, for exactly as long as it takes
# scanners/scan_orchestrator.py to compute the masked version; it is never
# written to the database, never logged, and never displayed. This
# satisfies the Phase 2 brief's own "Mandatory Security Requirements":
# "Secret values are masked" and "Logs are sanitized" — applied to
# persistence as well as to logs and the UI, not just to those two
# surfaces. See docs/security_boundaries.md.


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("scans.id"), nullable=False, index=True)

    scanner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scanner_version: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(32), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    finding_type: Mapped[str] = mapped_column(String(20), nullable=False)  # models.enums.FindingType
    category: Mapped[str] = mapped_column(String(40), nullable=False)  # models.enums.FindingCategory
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # models.enums.Severity
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)  # models.enums.ConfidenceLevel

    banking_domains: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    source_relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # See module docstring: masked only, by design. No `evidence` column exists.
    masked_evidence: Mapped[str] = mapped_column(Text, nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)

    remediation_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="advisory_only")
    read_only_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Phase 3 addition (BANKING_PLATFORM_INTEGRATION_PLAN.md §11's Finding
    # field list: "human_review_status (NEW: pending|approved|rejected|
    # overridden), reviewed_by, reviewed_at" — not added in Phase 2,
    # added now via alembic/versions/0002_phase3_controls_evidence_scoring.py.
    # Defaults to HumanReviewStatus.PENDING; nothing in Phase 3 sets this
    # to anything else automatically — only a human action would, and no
    # approval-workflow UI exists yet (Phase 5 territory).
    human_review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
