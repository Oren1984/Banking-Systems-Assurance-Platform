from __future__ import annotations

from typing import Optional

from core.exceptions import ProviderDisabledError
from providers.base import ProviderAdapter, ProviderRequest, ProviderResponse

# Configuration-ready scaffolding (BANKING_PLATFORM_INTEGRATION_PLAN.md §7;
# finalized in Phase 6 per that phase's own scope: "Adapters may remain
# configuration-ready or minimally implemented if real external execution
# is outside the approved final scope. Do not make real paid API calls by
# default."). Fail-fast-at-construction / never-log-key pattern adapted
# from RAG-Engineering-Lab/src/embeddings/openai_provider.py.
#
# `send()` still raises NotImplementedError — no real outbound HTTP call
# exists anywhere in this module, and no network-client library (`httpx`,
# `requests`, the `openai` SDK) is imported here, lazily or otherwise. This
# is a deliberate Phase 6 scope boundary, not an oversight: implementing a
# real call would require this codebase to depend on live, paid,
# non-deterministic external infrastructure for a project brief whose
# entire premise is a deterministic, local-first core. `model`/
# `timeout_seconds`/`max_retries` exist so the configuration surface
# (agents/agent_service.py, core.config.Settings) is real and testable
# even though no call is actually placed — every value is read and stored,
# never silently ignored.


class OpenAIAdapter(ProviderAdapter):
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
    ) -> None:
        if not api_key:
            raise ProviderDisabledError("OpenAIAdapter requires a non-empty api_key.")
        self._api_key = api_key  # never logged, never included in __repr__
        self.model = model or self.DEFAULT_MODEL
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def is_available(self) -> bool:
        return bool(self._api_key)

    def send(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError(
            "OpenAIAdapter.send() is a configuration-ready stub — no real outbound API call is "
            "implemented, by design (see this module's own docstring). "
            "agents/agent_service.py falls back to local mode when this is raised."
        )

    @property
    def provider_name(self) -> str:
        return "openai"

    def __repr__(self) -> str:
        return f"OpenAIAdapter(api_key=***, model={self.model!r})"
