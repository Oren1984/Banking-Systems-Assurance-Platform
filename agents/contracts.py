from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from models.enums import AgentActionType

# Phase 6 — Optional agent boundary: shared data shapes.
# (BANKING_PLATFORM_INTEGRATION_PLAN.md never explicitly scoped this
# module by name; it exists so agents/sanitizer.py, agents/local_agent.py,
# agents/registry.py, and agents/agent_service.py all speak one vocabulary
# — the same "one shared contracts module" rule core/contracts.py and
# providers/base.py already established for their own layers.
#
# EVERYTHING HERE IS ADVISORY, NEVER AUTHORITATIVE. No dataclass in this
# module is a Finding, a Score, or anything persisted as a deterministic
# assessment result — see AgentResponse's own fields below, which exist
# specifically to make "this is AI-assisted, not a scanner finding"
# machine-checkable rather than an implicit assumption (the same pattern
# `models.enums.RemediationMode` already uses for "never auto-fix").

ADVISORY_DISCLAIMER = (
    "AI-assisted, advisory only. Non-deterministic. Not a scanner finding, not a score, "
    "and not an approval or compliance decision — deterministic findings, scores, and "
    "governance status are unaffected by this output."
)


@dataclass
class AgentContext:
    """The sanitized, size-limited context actually available to be sent
    to a provider (local or external) for one agent action. Built
    exclusively by agents/sanitizer.py — no other module constructs this
    directly, so there is exactly one place data minimization happens.

    `sanitized_text` is the only content field — deliberately no raw
    object references (Finding, Score, ...) are carried alongside it, so
    a caller cannot accidentally forward something unsanitized "just this
    once."
    """

    categories: List[str] = field(default_factory=list)  # e.g. ["finding_detail", "domain_score"]
    sanitized_text: str = ""
    char_count: int = 0
    item_count: int = 0
    truncated: bool = False


@dataclass
class AgentResponse:
    action: AgentActionType
    provider_name: str  # "local" | "openai" | "gemini" | "claude"
    is_local: bool
    success: bool
    content: str
    disclaimer: str = ADVISORY_DISCLAIMER
    is_advisory: bool = True
    error: Optional[str] = None
    model_name: Optional[str] = None
    latency_ms: float = 0.0
    context_categories: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


__all__ = ["ADVISORY_DISCLAIMER", "AgentContext", "AgentResponse"]
