from __future__ import annotations

import re
from typing import List

from models.enums import ConfidenceLevel, FindingCategory, FindingType, Severity
from scanners.content_reader import line_for_offset
from scanners.rules.base import BaseScanner, RawFinding

# Phase 2 scanner E — Broad Permission Indicators
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2 brief, §6.E).

_PATTERNS: list[tuple[re.Pattern, str, Severity, str]] = [
    (
        # Matches both JSON-style ("Action": "*") and HCL-style
        # ("Action" = "*") IAM policy statements.
        re.compile(r'["\']Action["\']\s*[:=]\s*["\']\*["\']'),
        "IAM policy grants wildcard Action (\"*\")",
        Severity.CRITICAL,
        "PERM-001",
    ),
    (
        re.compile(r'["\']Resource["\']\s*[:=]\s*["\']\*["\']'),
        "IAM policy grants access to wildcard Resource (\"*\")",
        Severity.HIGH,
        "PERM-002",
    ),
    (
        re.compile(r"(?i)\brole\s*[:=]\s*['\"]?(admin|administrator|superuser|root)\b"),
        "Administrator-level role assignment found",
        Severity.HIGH,
        "PERM-003",
    ),
    (
        re.compile(r"(?i)\b(is_)?public\s*[:=]\s*(true|1)\b"),
        "Public access flag set to true",
        Severity.HIGH,
        "PERM-004",
    ),
    (
        re.compile(r"(?i)\ballow[_-]?anonymous\s*[:=]\s*(true|1)\b"),
        "Anonymous access explicitly allowed",
        Severity.HIGH,
        "PERM-005",
    ),
    (
        re.compile(r"(?i)\bchmod\s+777\b"),
        "World-writable file permission (chmod 777) found",
        Severity.MEDIUM,
        "PERM-006",
    ),
]


class BroadPermissionScanner(BaseScanner):
    scanner_id = "broad_permissions"
    scanner_version = "1.0.0"
    category = FindingCategory.BROAD_PERMISSIONS

    def scan(self, relative_path: str, text: str) -> List[RawFinding]:
        findings: List[RawFinding] = []
        for pattern, title, severity, rule_id in _PATTERNS:
            for m in pattern.finditer(text):
                line_no = line_for_offset(text, m.start())
                findings.append(
                    RawFinding(
                        title=title,
                        finding_type=FindingType.OBSERVED_EVIDENCE,
                        category=self.category,
                        severity=severity,
                        confidence=ConfidenceLevel.MEDIUM,
                        line_start=line_no,
                        line_end=line_no,
                        evidence=m.group(0),
                        masked_evidence=m.group(0),
                        description=f"{title} — a broad-access pattern was matched directly in this file.",
                        impact="Overly broad permissions increase blast radius if this credential, role, or resource is compromised.",
                        recommended_action="Review whether this scope is actually required; apply least-privilege scoping if not.",
                        rule_id=rule_id,
                    )
                )
        return findings
