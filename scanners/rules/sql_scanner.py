from __future__ import annotations

import re
from typing import List

from models.enums import ConfidenceLevel, FindingCategory, FindingType, Severity
from scanners.content_reader import line_for_offset
from scanners.rules.base import BaseScanner, RawFinding

# Phase 2 scanner F — Unsafe SQL Indicators
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2 brief, §6.F). Detection
# only — this scanner never executes SQL, and no dependency it uses can
# execute SQL (plain regex against already-read text).

_STRING_CONCAT_SQL_RE = re.compile(
    r"(?i)\b(SELECT|INSERT|UPDATE|DELETE)\b[^;\n]{0,200}['\"]\s*\+\s*\w+|"
    r"\b(SELECT|INSERT|UPDATE|DELETE)\b[^;\n]{0,200}\+\s*['\"]"
)
_FSTRING_SQL_RE = re.compile(
    r"(?i)f['\"][^'\"\n]*\b(SELECT|INSERT|UPDATE|DELETE)\b[^'\"\n]*\{[^}]+\}"
)
_PERCENT_FORMAT_SQL_RE = re.compile(
    r"(?i)['\"][^'\"\n]*\b(SELECT|INSERT|UPDATE|DELETE)\b[^'\"\n]*['\"]\s*%\s*"
)
_DESTRUCTIVE_SQL_RE = re.compile(
    r"(?im)^\s*(DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE\s+TABLE)\b"
)
_PLAINTEXT_DB_CRED_RE = re.compile(
    r"(?i)\b(DB_PASSWORD|DATABASE_PASSWORD|SA_PASSWORD)\s*=\s*['\"]?[^'\"\s]{3,}"
)


class UnsafeSqlScanner(BaseScanner):
    scanner_id = "unsafe_sql"
    scanner_version = "1.0.0"
    category = FindingCategory.UNSAFE_SQL

    def scan(self, relative_path: str, text: str) -> List[RawFinding]:
        findings: List[RawFinding] = []
        findings += self._match(
            text, _STRING_CONCAT_SQL_RE, "SQL-001", Severity.HIGH,
            "String-concatenated SQL query",
            "SQL built via string concatenation with a variable was found — a classic SQL-injection pattern.",
        )
        findings += self._match(
            text, _FSTRING_SQL_RE, "SQL-002", Severity.HIGH,
            "Dynamic (f-string) SQL query",
            "SQL built via an f-string/template with interpolated values was found.",
        )
        findings += self._match(
            text, _PERCENT_FORMAT_SQL_RE, "SQL-003", Severity.MEDIUM,
            "SQL built via %-style string formatting",
            "SQL built via %-style string formatting was found — verify parameterized queries are used instead.",
        )
        findings += self._match(
            text, _DESTRUCTIVE_SQL_RE, "SQL-004", Severity.HIGH,
            "Destructive SQL statement found",
            "A DROP TABLE/DROP DATABASE/TRUNCATE TABLE statement was found in this file.",
        )
        findings += self._match(
            text, _PLAINTEXT_DB_CRED_RE, "SQL-005", Severity.HIGH,
            "Plaintext database credential in configuration",
            "A database credential appears to be set in plaintext.",
        )
        return findings

    def _match(
        self,
        text: str,
        pattern: re.Pattern,
        rule_id: str,
        severity: Severity,
        title: str,
        description: str,
    ) -> List[RawFinding]:
        out: List[RawFinding] = []
        for m in pattern.finditer(text):
            line_no = line_for_offset(text, m.start())
            snippet = m.group(0).strip()
            out.append(
                RawFinding(
                    title=title,
                    finding_type=FindingType.OBSERVED_EVIDENCE,
                    category=self.category,
                    severity=severity,
                    confidence=ConfidenceLevel.MEDIUM,
                    line_start=line_no,
                    line_end=line_no,
                    evidence=snippet,
                    masked_evidence=snippet if rule_id != "SQL-005" else _mask_cred(snippet),
                    description=description + " No SQL was executed by this scan — detection is text-pattern-based only.",
                    impact="Unsafe SQL construction can allow injection attacks; destructive statements can cause irreversible data loss if run unintentionally.",
                    recommended_action="Use parameterized queries / an ORM query builder instead of string interpolation; review destructive statements for guardrails (backups, confirmation, restricted execution).",
                    rule_id=rule_id,
                )
            )
        return out


def _mask_cred(snippet: str) -> str:
    return re.sub(r"=\s*['\"]?[^'\"\s]{3,}", "=[REDACTED]", snippet)
