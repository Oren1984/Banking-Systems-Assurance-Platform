from __future__ import annotations

from core.exceptions import ProviderDisabledError
from providers.base import ProviderAdapter, ProviderRequest, ProviderResponse

# Disabled-by-default scaffolding only — see providers/openai_adapter.py for
# the pattern rationale (BANKING_PLATFORM_INTEGRATION_PLAN.md §7, Phase 6).


class ClaudeAdapter(ProviderAdapter):
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ProviderDisabledError("ClaudeAdapter requires a non-empty api_key.")
        self._api_key = api_key

    def is_available(self) -> bool:
        return bool(self._api_key)

    def send(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError(
            "ClaudeAdapter.send() is not implemented in Phase 1. "
            "Real outbound calls are scoped to Phase 6 (Optional External Providers)."
        )

    @property
    def provider_name(self) -> str:
        return "claude"

    def __repr__(self) -> str:
        return "ClaudeAdapter(api_key=***)"
