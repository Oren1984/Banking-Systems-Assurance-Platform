from __future__ import annotations

from core.config import Settings
from providers.registry import get_provider


def test_returns_none_when_kill_switch_disabled():
    settings = Settings(
        _env_file=None,
        external_providers_enabled=False,
        openai_enabled=True,
        openai_api_key="sk-fake-not-a-real-key",
    )
    assert get_provider("openai", settings) is None
    assert get_provider("gemini", settings) is None
    assert get_provider("claude", settings) is None


def test_returns_none_when_kill_switch_enabled_but_provider_disabled():
    settings = Settings(
        _env_file=None,
        external_providers_enabled=True,
        openai_enabled=False,
        openai_api_key="sk-fake-not-a-real-key",
    )
    assert get_provider("openai", settings) is None


def test_returns_none_when_provider_enabled_but_no_key():
    settings = Settings(
        _env_file=None,
        external_providers_enabled=True,
        openai_enabled=True,
        openai_api_key=None,
    )
    assert get_provider("openai", settings) is None


def test_returns_adapter_only_when_all_three_conditions_hold():
    settings = Settings(
        _env_file=None,
        external_providers_enabled=True,
        openai_enabled=True,
        openai_api_key="sk-fake-not-a-real-key",
    )
    adapter = get_provider("openai", settings)
    assert adapter is not None
    assert adapter.provider_name == "openai"
    assert adapter.is_available() is True


def test_unknown_provider_name_returns_none():
    settings = Settings(_env_file=None, external_providers_enabled=True)
    assert get_provider("not-a-real-provider", settings) is None
