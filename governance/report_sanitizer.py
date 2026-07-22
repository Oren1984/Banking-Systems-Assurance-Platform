from __future__ import annotations

# Reused as-is from ai-project-control-tower/app/reports/report_sanitizer.py
# (see BANKING_PLATFORM_INTEGRATION_PLAN.md §3). This is the code-level
# enforcement of the platform's "recommend, never auto-fix" hard requirement
# (Part D: "Do not generate patches or auto-remediation against assessed
# systems") — it strips auto-fix/patch-plan content in addition to masking
# secrets, so it must run on every report before it reaches a human or an
# external provider (see providers/base.py).

import re

from governance.secret_masker import mask_secrets

_AUTOFIX_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?mi)^#{1,4}\s*(auto[-\s]?fix|patch plan|fix plan|code rewrite).*$"),
    re.compile(r"```(?:diff|patch)\n[\s\S]*?```", re.IGNORECASE),
    # diff file headers — [ \t]+ (not \s+) to avoid crossing line boundaries
    re.compile(r"(?m)^[-+]{3}[ \t]+\S+.*$"),
]

# Catches keyword=value inline (e.g. inside evidence strings, table cells, JSON values).
# Uses bounded character classes to avoid consuming JSON structural chars like ", ', comma.
_INLINE_SECRET = re.compile(
    r"(?:PASSWORD|SECRET|API_KEY|APIKEY|TOKEN|PASSWD|PRIVATE_KEY|"
    r"AUTH_TOKEN|ACCESS_TOKEN|CREDENTIALS?)\w*[ \t]*=[ \t]*"
    r"(?:'[^'\n]{4,}'|\"[^\"\n]{4,}\"|[A-Za-z0-9\-_./:@#!$%^&*+=~]{4,})",
    re.IGNORECASE,
)


def _redact_inline(match: re.Match) -> str:
    keyword = re.split(r"[ \t]*=", match.group(0), maxsplit=1)[0].rstrip()
    return f"{keyword}=[REDACTED]"


def sanitize_report(content: str) -> str:
    content = mask_secrets(content)
    content = _INLINE_SECRET.sub(_redact_inline, content)
    for pattern in _AUTOFIX_PATTERNS:
        content = pattern.sub("[REMOVED]", content)
    return content
