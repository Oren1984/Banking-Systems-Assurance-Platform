from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from agents.contracts import AgentContext
from core.exceptions import GovernanceError
from governance.pii_redaction import redact_pii
from governance.prompt_safety import check_prompt_safety
from governance.report_sanitizer import sanitize_report

# Phase 6 — the dedicated sanitization/minimization boundary every agent
# action must pass through before any context reaches agents/agent_service.py
# (BANKING_PLATFORM_INTEGRATION_PLAN.md's own §7 requirement, restated for
# Phase 6: "External providers must never ... receive an entire repository
# by default ... receive raw secrets, credentials, tokens, passwords,
# private keys, or unnecessary PII").
#
# Reuses the platform's existing sanitization utilities rather than
# duplicating detection logic — the same rule
# scanners/rules/secret_scanner.py already follows for
# governance/secret_masker.py:
#   1. governance/report_sanitizer.sanitize_report() — masks secrets
#      (governance/secret_masker.py) and strips any auto-fix/patch-plan
#      content, exactly as already applied to every human-facing report.
#   2. governance/pii_redaction.redact_pii() — a second pass for
#      email/phone/long-digit-run patterns not already caught by masking.
#
# Every function here is pure — no database, no network, no Streamlit —
# and every function enforces both a character limit and an item-count
# limit so "summarize everything" cannot silently balloon into a
# near-full-repository payload. Inputs are plain dataclasses
# (`FindingForAgent`, `DomainScoreForAgent`), never ORM rows or raw
# Finding/Score ORM objects — the same "pure function, plain input shape"
# convention scoring/engine.py and evidence/capture.py already established.
#
# WHAT THIS MODULE NEVER RECEIVES: raw (unmasked) evidence. Every
# `FindingForAgent.masked_evidence` value is expected to already be
# `Finding.masked_evidence` — the same guarantee
# storage/db/models/finding.py's own docstring documents (no raw
# `evidence` column exists at all). This module has no code path that
# could introduce raw content even if a caller tried.


@dataclass
class FindingForAgent:
    finding_id: str
    rule_id: str
    severity: str
    confidence: str
    title: str
    masked_evidence: str
    description: str
    recommended_action: str
    source_relative_path: str
    line_start: int
    banking_domains: List[str] = field(default_factory=list)


@dataclass
class DomainScoreForAgent:
    domain: str
    decision_category: str
    weighted_score: Optional[float]
    confidence_level: str
    evidence_completeness: str
    findings_count: int
    files_evaluated: int


def _sanitize(text: str) -> str:
    return redact_pii(sanitize_report(text))


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def build_finding_context(finding: FindingForAgent, max_chars: int) -> AgentContext:
    raw = (
        f"Rule: {finding.rule_id}\n"
        f"Severity: {finding.severity} (confidence: {finding.confidence})\n"
        f"Title: {finding.title}\n"
        f"Location: {finding.source_relative_path}:{finding.line_start}\n"
        f"Banking domains: {', '.join(finding.banking_domains) or 'none mapped'}\n"
        f"Evidence (already masked): {finding.masked_evidence}\n"
        f"Description: {finding.description}\n"
        f"Recommended action (advisory only, never auto-applied): {finding.recommended_action}\n"
    )
    text, truncated = _truncate(_sanitize(raw), max_chars)
    return AgentContext(
        categories=["finding_detail"],
        sanitized_text=text,
        char_count=len(text),
        item_count=1,
        truncated=truncated,
    )


def build_domain_context(
    domain_score: DomainScoreForAgent,
    findings: List[FindingForAgent],
    max_chars: int,
    max_items: int,
) -> AgentContext:
    limited = findings[:max_items]
    truncated_by_count = len(findings) > max_items

    lines = [
        f"Domain: {domain_score.domain}",
        f"Decision category: {domain_score.decision_category}",
        f"Weighted score: {domain_score.weighted_score if domain_score.weighted_score is not None else 'N/A (insufficient evidence)'}",
        f"Confidence: {domain_score.confidence_level}",
        f"Evidence completeness: {domain_score.evidence_completeness}",
        f"Findings count: {domain_score.findings_count}",
        f"Files evaluated: {domain_score.files_evaluated}",
        "",
        f"Findings included below: {len(limited)} of {domain_score.findings_count}",
    ]
    for f in limited:
        lines.append(f"- [{f.severity}] {f.rule_id}: {f.title} ({f.source_relative_path}:{f.line_start})")

    text, truncated_by_chars = _truncate(_sanitize("\n".join(lines)), max_chars)
    return AgentContext(
        categories=["domain_score", "finding_summary"],
        sanitized_text=text,
        char_count=len(text),
        item_count=len(limited),
        truncated=truncated_by_chars or truncated_by_count,
    )


def build_question_context(
    question: str,
    evidence_snippets: List[str],
    max_chars: int,
    max_items: int,
) -> AgentContext:
    safety = check_prompt_safety(question, enforce=True)
    if safety.blocked:
        raise GovernanceError(f"question rejected by prompt-safety check: {safety.warning}")

    limited = evidence_snippets[:max_items]
    truncated_by_count = len(evidence_snippets) > max_items

    lines = [f"Question: {question}", "", "Retrieved evidence (sanitized):"]
    for i, snippet in enumerate(limited, start=1):
        lines.append(f"{i}. {snippet}")

    text, truncated_by_chars = _truncate(_sanitize("\n".join(lines)), max_chars)
    return AgentContext(
        categories=["question", "retrieved_evidence"],
        sanitized_text=text,
        char_count=len(text),
        item_count=len(limited),
        truncated=truncated_by_chars or truncated_by_count,
    )


def build_executive_summary_context(
    domain_scores: List[DomainScoreForAgent],
    max_chars: int,
    max_items: int,
) -> AgentContext:
    limited = domain_scores[:max_items]
    truncated_by_count = len(domain_scores) > max_items

    lines = [f"Domains included below: {len(limited)} of {len(domain_scores)}", ""]
    for s in limited:
        weighted = s.weighted_score if s.weighted_score is not None else "N/A"
        lines.append(f"- {s.domain}: {s.decision_category} (weighted score: {weighted}, findings: {s.findings_count})")

    text, truncated_by_chars = _truncate(_sanitize("\n".join(lines)), max_chars)
    return AgentContext(
        categories=["domain_score_overview"],
        sanitized_text=text,
        char_count=len(text),
        item_count=len(limited),
        truncated=truncated_by_chars or truncated_by_count,
    )


__all__ = [
    "FindingForAgent",
    "DomainScoreForAgent",
    "build_finding_context",
    "build_domain_context",
    "build_question_context",
    "build_executive_summary_context",
]
