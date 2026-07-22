from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

# BANKING_PLATFORM_INTEGRATION_PLAN.md §7 — shared provider interface.
# ProviderRequest carries only sanitized, size-capped context: never raw
# findings, never raw source files, never unredacted scan results. Every
# outbound request must have passed through governance/report_sanitizer.py
# and governance/pii_redaction.py before construction (enforced by the
# caller, not by this dataclass, since sanitization is a pipeline step —
# see governance/README.md for the enforcement point once assessment/
# exists in Phase 4+).


@dataclass
class ProviderRequest:
    purpose: str
    sanitized_context: str
    approved_by: Optional[str] = None
    max_tokens: int = 2000
    metadata: dict = field(default_factory=dict)


@dataclass
class ProviderResponse:
    provider_name: str
    content: str
    latency_ms: float
    metadata: dict = field(default_factory=dict)


class ProviderAdapter(ABC):
    """Shared interface for all optional external AI provider adapters.

    No adapter may access the vector store directly (see rag/vectorstores/)
    and no adapter may receive raw banking documents or source code — only
    a pre-sanitized ProviderRequest.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """False if disabled by the kill switch, unconfigured, or missing a key."""

    @abstractmethod
    def send(self, request: ProviderRequest) -> ProviderResponse:
        """Send a sanitized request to the provider. Must not be called when
        is_available() is False — see providers/registry.py."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier (e.g. 'openai', 'gemini', 'claude')."""
