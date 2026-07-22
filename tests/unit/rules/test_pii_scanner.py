from __future__ import annotations

from scanners.rules.pii_scanner import PiiExposureScanner


def test_detects_email():
    scanner = PiiExposureScanner()
    findings = scanner.scan("app.py", "contact = 'jane.doe@example.com'")
    assert any(f.rule_id == "PII-EMAIL" for f in findings)


def test_detects_card_like_sequence():
    scanner = PiiExposureScanner()
    findings = scanner.scan("app.py", "card = '4111111111111111'")
    assert any(f.rule_id == "PII-CARD_LIKE" for f in findings)


def test_detects_national_id_shaped_pattern():
    scanner = PiiExposureScanner()
    findings = scanner.scan("app.py", "national_id_shaped = '123-45-6789'")
    assert any(f.rule_id == "PII-NATIONAL_ID_SHAPED" for f in findings)


def test_detects_date_of_birth_field():
    scanner = PiiExposureScanner()
    findings = scanner.scan("app.py", 'date_of_birth: "1990-01-01"')
    assert any(f.rule_id == "PII-DATE_OF_BIRTH" for f in findings)


def test_detects_account_number_field():
    scanner = PiiExposureScanner()
    findings = scanner.scan("app.py", 'account_number = "IBAN00FAKE0000"')
    assert any(f.rule_id == "PII-ACCOUNT_NUMBER_FIELD" for f in findings)


def test_no_findings_for_clean_text():
    scanner = PiiExposureScanner()
    findings = scanner.scan("app.py", "def add(a, b):\n    return a + b\n")
    assert findings == []


def test_never_claims_regulatory_non_compliance():
    scanner = PiiExposureScanner()
    findings = scanner.scan("app.py", "email = 'a@b.com'")
    for f in findings:
        assert "compliance" not in f.description.lower() or "not a" in f.description.lower()


def test_evidence_is_masked_in_middle():
    scanner = PiiExposureScanner()
    findings = scanner.scan("app.py", "email = 'jane.doe@example.com'")
    email_finding = next(f for f in findings if f.rule_id == "PII-EMAIL")
    assert "*" in email_finding.masked_evidence
