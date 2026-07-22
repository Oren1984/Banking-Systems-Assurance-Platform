from __future__ import annotations

import re
from typing import List

from models.enums import ConfidenceLevel, FindingCategory, FindingType, Severity
from scanners.content_reader import line_for_offset
from scanners.rules.base import BaseScanner, RawFinding

# Phase 2 scanner C — Unsafe Logging
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2 brief, §6.C).
#
# Looks for a logging call (log.*/logger.*/console.log/print/System.out)
# whose argument text mentions a sensitive field name. This is a
# co-occurrence heuristic, not proof the sensitive value itself is logged —
# confidence is capped at LOW/MEDIUM accordingly.

_LOG_CALL_RE = re.compile(
    r"(?im)^.*\b(?:log(?:ger)?\.\w+|console\.log|print|System\.out\.\w+)\s*\("
    r"[^\n]*\b(password|passwd|token|secret|api[_-]?key|ssn|"
    r"account_?number|card_?number|cvv|auth(?:orization)?[_-]?header|"
    r"request_?body|response_?body)\b[^\n]*\)"
)

_SEVERITY_BY_KEYWORD = {
    "password": Severity.HIGH,
    "passwd": Severity.HIGH,
    "token": Severity.HIGH,
    "secret": Severity.HIGH,
    "cvv": Severity.CRITICAL,
    "card_number": Severity.CRITICAL,
    "cardnumber": Severity.CRITICAL,
    "ssn": Severity.HIGH,
    "account_number": Severity.HIGH,
    "accountnumber": Severity.HIGH,
    "auth_header": Severity.MEDIUM,
    "authorization_header": Severity.MEDIUM,
    "request_body": Severity.MEDIUM,
    "response_body": Severity.MEDIUM,
    "api_key": Severity.HIGH,
    "apikey": Severity.HIGH,
}


class UnsafeLoggingScanner(BaseScanner):
    scanner_id = "unsafe_logging"
    scanner_version = "1.0.0"
    category = FindingCategory.UNSAFE_LOGGING

    def scan(self, relative_path: str, text: str) -> List[RawFinding]:
        findings: List[RawFinding] = []
        for m in _LOG_CALL_RE.finditer(text):
            keyword = m.group(1).lower().replace("-", "_")
            severity = _SEVERITY_BY_KEYWORD.get(keyword, Severity.MEDIUM)
            line_no = line_for_offset(text, m.start())
            snippet = m.group(0).strip()
            findings.append(
                RawFinding(
                    title="Logging call may include sensitive data",
                    finding_type=FindingType.INFERENCE,
                    category=self.category,
                    severity=severity,
                    confidence=ConfidenceLevel.LOW,
                    line_start=line_no,
                    line_end=line_no,
                    evidence=snippet,
                    masked_evidence=_mask_snippet(snippet),
                    description=(
                        f"A logging call on this line also mentions "
                        f"'{keyword}', which suggests (but does not "
                        "confirm) that sensitive data may be written to "
                        "logs."
                    ),
                    impact=(
                        "Logs are often retained longer and accessed more "
                        "broadly than the systems that generate them; "
                        "sensitive values in logs increase exposure."
                    ),
                    recommended_action=(
                        "Review this log statement manually. If it logs a "
                        "sensitive value directly, mask or remove it from "
                        "the log line."
                    ),
                    rule_id="LOG-001",
                    metadata={"matched_keyword": keyword},
                )
            )
        return findings


def _mask_snippet(snippet: str) -> str:
    return re.sub(r"['\"][^'\"]{4,}['\"]", "'[REDACTED]'", snippet)
