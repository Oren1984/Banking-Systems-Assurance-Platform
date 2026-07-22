from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from storage.db.base import Base

# Phase 3 — Score model (BANKING_PLATFORM_INTEGRATION_PLAN.md §11, adapted
# from ai-project-control-tower/app/audit/models.py::AuditScores). This is
# the table that must deliver the phase's core fix: a domain with zero
# findings because it was never evaluated resolves to
# DecisionCategory.INSUFFICIENT_EVIDENCE, never a false "clean" score —
# see scoring/engine.py for the algorithm and
# tests/unit/test_scoring_engine.py for the boundary-case tests.
#
# DEVIATION FROM §11's LITERAL FIELD NAME: uses `scan_id`, not
# `assessment_id`. No `Assessment`/`AssessmentTarget` entity exists yet
# (that remains Phase 4+ scope per BANKING_PLATFORM_INTEGRATION_PLAN.md
# §13's Phase 3 "Included" list, which does not list assessment_target.py).
# Introducing a foreign key to a table that doesn't exist would be worse
# than using the real, already-persisted `scans.id` this data actually
# comes from. When a genuine Assessment entity is built, this column can
# be renamed/supplemented in that phase's own migration.
#
# `files_evaluated` and `findings_count` are documented additions beyond
# §11's literal field list, added for traceability and to make the
# evidence-completeness determination auditable from the row itself
# rather than requiring a join back to raw scan data.


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("scans.id"), nullable=False, index=True)

    domain: Mapped[str] = mapped_column(String(64), nullable=False)  # core.domains.BankingDomain value

    raw_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # None when insufficient_evidence
    weighted_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    confidence_level: Mapped[str] = mapped_column(String(16), nullable=False)  # models.enums.ConfidenceLevel
    evidence_completeness: Mapped[str] = mapped_column(String(16), nullable=False)  # models.enums.EvidenceCompleteness
    decision_category: Mapped[str] = mapped_column(String(32), nullable=False)  # models.enums.DecisionCategory

    files_evaluated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Self-referential FK for human overrides (§11). Nothing sets this in
    # Phase 3 — no override UI/workflow is built yet (Phase 5 territory) —
    # but the column exists so a future override doesn't require another
    # migration.
    override_of: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("scores.id"), nullable=True)
