from __future__ import annotations

# Adapted from RAG-Engineering-Lab/src/security/prompt_safety.py (see
# BANKING_PLATFORM_INTEGRATION_PLAN.md §3 and §10 finding #2).
#
# Advisory-only in Phase 1, exactly as in the source repository: this scan
# warns but never blocks a query. BANKING_PLATFORM_INTEGRATION_PLAN.md's
# approved revision (Part A §6/§9) calls for this to become a *configurable*
# hard gate in a later phase — `enforce` is added here as the extension
# point for that, defaulting to False so today's behavior is unchanged.

from dataclasses import dataclass, field
from typing import List

_SUSPICIOUS_PATTERNS: List[str] = [
    "ignore previous instructions",
    "ignore all previous",
    "disregard previous",
    "show system prompt",
    "reveal system prompt",
    "print system prompt",
    "developer message",
    "system message",
    "forget your instructions",
    "delete files",
    "run command",
    "execute code",
    "drop table",
    "rm -rf",
]


@dataclass
class SafetyCheckResult:
    is_suspicious: bool
    matched_patterns: List[str] = field(default_factory=list)
    warning: str = ""
    blocked: bool = False


def check_prompt_safety(query: str, enforce: bool = False) -> SafetyCheckResult:
    """
    Lightweight scan for suspicious query patterns.

    When `enforce` is False (the current default everywhere this is called),
    the result is advisory only and the caller decides whether to warn or
    proceed. When `enforce` is True, `blocked` is set on a match so a future
    caller can treat this as a hard gate without changing this function's
    detection logic.
    """
    lower = query.lower()
    matched = [p for p in _SUSPICIOUS_PATTERNS if p in lower]

    if matched:
        return SafetyCheckResult(
            is_suspicious=True,
            matched_patterns=matched,
            warning="Query may contain a prompt-injection attempt.",
            blocked=enforce,
        )

    return SafetyCheckResult(is_suspicious=False)
