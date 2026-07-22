from __future__ import annotations

# Adapted from RAG-Engineering-Lab/src/security/pii_redaction.py (see
# BANKING_PLATFORM_INTEGRATION_PLAN.md §3: "Refactor before reuse").
#
# NOT COMPLETE: this is regex-based pattern matching, not a comprehensive
# PII detection system. It will not catch every form of personally
# identifiable information (e.g. names, addresses, free-text account
# references). Document this residual risk in any deployment; do not present
# redacted output as guaranteed PII-free. See docs/security_boundaries.md.

import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s\-().]{7,15}\d")
# Long digit runs that resemble IDs, SSNs, or account numbers (7+ consecutive digits)
_ID_RE = re.compile(r"\b\d{7,}\b")

_EMAIL_PLACEHOLDER = "[EMAIL]"
_PHONE_PLACEHOLDER = "[PHONE]"
_ID_PLACEHOLDER = "[ID]"


def redact_pii(text: str) -> str:
    """
    Replace recognisable PII patterns with safe placeholders.

    Apply during ingestion (before chunking/storage) when PII redaction is
    enabled via configuration. Non-exhaustive by design (see module docstring).
    """
    text = _EMAIL_RE.sub(_EMAIL_PLACEHOLDER, text)
    text = _PHONE_RE.sub(_PHONE_PLACEHOLDER, text)
    text = _ID_RE.sub(_ID_PLACEHOLDER, text)
    return text
