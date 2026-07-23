from __future__ import annotations

from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from agents.agent_service import answer_question as _answer_question
from agents.agent_service import explain_finding as _explain_finding
from agents.agent_service import generate_executive_summary as _generate_executive_summary
from agents.agent_service import summarize_domain as _summarize_domain
from agents.contracts import AgentResponse
from agents.registry import validate_agent_configuration
from agents.sanitizer import DomainScoreForAgent, FindingForAgent
from core.config import Settings
from governance.audit_trail import AuditEventInput
from models.enums import AuditEventType
from storage.db.base import Base
from storage.db.models.finding import Finding
from storage.db.repositories import AuditRepository, ScanRepository, ScoringRepository

# Phase 6 — the only module that connects the optional agent boundary
# (agents/) to the database and to a specific assessment. Deliberately a
# separate file from ui/services/assessment_service.py, not a set of
# functions added to it — the same "the agent must appear outside the
# trusted deterministic assessment boundary" separation the Phase 6 brief
# requires is reflected here at the module-boundary level, not just in
# prose. No function in this module writes to a Finding, Score,
# ControlEvaluation, or Recommendation row — the only write this module
# ever performs is an AuditEvent, exactly like every other governance
# action in this codebase.
#
# Every call here requires the caller to already have taken an explicit
# action (a Streamlit button click, in `ui/streamlit_app.py`) — nothing in
# this module is invoked automatically when an assessment is opened.


def _session(settings: Settings) -> Session:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _finding_for_agent(row) -> FindingForAgent:
    return FindingForAgent(
        finding_id=row.id,
        rule_id=row.rule_id,
        severity=row.severity,
        confidence=row.confidence,
        title=row.title,
        masked_evidence=row.masked_evidence,
        description=row.description,
        recommended_action=row.recommended_action,
        source_relative_path=row.source_relative_path,
        line_start=row.line_start,
        banking_domains=list(row.banking_domains or []),
    )


def _domain_score_for_agent(row) -> DomainScoreForAgent:
    return DomainScoreForAgent(
        domain=row.domain,
        decision_category=row.decision_category,
        weighted_score=row.weighted_score,
        confidence_level=row.confidence_level,
        evidence_completeness=row.evidence_completeness,
        findings_count=row.findings_count,
        files_evaluated=row.files_evaluated,
    )


def _record_agent_audit_event(session: Session, scan_id: str, triggered_by: str, response: AgentResponse) -> None:
    AuditRepository(session).record(
        AuditEventInput(
            event_type=AuditEventType.AGENT_ACTION,
            actor=triggered_by,
            scan_id=scan_id,
            summary=(
                f"Agent action '{response.action.value}' via provider '{response.provider_name}' "
                f"({'success' if response.success else 'failed, fell back to local'})"
            ),
            payload={
                "action": response.action.value,
                "provider": response.provider_name,
                "is_local": response.is_local,
                "model": response.model_name,
                "success": response.success,
                "error": response.error,
                "context_categories": response.context_categories,
                "user_triggered": True,
            },
        )
    )


def get_agent_status(settings: Settings) -> dict:
    """Read-only status for UI display — never triggers a call."""
    from agents.registry import get_agent_provider

    handle = get_agent_provider(settings)
    return {
        "agent_enabled": settings.agent_enabled,
        "provider": handle.name,
        "is_local": handle.is_local,
        "reason": handle.reason,
        "warnings": validate_agent_configuration(settings),
    }


def explain_finding(settings: Settings, scan_id: str, finding_id: str, triggered_by: str) -> Optional[AgentResponse]:
    session = _session(settings)
    try:
        row = session.get(Finding, finding_id)
        if row is None or row.scan_id != scan_id:
            return None
        response = _explain_finding(settings, _finding_for_agent(row))
        _record_agent_audit_event(session, scan_id, triggered_by, response)
        return response
    finally:
        session.close()


def summarize_domain(settings: Settings, scan_id: str, domain: str, triggered_by: str) -> Optional[AgentResponse]:
    session = _session(settings)
    try:
        scores = [s for s in ScoringRepository(session).get_scores(scan_id) if s.domain == domain]
        if not scores:
            return None
        findings = [
            _finding_for_agent(f)
            for f in ScanRepository(session).get_findings(scan_id)
            if domain in (f.banking_domains or [])
        ]
        response = _summarize_domain(settings, _domain_score_for_agent(scores[0]), findings)
        _record_agent_audit_event(session, scan_id, triggered_by, response)
        return response
    finally:
        session.close()


def answer_question(
    settings: Settings, scan_id: str, question: str, triggered_by: str, evidence_finding_ids: Optional[List[str]] = None
) -> AgentResponse:
    session = _session(settings)
    try:
        findings = ScanRepository(session).get_findings(scan_id)
        if evidence_finding_ids:
            findings = [f for f in findings if f.id in evidence_finding_ids]
        snippets = [f"[{f.rule_id}] {f.title}: {f.masked_evidence}" for f in findings]
        response = _answer_question(settings, question, snippets)
        _record_agent_audit_event(session, scan_id, triggered_by, response)
        return response
    finally:
        session.close()


def generate_executive_summary(settings: Settings, scan_id: str, triggered_by: str) -> AgentResponse:
    session = _session(settings)
    try:
        scores = [_domain_score_for_agent(s) for s in ScoringRepository(session).get_scores(scan_id)]
        response = _generate_executive_summary(settings, scores)
        _record_agent_audit_event(session, scan_id, triggered_by, response)
        return response
    finally:
        session.close()


__all__ = [
    "get_agent_status",
    "explain_finding",
    "summarize_domain",
    "answer_question",
    "generate_executive_summary",
]
