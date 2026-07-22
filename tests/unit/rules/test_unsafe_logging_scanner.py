from __future__ import annotations

from models.enums import FindingType
from scanners.rules.unsafe_logging_scanner import UnsafeLoggingScanner


def test_detects_password_in_log_call():
    scanner = UnsafeLoggingScanner()
    findings = scanner.scan("app.py", 'logger.info(f"login password={password}")')
    assert len(findings) == 1
    assert findings[0].finding_type == FindingType.INFERENCE


def test_detects_card_number_in_print_call():
    scanner = UnsafeLoggingScanner()
    findings = scanner.scan("app.py", 'print("card_number:", card_number)')
    assert len(findings) == 1


def test_no_finding_for_log_call_without_sensitive_keyword():
    scanner = UnsafeLoggingScanner()
    findings = scanner.scan("app.py", 'logger.info("scan completed successfully")')
    assert findings == []


def test_no_finding_for_sensitive_keyword_without_log_call():
    scanner = UnsafeLoggingScanner()
    findings = scanner.scan("app.py", "password = get_password()")
    assert findings == []


def test_matches_on_keyword_co_occurrence_even_in_a_message_string():
    # Deliberately broad/conservative heuristic: any logging call whose
    # arguments mention a sensitive keyword is flagged, even if the
    # keyword only appears in message text rather than a variable being
    # logged — see the module docstring for why this is a co-occurrence
    # signal, not proof, and is capped at LOW confidence / INFERENCE.
    scanner = UnsafeLoggingScanner()
    findings = scanner.scan("app.py", 'logger.info("secret value is here")')
    assert len(findings) == 1


def test_masked_evidence_redacts_quoted_string_values():
    scanner = UnsafeLoggingScanner()
    findings = scanner.scan("app.py", 'logger.info("secret", token_value)')
    assert len(findings) == 1
    assert '"secret"' not in findings[0].masked_evidence
    assert "[REDACTED]" in findings[0].masked_evidence
