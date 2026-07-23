from __future__ import annotations

from core.config import Settings
from core.exceptions import ProviderError
from agents.agent_service import answer_question, explain_finding, generate_executive_summary, summarize_domain
from agents.registry import AgentProviderHandle
from agents.sanitizer import DomainScoreForAgent, FindingForAgent
import agents.agent_service as agent_service_module
from models.enums import AgentActionType
from providers.base import ProviderAdapter, ProviderRequest, ProviderResponse

# Phase 6 — agents/agent_service.py. Uses fakes/mocks only — no real
# external API call is made anywhere in this test file, consistent with
# "External-provider tests must use mocks or fakes by default."


def _finding(**overrides) -> FindingForAgent:
    defaults = dict(
        finding_id="f1", rule_id="SECRET-001", severity="high", confidence="medium",
        title="Likely secret found", masked_evidence="PASSWORD = [REDACTED]",
        description="d", recommended_action="r", source_relative_path="app/config.py",
        line_start=5, banking_domains=["core_banking"],
    )
    defaults.update(overrides)
    return FindingForAgent(**defaults)


def _domain_score(**overrides) -> DomainScoreForAgent:
    defaults = dict(
        domain="core_banking", decision_category="high_risk", weighted_score=5.7,
        confidence_level="low", evidence_completeness="complete", findings_count=1, files_evaluated=1,
    )
    defaults.update(overrides)
    return DomainScoreForAgent(**defaults)


class _FakeSucceedingAdapter(ProviderAdapter):
    provider_name = "openai"

    def is_available(self) -> bool:
        return True

    def send(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(provider_name="openai", content=f"AI response for: {request.purpose}", latency_ms=12.3)


class _FakeFailingAdapter(ProviderAdapter):
    provider_name = "openai"

    def is_available(self) -> bool:
        return True

    def send(self, request: ProviderRequest) -> ProviderResponse:
        raise ProviderError("simulated upstream failure — no real network call was made")


def test_explain_finding_uses_local_mode_by_default():
    settings = Settings(_env_file=None)
    response = explain_finding(settings, _finding())
    assert response.is_local is True
    assert response.success is True
    assert response.provider_name == "local"
    assert response.action == AgentActionType.EXPLAIN_FINDING


def test_explain_finding_never_contains_a_raw_secret_that_slipped_into_a_field():
    settings = Settings(_env_file=None)
    finding = _finding(description='API_KEY = "hunter2value123demo"')
    response = explain_finding(settings, finding)
    assert "hunter2value123demo" not in response.content


def test_summarize_domain_local_mode():
    settings = Settings(_env_file=None)
    response = summarize_domain(settings, _domain_score(), [_finding()])
    assert response.is_local is True
    assert response.action == AgentActionType.SUMMARIZE_DOMAIN


def test_answer_question_local_mode():
    settings = Settings(_env_file=None)
    response = answer_question(settings, "What is the biggest risk?", ["evidence snippet"])
    assert response.is_local is True
    assert response.action == AgentActionType.ANSWER_QUESTION


def test_generate_executive_summary_local_mode():
    settings = Settings(_env_file=None)
    response = generate_executive_summary(settings, [_domain_score()])
    assert response.is_local is True
    assert response.action == AgentActionType.EXECUTIVE_SUMMARY


def test_response_always_carries_the_advisory_disclaimer():
    settings = Settings(_env_file=None)
    response = explain_finding(settings, _finding())
    assert response.is_advisory is True
    assert "advisory" in response.disclaimer.lower()


def test_agent_service_uses_a_succeeding_fake_external_adapter(monkeypatch):
    settings = Settings(_env_file=None, agent_enabled=True, agent_provider="openai")
    handle = AgentProviderHandle(name="openai", is_local=False, is_available=True, reason="fake", adapter=_FakeSucceedingAdapter())
    monkeypatch.setattr(agent_service_module, "get_agent_provider", lambda s: handle)

    response = explain_finding(settings, _finding())
    assert response.is_local is False
    assert response.success is True
    assert response.provider_name == "openai"
    assert "AI response for: explain_finding" in response.content


def test_agent_service_gracefully_falls_back_when_the_external_adapter_fails(monkeypatch):
    settings = Settings(_env_file=None, agent_enabled=True, agent_provider="openai")
    handle = AgentProviderHandle(name="openai", is_local=False, is_available=True, reason="fake", adapter=_FakeFailingAdapter())
    monkeypatch.setattr(agent_service_module, "get_agent_provider", lambda s: handle)

    response = explain_finding(settings, _finding())
    assert response.success is False
    assert response.is_local is True  # fell back
    assert "simulated upstream failure" in response.error
    assert response.content  # local fallback content is still produced, never empty


def test_provider_failure_error_message_is_sanitized(monkeypatch):
    class _LeakyAdapter(ProviderAdapter):
        provider_name = "openai"

        def is_available(self) -> bool:
            return True

        def send(self, request: ProviderRequest) -> ProviderResponse:
            raise ProviderError('upstream rejected PASSWORD = "hunter2value123demo"')

    settings = Settings(_env_file=None, agent_enabled=True, agent_provider="openai")
    handle = AgentProviderHandle(name="openai", is_local=False, is_available=True, reason="fake", adapter=_LeakyAdapter())
    monkeypatch.setattr(agent_service_module, "get_agent_provider", lambda s: handle)

    response = explain_finding(settings, _finding())
    assert "hunter2value123demo" not in response.error


def test_real_provider_stub_not_implemented_falls_back_gracefully():
    # The real (unmocked) OpenAIAdapter.send() always raises NotImplementedError
    # today — confirms agents/agent_service.py handles that specific,
    # real exception type gracefully too, not just a generic mock.
    settings = Settings(
        _env_file=None, agent_enabled=True, agent_provider="openai",
        external_providers_enabled=True, openai_enabled=True, openai_api_key="sk-fake-test-key",
    )
    response = explain_finding(settings, _finding())
    assert response.success is False
    assert response.is_local is True
    assert response.error is not None
