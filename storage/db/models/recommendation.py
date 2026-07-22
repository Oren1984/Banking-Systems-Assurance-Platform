from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from storage.db.base import Base

# Phase 3 — Recommendation model (BANKING_PLATFORM_INTEGRATION_PLAN.md §11:
# "currently inline text on Finding.recommendation; promoted to its own
# entity to support prioritization/status independent of the finding").
#
# `scan_id` and `control_id` are documented additions beyond §11's literal
# field list (`id, finding_id, text, priority, status`), required for the
# traceability the Phase 3 brief demands. `reviewed_by`/`reviewed_at`
# support the brief's "human review, approval, rejection, or annotation"
# requirement without building the full approval-workflow module —
# governance/approval_workflow.py remains Phase 5 scope, unbuilt.
#
# `priority` reuses models.enums.Severity's value space (critical/high/
# medium/low/info) rather than introducing a second, parallel severity-like
# enum — the Phase 1 rule against duplicate vocabulary applies here too.
# `source` is always RecommendationSource.DETERMINISTIC_TEMPLATE in
# Phase 3: there is no AI/LLM component yet, so every recommendation's
# text is produced by scoring/recommendations.py from a fixed template,
# never by a model. This field exists precisely so that never has to be
# taken on faith later — see BANKING_PLATFORM_INTEGRATION_PLAN.md §7 for
# where a real LLM-backed source would eventually be gated.


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    finding_id: Mapped[str] = mapped_column(String(36), ForeignKey("findings.id"), nullable=False, index=True)
    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("scans.id"), nullable=False, index=True)
    control_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("controls.id"), nullable=True, index=True)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)  # models.enums.Severity value
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")  # models.enums.RecommendationStatus
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="deterministic_template")  # models.enums.RecommendationSource

    reviewed_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
