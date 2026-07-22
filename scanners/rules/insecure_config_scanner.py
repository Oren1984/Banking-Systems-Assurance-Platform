from __future__ import annotations

import re
from typing import List

from models.enums import ConfidenceLevel, FindingCategory, FindingType, Severity
from scanners.content_reader import line_for_offset
from scanners.rules.base import BaseScanner, RawFinding

# Phase 2 scanner G — Insecure Configuration
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2 brief, §6.G).

_PATTERNS: list[tuple[re.Pattern, str, Severity, str]] = [
    (
        re.compile(r"(?i)\bDEBUG\s*[:=]\s*(true|1|on)\b"),
        "Debug mode appears enabled",
        Severity.MEDIUM,
        "CFG-001",
    ),
    (
        re.compile(
            r"(?i)\b(verify|ssl_verify|tls_verify|verify_ssl|verify_certs?)\s*[:=]\s*(false|0|off)\b|"
            r"\brequests\.\w+\([^)]*verify\s*=\s*False"
        ),
        "TLS/SSL certificate verification appears disabled",
        Severity.HIGH,
        "CFG-002",
    ),
    (
        re.compile(r"(?i)\b(auth(?:entication)?_enabled)\s*[:=]\s*(false|0|off)\b"),
        "Authentication appears disabled in configuration",
        Severity.CRITICAL,
        "CFG-003",
    ),
    (
        re.compile(r"(?i)\b(encrypt(?:ion)?_enabled)\s*[:=]\s*(false|0|off)\b"),
        "Encryption appears disabled in configuration",
        Severity.HIGH,
        "CFG-004",
    ),
    (
        re.compile(r"(?i)Access-Control-Allow-Origin\s*[:=]\s*['\"]?\*"),
        "Permissive CORS policy (Access-Control-Allow-Origin: *)",
        Severity.MEDIUM,
        "CFG-005",
    ),
    (
        re.compile(r"(?i)\bhost\s*[:=]\s*['\"]?0\.0\.0\.0\b"),
        "Service binds to all network interfaces (0.0.0.0)",
        Severity.MEDIUM,
        "CFG-006",
    ),
    (
        re.compile(r"(?i)\b(admin|root|test|guest|password)\s*[:=]\s*['\"]?(admin|password|changeme|123456|root)['\"]?\b"),
        "Default or well-known weak credential pattern found",
        Severity.HIGH,
        "CFG-007",
    ),
    (
        re.compile(r"(?i)\b(display_errors|debug_errors|show_stacktrace)\s*[:=]\s*(true|1|on)\b"),
        "Verbose error/stack-trace exposure appears enabled",
        Severity.LOW,
        "CFG-008",
    ),
    (
        re.compile(r"(?i)set-cookie[^\n]*(?<!secure)\s*$", re.MULTILINE),
        "Cookie set without a Secure flag",
        Severity.LOW,
        "CFG-009",
    ),
]


class InsecureConfigurationScanner(BaseScanner):
    scanner_id = "insecure_configuration"
    scanner_version = "1.0.0"
    category = FindingCategory.INSECURE_CONFIGURATION

    def scan(self, relative_path: str, text: str) -> List[RawFinding]:
        findings: List[RawFinding] = []
        for pattern, title, severity, rule_id in _PATTERNS:
            for m in pattern.finditer(text):
                line_no = line_for_offset(text, m.start())
                snippet = m.group(0).strip()
                findings.append(
                    RawFinding(
                        title=title,
                        finding_type=FindingType.OBSERVED_EVIDENCE,
                        category=self.category,
                        severity=severity,
                        confidence=ConfidenceLevel.MEDIUM,
                        line_start=line_no,
                        line_end=line_no,
                        evidence=snippet,
                        masked_evidence=snippet,
                        description=f"{title} — matched directly in configuration/source text.",
                        impact="Insecure configuration defaults are a common root cause of otherwise-preventable incidents.",
                        recommended_action="Confirm this setting is intentional for this environment; harden the default if not.",
                        rule_id=rule_id,
                    )
                )
        return findings
