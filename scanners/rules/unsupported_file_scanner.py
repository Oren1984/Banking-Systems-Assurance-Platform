from __future__ import annotations

from typing import List

from models.enums import ConfidenceLevel, FindingCategory, FindingType, Severity, SkipReason
from scanners.file_classifier import looks_sensitive_by_name
from scanners.file_discovery import SkippedFile
from scanners.rules.base import RawFinding

# Phase 2 scanner H — Unsupported or Unclassified Sensitive Files
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2 brief, §6.H).
#
# Unlike the other seven scanners, this one operates on the *skipped-file*
# list from scanners/file_discovery.py, not on file content (there is no
# content — these files were never read). Deliberately conservative: most
# skipped files never become findings, only the ones with a sensitive-
# looking name and a reason worth a human's attention (see
# scanners/scan_orchestrator.py for how the full skip summary is still
# reported regardless of whether a finding is raised).

_REASON_SEVERITY: dict[SkipReason, Severity] = {
    SkipReason.UNSUPPORTED_TYPE: Severity.MEDIUM,
    SkipReason.SIZE_LIMIT: Severity.LOW,
    SkipReason.TOTAL_SIZE_LIMIT: Severity.LOW,
    SkipReason.SYMLINK: Severity.LOW,
    SkipReason.UNREADABLE: Severity.INFO,
    SkipReason.BINARY_UNSUPPORTED: Severity.LOW,
}

_RULE_ID = "SKIP-001"
_SCANNER_ID = "unsupported_sensitive_file"
_SCANNER_VERSION = "1.0.0"
_CATEGORY = FindingCategory.UNSUPPORTED_SENSITIVE_FILE


def scan_skipped_files(skipped: List[SkippedFile]) -> List[RawFinding]:
    findings: List[RawFinding] = []
    for item in skipped:
        if not looks_sensitive_by_name(item.relative_path):
            continue  # not every skipped file is a finding — only sensitive-looking ones
        severity = _REASON_SEVERITY.get(item.reason, Severity.LOW)
        findings.append(
            RawFinding(
                title="Sensitive-looking file was not scanned",
                finding_type=FindingType.INFERENCE,
                category=_CATEGORY,
                severity=severity,
                confidence=ConfidenceLevel.LOW,
                line_start=0,
                line_end=0,
                evidence=item.relative_path,
                masked_evidence=item.relative_path,
                description=(
                    f"'{item.relative_path}' has a name suggesting it may contain "
                    f"sensitive material (e.g. secret/credential/key), but it was "
                    f"skipped during discovery ({item.reason.value}: {item.detail}) "
                    "and its content was never read or evaluated."
                ),
                impact=(
                    "This file's contents were not assessed by any Phase 2 scanner. "
                    "It may or may not contain a real issue — this finding exists so "
                    "a human can decide whether to review it directly."
                ),
                recommended_action=(
                    "Review this file manually, or adjust scan limits/allowlists if "
                    "it should be included in a future scan."
                ),
                rule_id=_RULE_ID,
                metadata={"skip_reason": item.reason.value},
            )
        )
    return findings


scanner_id = _SCANNER_ID
scanner_version = _SCANNER_VERSION
category = _CATEGORY
