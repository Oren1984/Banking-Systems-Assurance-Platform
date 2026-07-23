from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from storage.db.base import Base

# Phase 4 — Control Evaluation model (BANKING_PLATFORM_INTEGRATION_PLAN.md
# §13 Phase 4: "assessment/evaluators/*"). Closes an explicit gap Phase 3
# left open: Evidence/Recommendation rows only exist for controls a
# finding actually violated — there was previously no persisted record
# that a control which produced *no* findings in an evaluated domain was
# actually checked and passed, as opposed to never having been considered
# at all. This table makes that distinction a first-class, queryable fact
# for every (scan, domain, control) combination, not just an inference
# from the absence of an Evidence row.
#
# `control_id` is nullable for exactly one reason: a domain can be
# INSUFFICIENT_EVIDENCE before any specific control is even known to
# apply (the domain itself was never evaluated) — recording that as a
# domain-level row with control_id=None avoids fabricating a false
# per-control "pass" the same way scoring/engine.py avoids fabricating a
# false domain-level "clean" score.


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ControlEvaluation(Base):
    __tablename__ = "control_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("scans.id"), nullable=False, index=True)
    control_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("controls.id"), nullable=True, index=True)

    domain: Mapped[str] = mapped_column(String(64), nullable=False)  # core.domains.BankingDomain value
    status: Mapped[str] = mapped_column(String(24), nullable=False)  # models.enums.ControlEvaluationStatus

    # Which persisted Finding rows (if any) drove a GAP status for this
    # (domain, control) pair — empty for SATISFIED/INSUFFICIENT_EVIDENCE.
    finding_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
