from __future__ import annotations

from models.enums import AgentActionType
from agents.contracts import AgentContext

# Phase 6 — the always-available, deterministic local agent mode
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 6 requirement: "Provide a
# local or disabled implementation that allows the application to run
# without external credentials"). This is the platform's default and its
# safe fallback whenever the agent feature is disabled, no external
# provider is configured, or an external provider call fails — never a
# crash, never a blank UI state (agents/registry.py::get_agent_provider()
# only ever returns this mode or a genuinely available external adapter,
# nothing in between).
#
# DELIBERATE DESIGN CHOICE: this module never receives a raw Finding,
# Score, or any other ORM/domain object — only the exact same
# `AgentContext.sanitized_text` an external provider would have received
# (agents/sanitizer.py). This guarantees local mode can never leak
# anything an external call would not also have been given, and it means
# there is exactly one sanitization boundary in this codebase, not two.
#
# This is intentionally NOT a template that fabricates prose pretending to
# be an AI-generated explanation — it presents the already-sanitized,
# already-deterministic data directly, clearly labeled as local/non-AI.
# Fabricating explanatory language without a real model behind it would
# blur exactly the "AI-assisted vs. deterministic" line
# agents/contracts.py::AgentResponse's own fields exist to keep clear.

_HEADER = "[Local deterministic mode — no external AI provider was used for this response]"


def generate_local_response(action: AgentActionType, context: AgentContext, question: str | None = None) -> str:
    if action == AgentActionType.ANSWER_QUESTION:
        body = (
            "Local mode cannot synthesize a natural-language answer to a free-text question — "
            "that requires an external provider (currently disabled or unavailable). Below is "
            "the exact sanitized, size-limited context that would have been sent if one were "
            "enabled:\n\n" + context.sanitized_text
        )
    else:
        body = (
            "Local mode presents the sanitized, already-deterministic assessment data directly, "
            "rather than generating new prose. Enable and select an external provider to receive "
            "a natural-language version of the same, size-limited context:\n\n" + context.sanitized_text
        )

    truncation_note = (
        "\n\n[Note: this context was truncated to stay within the configured size/item limits.]"
        if context.truncated
        else ""
    )
    return f"{_HEADER}\n\n{body}{truncation_note}"


__all__ = ["generate_local_response"]
