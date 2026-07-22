from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from models.enums import EvidenceType

# Phase 3 — Evidence capture (BANKING_PLATFORM_INTEGRATION_PLAN.md §11).
# Pure function, no database — mirrors scoring/engine.py's design.
#
# `content` MUST be pre-masked text. This module never receives raw
# evidence — the caller (storage/db/repositories.py::ScoringRepository)
# only ever passes Finding.masked_evidence, which is guaranteed sanitized
# by construction (see storage/db/models/finding.py's module docstring).
# There is no code path in this module that could introduce raw content.


@dataclass
class FindingForEvidence:
    finding_id: str  # the persisted Finding row's real id
    masked_evidence: str
    source_relative_path: str
    line_start: int
    line_end: int
    control_id: Optional[str] = None


@dataclass
class EvidenceResult:
    finding_id: str
    control_id: Optional[str]
    evidence_type: str  # models.enums.EvidenceType value
    content: str  # sanitized only
    source_reference: str
    retrieved_via: Optional[str] = None  # future RAG chunk_id; always None in Phase 3


def build_evidence(findings: List[FindingForEvidence]) -> List[EvidenceResult]:
    """One Evidence row per Finding, sourced entirely from the scan itself
    (evidence_type=SCAN_RESULT) — Phase 3 has no other evidence source yet
    (no RAG-retrieved chunks, no manually-uploaded documents)."""
    return [_evidence_for(f) for f in findings]


def _evidence_for(finding: FindingForEvidence) -> EvidenceResult:
    if finding.line_end and finding.line_end != finding.line_start:
        location = f"{finding.source_relative_path}:{finding.line_start}-{finding.line_end}"
    else:
        location = f"{finding.source_relative_path}:{finding.line_start}"
    return EvidenceResult(
        finding_id=finding.finding_id,
        control_id=finding.control_id,
        evidence_type=EvidenceType.SCAN_RESULT.value,
        content=finding.masked_evidence,
        source_reference=location,
        retrieved_via=None,
    )
