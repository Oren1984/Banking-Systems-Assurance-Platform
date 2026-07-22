from __future__ import annotations

from core.exceptions import ProviderDisabledError
from providers.base import ProviderAdapter, ProviderRequest, ProviderResponse

# Disabled-by-default scaffolding only (BANKING_PLATFORM_INTEGRATION_PLAN.md
# §7, Phase 6). Fail-fast-at-construction / never-log-key pattern adapted
# from RAG-Engineering-Lab/src/embeddings/openai_provider.py. No real
# outbound API call is implemented in Phase 1 — send() raises
# NotImplementedError. The `openai` SDK is intentionally NOT imported here
# (lazy-import only, inside send(), once Phase 6 implements it), so this
# module has no dependency on the SDK being installed for local-only
# startup or Phase 1 tests.


class OpenAIAdapter(ProviderAdapter):
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ProviderDisabledError("OpenAIAdapter requires a non-empty api_key.")
        self._api_key = api_key  # never logged, never included in __repr__

    def is_available(self) -> bool:
        return bool(self._api_key)

    def send(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError(
            "OpenAIAdapter.send() is not implemented in Phase 1. "
            "Real outbound calls are scoped to Phase 6 (Optional External Providers)."
        )

    @property
    def provider_name(self) -> str:
        return "openai"

    def __repr__(self) -> str:
        return "OpenAIAdapter(api_key=***)"
