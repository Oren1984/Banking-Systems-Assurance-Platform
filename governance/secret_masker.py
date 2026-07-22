from __future__ import annotations

# Reused as-is from ai-project-control-tower/app/scanner/secret_masker.py
# (see BANKING_PLATFORM_INTEGRATION_PLAN.md §3: "Reuse as-is"). Pattern
# coverage is a known limitation, not a claim of completeness — banking-
# specific patterns (PANs, IBANs, routing numbers) are not yet included;
# see docs/security_boundaries.md.

import re
from typing import Callable, Union

REDACTED = "[REDACTED]"


def _preserve_key(m: re.Match) -> str:
    return m.group(1) + REDACTED


_PATTERNS: list[tuple[re.Pattern, Union[str, Callable[[re.Match], str]]]] = [
    # AWS access key ID: AKIA followed by 16 uppercase alphanumerics
    (re.compile(r"AKIA[0-9A-Z]{16}"), REDACTED),
    # GitHub tokens: ghp_, gho_, ghu_, ghs_, ghr_ prefix
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"), REDACTED),
    # GitHub fine-grained PAT
    (re.compile(r"github_pat_[A-Za-z0-9_]{82}"), REDACTED),
    # OpenAI key: sk- followed by exactly 48 alphanumerics
    (re.compile(r"sk-[A-Za-z0-9]{48}"), REDACTED),
    # Anthropic key: sk-ant- prefix
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{40,}"), REDACTED),
    # Google API key: AIza prefix + 35 chars
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), REDACTED),
    # JWT: three base64url segments separated by dots, starting with eyJ
    (
        re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
        REDACTED,
    ),
    # .env style secrets: KEYWORD=value — preserve the key name
    (
        re.compile(
            r"(?m)^([ \t]*(?:PASSWORD|SECRET|API_KEY|APIKEY|TOKEN|PASSWD|PRIVATE_KEY|"
            r"AUTH_TOKEN|ACCESS_TOKEN|CREDENTIALS?)\w*\s*=\s*)['\"]?\S{4,}['\"]?",
            re.IGNORECASE,
        ),
        _preserve_key,
    ),
    # Bearer tokens in HTTP headers — preserve "bearer " prefix
    (
        re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{20,}"),
        _preserve_key,
    ),
    # Quoted assignment style, anywhere in a line (not line-anchored, unlike
    # the .env-style pattern above) — catches code like
    # `db_password = "hunter2"` or `apiKey: "sk-..."`, added for Phase 2's
    # scanners/rules/secret_scanner.py. The env-style pattern above only
    # matches when the keyword is the first token on the line — this one
    # also matches a keyword anywhere before the assignment.
    (
        re.compile(
            r"(?i)((?:password|passwd|secret|api[_-]?key|apikey|token|"
            r"private[_-]?key|auth[_-]?token|access[_-]?token|credentials?)"
            r"\w*\s*[:=]\s*)(['\"])[^'\"\n]{4,}\2"
        ),
        _preserve_key,
    ),
    # Database/service connection strings with an inline password —
    # preserve everything except the password itself.
    (
        re.compile(
            r"(?i)((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)"
            r"://[^:\s]+:)[^@\s]+(@)"
        ),
        lambda m: m.group(1) + REDACTED + m.group(2),
    ),
]


def mask_secrets(content: str) -> str:
    for pattern, replacement in _PATTERNS:
        content = pattern.sub(replacement, content)
    return content


def find_secret_spans(content: str) -> list[tuple[int, int]]:
    """
    Return (start, end) character offsets for every secret-like match in
    `content`, using the exact same pattern set as mask_secrets(). Matches
    are found independently per pattern against the *original* content (not
    against progressively-masked content), so overlapping matches from
    different patterns may both appear — callers that turn this into
    findings should deduplicate by line number. Used by
    scanners/rules/secret_scanner.py so detection logic is defined in
    exactly one place, not duplicated between masking and scanning.
    """
    spans: list[tuple[int, int]] = []
    for pattern, _replacement in _PATTERNS:
        for m in pattern.finditer(content):
            spans.append((m.start(), m.end()))
    return spans
