from __future__ import annotations

from governance.pii_redaction import redact_pii


def test_redacts_email():
    result = redact_pii("Contact: jane.doe@example.com for details.")
    assert "jane.doe@example.com" not in result
    assert "[EMAIL]" in result


def test_redacts_phone_number():
    result = redact_pii("Call +1 (555) 123-4567 for support.")
    assert "[PHONE]" in result


def test_redacts_long_digit_runs():
    # 7-8 digit runs are below the phone pattern's 9-digit minimum, so they
    # hit the ID pattern specifically rather than being caught as a phone
    # number first (both patterns are regex-based and applied in sequence;
    # this reflects the ported behavior, not an assumption).
    result = redact_pii("Account number: 1234567")
    assert "1234567" not in result
    assert "[ID]" in result


def test_leaves_ordinary_text_untouched():
    text = "The scan completed successfully with no issues found."
    assert redact_pii(text) == text


def test_documented_as_non_exhaustive():
    # This is a documentation/behavior contract test, not a completeness
    # claim: names and addresses are NOT redacted by this module.
    result = redact_pii("Customer name: Jane Doe, no digits or email here.")
    assert "Jane Doe" in result
