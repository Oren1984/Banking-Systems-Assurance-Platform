from __future__ import annotations

from typing import Optional

from core.exceptions import ProviderDisabledError
from providers.base import ProviderAdapter, ProviderRequest, ProviderResponse

# Configuration-ready scaffolding — see providers/openai_adapter.py for the
# full pattern rationale (BANKING_PLATFORM_INTEGRATION_PLAN.md §7; Phase 6
# scope boundary: configuration-ready, not a real outbound call).


class ClaudeAdapter(ProviderAdapter):
    DEFAULT_MODEL = "claude-sonnet-5"

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
    ) -> None:
        if not api_key:
            raise ProviderDisabledError("ClaudeAdapter requires a non-empty api_key.")
        self._api_key = api_key
        self.model = model or self.DEFAULT_MODEL
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def is_available(self) -> bool:
        return bool(self._api_key)

    def send(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError(
            "ClaudeAdapter.send() is a configuration-ready stub — no real outbound API call is "
            "implemented, by design (see providers/openai_adapter.py's module docstring). "
            "agents/agent_service.py falls back to local mode when this is raised."
        )

    @property
    def provider_name(self) -> str:
        return "claude"

    def __repr__(self) -> str:
        return f"ClaudeAdapter(api_key=***, model={self.model!r})"
