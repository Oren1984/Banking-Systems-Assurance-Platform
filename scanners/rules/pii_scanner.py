from __future__ import annotations

import re
from typing import List

from models.enums import ConfidenceLevel, FindingCategory, FindingType, Severity
from scanners.content_reader import line_for_offset
from scanners.rules.base import BaseScanner, RawFinding

# Phase 2 scanner B — Sensitive Data and PII Exposure
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2 brief, §6.B).
#
# Pattern-based detection only. A pattern match here is evidence that
# text *resembles* PII/sensitive banking data — it is not a regulatory
# compliance determination, and this scanner never claims one. See
# description text below and docs/security_boundaries.md.

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s\-().]{7,15}\d")
# 16-digit card-like sequence, optionally grouped in 4s with spaces/dashes.
_CARD_LIKE_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
# US SSN-shaped (###-##-####) — used only as a representative national-ID pattern.
_SSN_SHAPED_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# ISO-8601-ish date of birth field, matched only near a dob-like keyword.
_DOB_FIELD_RE = re.compile(r"(?i)\b(date_of_birth|dob|birth_?date)\b\s*[:=]\s*['\"]?\d{4}-\d{2}-\d{2}")
_ACCOUNT_FIELD_RE = re.compile(r"(?i)\b(account_?number|acct_?no|iban)\b\s*[:=]\s*['\"]?[A-Z0-9]{6,}")

_KIND_TO_META = {
    "email": ("Email address pattern found", Severity.LOW),
    "phone": ("Phone number pattern found", Severity.LOW),
    "card_like": ("Card- or account-number-shaped digit sequence found", Severity.HIGH),
    "national_id_shaped": ("National-ID-shaped pattern found", Severity.HIGH),
    "date_of_birth": ("Date-of-birth field found", Severity.MEDIUM),
    "account_number_field": ("Account/IBAN-labeled field found", Severity.HIGH),
}


class PiiExposureScanner(BaseScanner):
    scanner_id = "pii_exposure"
    scanner_version = "1.0.0"
    category = FindingCategory.PII_EXPOSURE

    def scan(self, relative_path: str, text: str) -> List[RawFinding]:
        findings: List[RawFinding] = []
        findings += self._matches(text, _EMAIL_RE, "email")
        findings += self._matches(text, _PHONE_RE, "phone")
        findings += self._matches(text, _CARD_LIKE_RE, "card_like")
        findings += self._matches(text, _SSN_SHAPED_RE, "national_id_shaped")
        findings += self._matches(text, _DOB_FIELD_RE, "date_of_birth")
        findings += self._matches(text, _ACCOUNT_FIELD_RE, "account_number_field")
        return findings

    def _matches(self, text: str, pattern: re.Pattern, kind: str) -> List[RawFinding]:
        title, severity = _KIND_TO_META[kind]
        out: List[RawFinding] = []
        seen_lines: set[int] = set()
        for m in pattern.finditer(text):
            line_no = line_for_offset(text, m.start())
            if line_no in seen_lines:
                continue
            seen_lines.add(line_no)
            snippet = m.group(0)
            masked = _mask_middle(snippet)
            out.append(
                RawFinding(
                    title=title,
                    finding_type=FindingType.OBSERVED_EVIDENCE,
                    category=self.category,
                    severity=severity,
                    confidence=ConfidenceLevel.LOW,
                    line_start=line_no,
                    line_end=line_no,
                    evidence=snippet,
                    masked_evidence=masked,
                    description=(
                        f"A text pattern resembling {kind.replace('_', ' ')} "
                        "was found. This is a pattern match only — it does "
                        "not confirm real customer data is present, and it "
                        "is not a determination of regulatory compliance or "
                        "non-compliance."
                    ),
                    impact=(
                        "If this is real customer data present in source, "
                        "logs, or fixtures, it represents unnecessary "
                        "exposure of sensitive information outside "
                        "production data stores."
                    ),
                    recommended_action=(
                        "Confirm manually whether this is real or synthetic "
                        "data. If real, remove it from this location and "
                        "review how it was introduced."
                    ),
                    rule_id=f"PII-{kind.upper()}",
                    metadata={"pii_kind": kind},
                )
            )
        return out


def _mask_middle(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]
