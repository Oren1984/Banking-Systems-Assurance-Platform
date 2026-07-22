from __future__ import annotations

from models.enums import SkipReason
from scanners.file_discovery import SkippedFile
from scanners.rules.unsupported_file_scanner import scan_skipped_files


def test_sensitive_looking_unsupported_file_produces_a_finding():
    skipped = [SkippedFile("config/db_credentials.secrets", SkipReason.UNSUPPORTED_TYPE, "unsupported extension")]
    findings = scan_skipped_files(skipped)
    assert len(findings) == 1
    assert findings[0].metadata["skip_reason"] == "unsupported_type"


def test_ordinary_unsupported_file_produces_no_finding():
    skipped = [SkippedFile("assets/logo.png", SkipReason.UNSUPPORTED_TYPE, "unsupported extension")]
    findings = scan_skipped_files(skipped)
    assert findings == []


def test_not_every_skipped_file_becomes_a_finding():
    skipped = [
        SkippedFile("assets/logo.png", SkipReason.UNSUPPORTED_TYPE, "x"),
        SkippedFile("vendor/lib.min.js", SkipReason.SIZE_LIMIT, "x"),
        SkippedFile("data/huge_export.csv", SkipReason.TOTAL_SIZE_LIMIT, "x"),
    ]
    findings = scan_skipped_files(skipped)
    assert findings == []


def test_severity_reflects_skip_reason_not_always_high():
    skipped = [SkippedFile("secret_key.bin", SkipReason.UNREADABLE, "permission denied")]
    findings = scan_skipped_files(skipped)
    assert len(findings) == 1
    assert findings[0].severity.value == "info"
