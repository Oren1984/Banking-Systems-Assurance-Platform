from __future__ import annotations

from typing import List

from governance.secret_masker import find_secret_spans, mask_secrets
from models.enums import ConfidenceLevel, FindingCategory, FindingType, Severity
from scanners.content_reader import line_for_offset
from scanners.rules.base import BaseScanner, RawFinding

# Phase 2 scanner A — Secret and Credential Exposure
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2 brief, §6.A). Detection
# logic itself lives in governance/secret_masker.py (single source of
# truth — reused here, not duplicated) so that masking and detection can
# never drift apart.


class SecretExposureScanner(BaseScanner):
    scanner_id = "secret_exposure"
    scanner_version = "1.0.0"
    category = FindingCategory.SECRET_EXPOSURE

    def scan(self, relative_path: str, text: str) -> List[RawFinding]:
        spans = find_secret_spans(text)
        if not spans:
            return []

        # Deduplicate to one finding per line — several patterns can match
        # overlapping text on the same line (e.g. a connection string is
        # also caught by the generic quoted-assignment pattern).
        lines_seen: set[int] = set()
        findings: List[RawFinding] = []
        for start, end in sorted(spans):
            line_no = line_for_offset(text, start)
            if line_no in lines_seen:
                continue
            lines_seen.add(line_no)

            raw_snippet = text[start:end]
            masked_snippet = mask_secrets(raw_snippet)

            findings.append(
                RawFinding(
                    title="Likely secret or credential found in source",
                    finding_type=FindingType.OBSERVED_EVIDENCE,
                    category=self.category,
                    severity=Severity.HIGH,
                    confidence=ConfidenceLevel.MEDIUM,
                    line_start=line_no,
                    line_end=line_no,
                    evidence=raw_snippet,
                    masked_evidence=masked_snippet,
                    description=(
                        "A pattern matching a known secret/credential format "
                        "(API key, password assignment, token, private key "
                        "marker, or connection-string credential) was found "
                        "in this file."
                    ),
                    impact=(
                        "If this is a real, active credential committed to "
                        "source, anyone with read access to this file can "
                        "use it to impersonate the associated system or "
                        "account."
                    ),
                    recommended_action=(
                        "Rotate the credential if it is real, remove it "
                        "from source, and load it from an environment "
                        "variable or secret manager instead. This is "
                        "pattern-based detection; verify manually before "
                        "acting."
                    ),
                    rule_id="SECRET-001",
                )
            )
        return findings
