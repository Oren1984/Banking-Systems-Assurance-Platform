from __future__ import annotations

from core.config import Settings
from agents.registry import get_agent_provider, validate_agent_configuration

# Phase 6 — agents/registry.py. Every scenario must resolve to either a
# genuinely available external adapter or local mode — never a crash, never
# "no provider at all."


def test_defaults_to_local_when_agent_disabled():
    settings = Settings(_env_file=None)
    handle = get_agent_provider(settings)
    assert handle.is_local is True
    assert handle.name == "local"
    assert "AGENT_ENABLED" in handle.reason


def test_local_explicitly_selected_stays_local_even_if_agent_enabled():
    settings = Settings(_env_file=None, agent_enabled=True, agent_provider="local")
    handle = get_agent_provider(settings)
    assert handle.is_local is True
    assert handle.name == "local"


def test_agent_enabled_but_external_providers_disabled_falls_back_to_local():
    settings = Settings(_env_file=None, agent_enabled=True, agent_provider="openai", external_providers_enabled=False)
    handle = get_agent_provider(settings)
    assert handle.is_local is True
    assert "EXTERNAL_PROVIDERS_ENABLED" in handle.reason


def test_agent_enabled_provider_selected_but_no_api_key_falls_back_to_local():
    settings = Settings(
        _env_file=None,
        agent_enabled=True,
        agent_provider="openai",
        external_providers_enabled=True,
        openai_enabled=True,
        openai_api_key=None,
    )
    handle = get_agent_provider(settings)
    assert handle.is_local is True
    assert "openai" in handle.reason


def test_agent_enabled_provider_own_flag_disabled_falls_back_to_local():
    settings = Settings(
        _env_file=None,
        agent_enabled=True,
        agent_provider="openai",
        external_providers_enabled=True,
        openai_enabled=False,
        openai_api_key="sk-fake-test-key",
    )
    handle = get_agent_provider(settings)
    assert handle.is_local is True


def test_fully_configured_external_provider_resolves_to_that_provider():
    settings = Settings(
        _env_file=None,
        agent_enabled=True,
        agent_provider="openai",
        external_providers_enabled=True,
        openai_enabled=True,
        openai_api_key="sk-fake-test-key",
    )
    handle = get_agent_provider(settings)
    assert handle.is_local is False
    assert handle.name == "openai"
    assert handle.adapter is not None
    assert handle.adapter.is_available() is True


def test_fully_configured_provider_never_logs_or_exposes_the_key():
    settings = Settings(
        _env_file=None,
        agent_enabled=True,
        agent_provider="claude",
        external_providers_enabled=True,
        claude_enabled=True,
        claude_api_key="sk-ant-fake-test-key",
    )
    handle = get_agent_provider(settings)
    assert "sk-ant-fake-test-key" not in repr(handle.adapter)


def test_each_of_the_three_providers_resolves_when_fully_configured():
    for name in ("openai", "gemini", "claude"):
        settings = Settings(
            _env_file=None,
            agent_enabled=True,
            agent_provider=name,
            external_providers_enabled=True,
            **{f"{name}_enabled": True, f"{name}_api_key": "fake-test-key"},
        )
        handle = get_agent_provider(settings)
        assert handle.name == name
        assert handle.is_local is False


def test_validate_agent_configuration_reports_missing_key():
    settings = Settings(
        _env_file=None, agent_enabled=True, agent_provider="gemini",
        external_providers_enabled=True, gemini_enabled=True, gemini_api_key=None,
    )
    warnings = validate_agent_configuration(settings)
    assert any("GEMINI_API_KEY" in w for w in warnings)


def test_validate_agent_configuration_reports_disabled_agent():
    settings = Settings(_env_file=None)
    warnings = validate_agent_configuration(settings)
    assert any("AGENT_ENABLED" in w for w in warnings)


def test_validate_agent_configuration_empty_for_fully_configured_provider():
    settings = Settings(
        _env_file=None, agent_enabled=True, agent_provider="openai",
        external_providers_enabled=True, openai_enabled=True, openai_api_key="sk-fake-test-key",
    )
    assert validate_agent_configuration(settings) == []


def test_validate_agent_configuration_empty_for_local_mode():
    settings = Settings(_env_file=None, agent_enabled=True, agent_provider="local")
    assert validate_agent_configuration(settings) == []
