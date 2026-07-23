from __future__ import annotations

from typing import Optional

from core.config import Settings
from providers.base import ProviderAdapter

# BANKING_PLATFORM_INTEGRATION_PLAN.md §7 — activation rules:
# EXTERNAL_PROVIDERS_ENABLED must be true AND the specific provider's own
# enable flag must be true AND its API key must be set. All three
# conditions must hold before this registry returns anything other than
# None. No adapter is ever instantiated otherwise (see
# tests/isolation/test_provider_kill_switch.py).

_PROVIDER_NAMES = ("openai", "gemini", "claude")


def get_provider(name: str, settings: Settings) -> Optional[ProviderAdapter]:
    if name not in _PROVIDER_NAMES:
        return None

    if not settings.external_providers_enabled:
        return None

    # model/timeout/max_retries are read from the agent_* settings because
    # the optional agent boundary (agents/) is, as of Phase 6, this
    # registry's only caller — see agents/registry.py, which sits one
    # layer above this function. A future non-agent caller of this
    # registry could pass distinct values by constructing an adapter
    # directly instead of through get_provider().
    kwargs = dict(
        model=settings.agent_model_name,
        timeout_seconds=settings.agent_timeout_seconds,
        max_retries=settings.agent_max_retries,
    )

    if name == "openai":
        if not (settings.openai_enabled and settings.openai_api_key):
            return None
        from providers.openai_adapter import OpenAIAdapter

        return OpenAIAdapter(api_key=settings.openai_api_key, **kwargs)

    if name == "gemini":
        if not (settings.gemini_enabled and settings.gemini_api_key):
            return None
        from providers.gemini_adapter import GeminiAdapter

        return GeminiAdapter(api_key=settings.gemini_api_key, **kwargs)

    if name == "claude":
        if not (settings.claude_enabled and settings.claude_api_key):
            return None
        from providers.claude_adapter import ClaudeAdapter

        return ClaudeAdapter(api_key=settings.claude_api_key, **kwargs)

    return None
