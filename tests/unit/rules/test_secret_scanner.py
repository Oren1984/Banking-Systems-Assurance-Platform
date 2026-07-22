from __future__ import annotations

from models.enums import ConfidenceLevel, FindingCategory
from scanners.rules.secret_scanner import SecretExposureScanner


def test_detects_env_style_secret_and_masks_evidence():
    scanner = SecretExposureScanner()
    findings = scanner.scan("config/.env", 'PASSWORD="hunter2value"')
    assert len(findings) == 1
    f = findings[0]
    assert f.category == FindingCategory.SECRET_EXPOSURE
    assert "hunter2value" not in f.masked_evidence
    assert f.confidence == ConfidenceLevel.MEDIUM


def test_detects_quoted_assignment_secret_in_code():
    scanner = SecretExposureScanner()
    findings = scanner.scan("app.py", 'db_password = "SuperSecretValue123"')
    assert len(findings) == 1
    assert "SuperSecretValue123" not in findings[0].masked_evidence


def test_detects_connection_string_credential():
    scanner = SecretExposureScanner()
    findings = scanner.scan(
        "settings.py", 'DATABASE_URL = "postgresql://user:hunter2@localhost:5432/db"'
    )
    assert len(findings) == 1
    assert "hunter2" not in findings[0].masked_evidence


def test_no_findings_for_clean_text():
    scanner = SecretExposureScanner()
    findings = scanner.scan("app.py", "def add(a, b):\n    return a + b\n")
    assert findings == []


def test_one_finding_per_line_even_with_overlapping_patterns():
    scanner = SecretExposureScanner()
    text = 'api_key = "sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"'
    findings = scanner.scan("app.py", text)
    line_numbers = [f.line_start for f in findings]
    assert len(line_numbers) == len(set(line_numbers))


def test_evidence_never_contains_raw_secret_in_masked_field():
    scanner = SecretExposureScanner()
    secret_value = "TopSecretPassword987"
    findings = scanner.scan("app.py", f'password = "{secret_value}"')
    for f in findings:
        assert secret_value not in f.masked_evidence
