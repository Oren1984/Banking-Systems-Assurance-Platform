from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from models.enums import ConfidenceLevel, FindingCategory, FindingType, RemediationMode, Severity

# Phase 2 — Structured Finding Model (BANKING_PLATFORM_INTEGRATION_PLAN.md
# Phase 2 brief, §7) and scanner contract (§6).
#
# RawFinding is the in-memory output of a single scanner rule, before
# domain-mapping and persistence. scanners/scan_orchestrator.py normalizes
# a list of RawFinding into storage/db/models/finding.py::Finding rows.
# This mirrors the same deliberate split already used for FileInventoryItem
# (scanners/file_discovery.py) vs. its persisted counterpart — a pipeline
# dataclass has no DB/session dependency, so scanner rules stay unit
# testable with zero I/O beyond the text they are given.


@dataclass
class RawFinding:
    title: str
    finding_type: FindingType
    category: FindingCategory
    severity: Severity
    confidence: ConfidenceLevel
    line_start: int
    line_end: int
    evidence: str
    masked_evidence: str
    description: str
    impact: str
    recommended_action: str
    rule_id: str
    remediation_mode: RemediationMode = RemediationMode.ADVISORY_ONLY
    read_only_confirmation: bool = True
    metadata: dict = field(default_factory=dict)


class BaseScanner(ABC):
    """Common interface for all Phase 2 deterministic content scanners.

    A scanner never modifies, executes, or imports the content it is
    given — it only reads already-decoded text (see
    scanners/content_reader.py) and returns findings.
    """

    @property
    @abstractmethod
    def scanner_id(self) -> str:
        """Stable identifier, e.g. 'secret_exposure'."""

    @property
    @abstractmethod
    def scanner_version(self) -> str:
        """Bumped whenever detection logic changes materially."""

    @property
    @abstractmethod
    def category(self) -> FindingCategory:
        ...

    @abstractmethod
    def scan(self, relative_path: str, text: str) -> List[RawFinding]:
        """Scan already-read text and return zero or more findings."""
