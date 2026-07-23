from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from core.config import Settings
from providers.base import ProviderAdapter
from providers.registry import get_provider

# Phase 6 — safe agent-provider selection
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 6: "Add a provider registry
# or factory that ... defaults safely to local/disabled mode ... prevents
# accidental fallback to an external provider"). This module sits one
# layer above providers/registry.py's raw `get_provider()` — that function
# already enforces the three-condition activation rule
# (EXTERNAL_PROVIDERS_ENABLED AND the specific provider's own enable flag
# AND a non-empty API key); this module adds the fourth, agent-specific
# condition (`AGENT_ENABLED`) and — critically — never raises and never
# returns nothing: every call resolves to either a genuinely available
# external adapter or the always-available local mode, with a
# human-readable `reason` explaining which and why. A UI or service caller
# never has to handle "no provider at all."
#
# PRECEDENCE (all must hold for anything other than local mode):
#   1. settings.agent_enabled is True (the agent *feature* is turned on)
#   2. settings.agent_provider != "local" (an external provider was chosen)
#   3. settings.external_providers_enabled is True (the platform-wide kill
#      switch — see providers/registry.py's own docstring)
#   4. providers.registry.get_provider(name, settings) returns a real
#      adapter (the provider's own enable flag AND API key are both set)
# Any single failure at any step falls back to local — never a crash, never
# a silent attempt to reach an unconfigured provider.


@dataclass
class AgentProviderHandle:
    name: str  # "local" | "openai" | "gemini" | "claude"
    is_local: bool
    is_available: bool
    reason: str
    adapter: Optional[ProviderAdapter] = None


def get_agent_provider(settings: Settings) -> AgentProviderHandle:
    if not settings.agent_enabled:
        return AgentProviderHandle(
            name="local", is_local=True, is_available=True,
            reason="agent feature disabled by configuration (AGENT_ENABLED=false)",
        )

    if settings.agent_provider == "local":
        return AgentProviderHandle(
            name="local", is_local=True, is_available=True, reason="local mode explicitly selected",
        )

    if not settings.external_providers_enabled:
        return AgentProviderHandle(
            name="local", is_local=True, is_available=True,
            reason="external providers disabled platform-wide (EXTERNAL_PROVIDERS_ENABLED=false); falling back to local",
        )

    adapter = get_provider(settings.agent_provider, settings)
    if adapter is None:
        return AgentProviderHandle(
            name="local", is_local=True, is_available=True,
            reason=(
                f"provider '{settings.agent_provider}' is not fully configured "
                "(its own enable flag or API key is missing); falling back to local"
            ),
        )

    return AgentProviderHandle(
        name=adapter.provider_name, is_local=False, is_available=adapter.is_available(),
        reason=f"{adapter.provider_name} is configured and available", adapter=adapter,
    )


def validate_agent_configuration(settings: Settings) -> List[str]:
    """Pure diagnostic — never raises, never blocks construction. Returns
    human-readable warnings about a configuration that will fall back to
    local mode, so a UI or operator can see *why* without reading logs."""
    warnings: List[str] = []
    if settings.agent_provider not in ("local", "openai", "gemini", "claude"):
        warnings.append(f"agent_provider={settings.agent_provider!r} is not a recognized provider name")
        return warnings

    if not settings.agent_enabled:
        warnings.append("AGENT_ENABLED is false — the agent feature itself is off")
        return warnings

    if settings.agent_provider == "local":
        return warnings

    if not settings.external_providers_enabled:
        warnings.append(
            f"agent_provider={settings.agent_provider!r} was selected but EXTERNAL_PROVIDERS_ENABLED is false"
        )
    provider_enabled = getattr(settings, f"{settings.agent_provider}_enabled", False)
    api_key = getattr(settings, f"{settings.agent_provider}_api_key", None)
    if not provider_enabled:
        warnings.append(f"{settings.agent_provider.upper()}_ENABLED is false")
    if not api_key:
        warnings.append(f"{settings.agent_provider.upper()}_API_KEY is not set")
    return warnings


__all__ = ["AgentProviderHandle", "get_agent_provider", "validate_agent_configuration"]
