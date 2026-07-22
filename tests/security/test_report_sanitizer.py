from __future__ import annotations

from governance.report_sanitizer import sanitize_report


def test_strips_autofix_heading():
    content = "## Auto-Fix Plan\nRun this command to fix it automatically."
    result = sanitize_report(content)
    assert "Auto-Fix Plan" not in result
    assert "[REMOVED]" in result


def test_strips_diff_code_block():
    content = "Here is a patch:\n```diff\n-old line\n+new line\n```\nDone."
    result = sanitize_report(content)
    assert "```diff" not in result
    assert "[REMOVED]" in result


def test_masks_secrets_within_report_content():
    content = "Evidence: API_KEY=abcd1234efgh5678"
    result = sanitize_report(content)
    assert "abcd1234efgh5678" not in result
    assert "API_KEY=[REDACTED]" in result


def test_leaves_ordinary_finding_text_untouched():
    content = "Finding: missing TLS configuration on the internal API gateway."
    assert sanitize_report(content) == content
