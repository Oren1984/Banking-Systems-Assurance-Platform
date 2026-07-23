from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

# Phase 4 — Retention foundations (BANKING_PLATFORM_INTEGRATION_PLAN.md
# §13 Phase 4: "retention foundations"). Deliberately identify-only: this
# module never deletes anything, and no caller in this codebase invokes a
# delete path from its output. "Foundations" means exactly that — a typed
# config field (core/config.py::Settings.data_retention_days, default
# None = retention disabled) and a pure function that can name which of
# the platform's own persisted scans are old enough to be considered,
# nothing more.
#
# WHAT THIS DELIBERATELY DOES NOT DECIDE (left for a later phase, per the
# plan's own "foundations" — not "policy" — wording): whether eligible
# scans are archived before deletion, who must approve an actual deletion,
# whether Score/Evidence/Recommendation/AuditEvent rows referencing a
# retired scan are deleted, retained, or anonymized, and whether deletion
# ever runs automatically versus only on an explicit human-triggered
# action. Implementing any of that now would be exactly the kind of
# "unnecessary infrastructure" this phase's brief says not to add.
#
# NOTE ON SCOPE: this concerns the platform's *own* persisted assessment
# data (scans, findings, scores, ...) — never the scanned target system,
# which this platform never writes to or deletes from under any
# circumstance (see docs/security_boundaries.md).


@dataclass
class ScanRetentionSnapshot:
    """The minimal shape this module needs from a persisted Scan row —
    deliberately not the ORM row itself, matching every other pure
    assessment/governance module's design."""

    scan_id: str
    created_at: datetime


@dataclass
class RetentionCandidate:
    scan_id: str
    created_at: datetime
    age_days: int


def find_scans_eligible_for_retention(
    scans: List[ScanRetentionSnapshot],
    retention_days: Optional[int],
    as_of: datetime,
) -> List[RetentionCandidate]:
    """Identify (never delete) scans older than `retention_days`.
    Returns an empty list — not an error — when `retention_days` is
    `None`, matching `Settings.data_retention_days`'s safe default
    (retention identification disabled unless explicitly configured)."""
    if retention_days is None:
        return []
    if retention_days < 0:
        raise ValueError("retention_days must not be negative")

    candidates: List[RetentionCandidate] = []
    for scan in scans:
        age_days = (as_of - scan.created_at).days
        if age_days >= retention_days:
            candidates.append(
                RetentionCandidate(scan_id=scan.scan_id, created_at=scan.created_at, age_days=age_days)
            )
    return candidates


__all__ = ["ScanRetentionSnapshot", "RetentionCandidate", "find_scans_eligible_for_retention"]
