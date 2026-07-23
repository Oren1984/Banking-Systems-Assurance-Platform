from __future__ import annotations

import time
from typing import List

from agents.contracts import AgentContext, AgentResponse
from agents.local_agent import generate_local_response
from agents.registry import AgentProviderHandle, get_agent_provider
from agents.sanitizer import (
    DomainScoreForAgent,
    FindingForAgent,
    build_domain_context,
    build_executive_summary_context,
    build_finding_context,
    build_question_context,
)
from core.config import Settings
from governance.report_sanitizer import sanitize_report
from models.enums import AgentActionType
from providers.base import ProviderRequest

# Phase 6 — the agent boundary's orchestration layer: the only module the
# UI (via ui/services/agent_ui_service.py) actually calls. Pure — no
# database, no Streamlit — mirrors scoring/engine.py and
# assessment/evaluators/control_evaluator.py's "pure function, repository
# wires it" convention.
#
# THIS MODULE ADDS NO NEW BUSINESS LOGIC TO THE DETERMINISTIC CORE. It
# never touches Finding/Score/ControlEvaluation rows, never writes to the
# database, and never calls anything in scanners/, scoring/,
# assessment/evaluators/, or governance/approval_workflow.py. Every
# response it returns is explicitly advisory
# (agents/contracts.py::AgentResponse.is_advisory, always True) and is
# never treated as a canonical finding or score anywhere in this codebase.
#
# PROVIDER FAILURE NEVER PROPAGATES. Every external-adapter call is
# wrapped; any exception (including the `NotImplementedError` every
# provider adapter's `send()` currently raises — see providers/README.md
# for why real outbound calls remain unimplemented) results in a graceful
# fallback to the local, deterministic response with `success=False` and a
# sanitized error message — never a crash, and never a failure that
# propagates to the assessment the agent was asked about.


def _run(action: AgentActionType, context: AgentContext, handle: AgentProviderHandle, settings: Settings) -> AgentResponse:
    start = time.monotonic()

    if handle.is_local or handle.adapter is None:
        content = generate_local_response(action, context)
        return AgentResponse(
            action=action,
            provider_name="local",
            is_local=True,
            success=True,
            content=content,
            context_categories=context.categories,
            latency_ms=(time.monotonic() - start) * 1000,
            metadata={"reason": handle.reason, "context_char_count": context.char_count, "context_truncated": context.truncated},
        )

    try:
        request = ProviderRequest(
            purpose=action.value,
            sanitized_context=context.sanitized_text,
            max_tokens=settings.agent_max_context_chars,
            metadata={"model": settings.agent_model_name} if settings.agent_model_name else {},
        )
        provider_response = handle.adapter.send(request)
        return AgentResponse(
            action=action,
            provider_name=handle.name,
            is_local=False,
            success=True,
            content=provider_response.content,
            model_name=settings.agent_model_name,
            latency_ms=provider_response.latency_ms,
            context_categories=context.categories,
            metadata={"context_char_count": context.char_count, "context_truncated": context.truncated},
        )
    except Exception as exc:  # noqa: BLE001 — a provider failure must never propagate to the caller
        fallback_content = generate_local_response(action, context)
        sanitized_error = sanitize_report(str(exc))[:300]
        return AgentResponse(
            action=action,
            provider_name=handle.name,
            is_local=True,
            success=False,
            content=fallback_content,
            error=sanitized_error,
            model_name=settings.agent_model_name,
            latency_ms=(time.monotonic() - start) * 1000,
            context_categories=context.categories,
            metadata={"attempted_provider": handle.name, "context_char_count": context.char_count},
        )


def explain_finding(settings: Settings, finding: FindingForAgent) -> AgentResponse:
    context = build_finding_context(finding, settings.agent_max_context_chars)
    handle = get_agent_provider(settings)
    return _run(AgentActionType.EXPLAIN_FINDING, context, handle, settings)


def summarize_domain(
    settings: Settings, domain_score: DomainScoreForAgent, findings: List[FindingForAgent]
) -> AgentResponse:
    context = build_domain_context(
        domain_score, findings, settings.agent_max_context_chars, settings.agent_max_evidence_items
    )
    handle = get_agent_provider(settings)
    return _run(AgentActionType.SUMMARIZE_DOMAIN, context, handle, settings)


def answer_question(settings: Settings, question: str, evidence_snippets: List[str]) -> AgentResponse:
    context = build_question_context(
        question, evidence_snippets, settings.agent_max_context_chars, settings.agent_max_evidence_items
    )
    handle = get_agent_provider(settings)
    return _run(AgentActionType.ANSWER_QUESTION, context, handle, settings)


def generate_executive_summary(settings: Settings, domain_scores: List[DomainScoreForAgent]) -> AgentResponse:
    context = build_executive_summary_context(
        domain_scores, settings.agent_max_context_chars, settings.agent_max_evidence_items
    )
    handle = get_agent_provider(settings)
    return _run(AgentActionType.EXECUTIVE_SUMMARY, context, handle, settings)


__all__ = ["explain_finding", "summarize_domain", "answer_question", "generate_executive_summary"]
