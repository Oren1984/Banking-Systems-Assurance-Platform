from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

from assessment.engine import AssessmentResult
from governance.report_sanitizer import sanitize_report

# Phase 4 — Assessment-level report export
# (BANKING_PLATFORM_INTEGRATION_PLAN.md §13 Phase 4: "report disclaimers").
# Extends Phase 2's scan-level reporting/scan_report_exporter.py with the
# Phase 3/4 governance layer: domain scores, control-evaluation coverage,
# recommendation status, human-review state, and the audit trail — the
# parts of the platform's own output that did not exist when
# scan_report_exporter.py was written and therefore could not be
# disclaimed there. Every free-text field is passed through the same
# governance/report_sanitizer.py used everywhere else in the platform —
# one sanitization implementation, not two.
#
# DISCLAIMERS ARE NOT DECORATIVE: this module exists specifically so that
# every assessment report — machine- or human-readable — states plainly
# that (1) this is not a regulatory compliance certification, (2) findings
# and scores are pending human review by default and must not be read as
# final until reviewed, (3) the platform never generates or applies
# remediation, only advisory recommendations, and (4) all detection,
# scoring, and control-evaluation logic in the current phase is
# deterministic and pattern-based — no LLM or RAG component produced or
# influenced any finding, score, or recommendation in this report.

_GOVERNANCE_DISCLAIMERS = [
    "This report is not a banking regulatory or compliance certification. Controls evaluated "
    "here are illustrative, engineering-derived technical checks, not citations to any specific "
    "regulation or standard (see knowledge_base/controls/README.md).",
    "All findings default to a pending human-review status. A domain scored high_risk or "
    "critical_risk with any pending finding blocks this assessment from being finalized — see "
    "the Human Review Status section below.",
    "Recommendations are advisory only. This platform never generates, applies, or auto-executes "
    "a remediation, patch, or configuration change against the assessed system.",
    "All detection, scoring, and control-evaluation logic in this report is deterministic and "
    "pattern-based. No AI/LLM or RAG component generated, altered, or influenced any finding, "
    "score, control evaluation, or recommendation.",
    "A human reviewer may override a score or a finding's review status; every override is "
    "recorded in the audit trail with a mandatory justification and is never silent.",
]


def to_assessment_markdown(result: AssessmentResult) -> str:
    lines: list[str] = []
    lines.append("# Banking Systems Assurance Platform — Assessment Report")
    lines.append("")
    lines.append(f"- Scan ID: `{result.scan_id}`")
    lines.append(f"- Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("## Governance Disclaimers")
    for disclaimer in _GOVERNANCE_DISCLAIMERS:
        lines.append(f"- {disclaimer}")
    lines.append("")

    lines.append("## Domain Scores")
    by_category = Counter(s.decision_category for s in result.scores)
    for category, count in sorted(by_category.items()):
        lines.append(f"- {category}: {count} domain(s)")
    lines.append("")
    for score in sorted(result.scores, key=lambda s: s.domain):
        weighted = f"{score.weighted_score:.1f}" if score.weighted_score is not None else "N/A"
        lines.append(
            f"- `{score.domain}`: {score.decision_category} (weighted score: {weighted}, "
            f"confidence: {score.confidence_level}, evidence: {score.evidence_completeness})"
        )
    lines.append("")

    lines.append("## Control Evaluation Summary")
    by_status = Counter(ce.status for ce in result.control_evaluations)
    for status, count in sorted(by_status.items()):
        lines.append(f"- {status}: {count} (domain, control) result(s)")
    lines.append("")

    lines.append("## Recommendations")
    if not result.recommendations:
        lines.append("No recommendations were generated for this scan.")
    for rec in result.recommendations:
        lines.append(f"- [{rec.priority}] ({rec.status}) {sanitize_report(rec.text)}")
    lines.append("")

    lines.append("## Human Review Status")
    review_counts = Counter(f.human_review_status for f in result.findings)
    for status, count in sorted(review_counts.items()):
        lines.append(f"- {status}: {count} finding(s)")
    lines.append("")

    lines.append("## Audit Trail")
    for event in result.audit_events:
        lines.append(f"- `{event.created_at.isoformat()}` [{event.event_type}] ({event.actor}): {event.summary}")
    lines.append("")

    return "\n".join(lines)


def to_assessment_json(result: AssessmentResult) -> str:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scan_id": result.scan_id,
        "governance_disclaimers": _GOVERNANCE_DISCLAIMERS,
        "scores": [
            {
                "domain": s.domain,
                "decision_category": s.decision_category,
                "raw_score": s.raw_score,
                "weighted_score": s.weighted_score,
                "confidence_level": s.confidence_level,
                "evidence_completeness": s.evidence_completeness,
                "files_evaluated": s.files_evaluated,
                "findings_count": s.findings_count,
            }
            for s in result.scores
        ],
        "control_evaluations": [
            {
                "domain": ce.domain,
                "control_id": ce.control_id,
                "status": ce.status,
                "finding_ids": ce.finding_ids,
            }
            for ce in result.control_evaluations
        ],
        "recommendations": [
            {
                "finding_id": r.finding_id,
                "control_id": r.control_id,
                "text": sanitize_report(r.text),
                "priority": r.priority,
                "status": r.status,
            }
            for r in result.recommendations
        ],
        "human_review_status_counts": dict(Counter(f.human_review_status for f in result.findings)),
        "audit_trail": [
            {
                "event_type": e.event_type,
                "actor": e.actor,
                "summary": e.summary,
                "created_at": e.created_at.isoformat(),
            }
            for e in result.audit_events
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=False, default=str)


def to_findings_csv(result: AssessmentResult) -> str:
    """Phase 5 — findings-only CSV export, structurally suitable the same
    way reporting/scan_report_exporter.py::to_findings_csv() already is
    for Phase 2 findings; this variant additionally carries
    human_review_status, which only exists once a Finding is persisted
    (Phase 3+)."""
    header = [
        "finding_id",
        "rule_id",
        "severity",
        "confidence",
        "banking_domains",
        "source_relative_path",
        "line_start",
        "human_review_status",
        "masked_evidence",
    ]
    rows = [",".join(header)]
    for f in result.findings:
        row = [
            f.id,
            f.rule_id,
            f.severity,
            f.confidence,
            _csv_escape("|".join(f.banking_domains or [])),
            _csv_escape(f.source_relative_path),
            str(f.line_start),
            f.human_review_status,
            _csv_escape(sanitize_report(f.masked_evidence)),
        ]
        rows.append(",".join(row))
    return "\n".join(rows)


def to_scores_csv(result: AssessmentResult) -> str:
    """Phase 5 — domain scores CSV export."""
    header = [
        "domain",
        "decision_category",
        "raw_score",
        "weighted_score",
        "confidence_level",
        "evidence_completeness",
        "findings_count",
        "files_evaluated",
        "override_of",
    ]
    rows = [",".join(header)]
    for s in result.scores:
        row = [
            s.domain,
            s.decision_category,
            "" if s.raw_score is None else str(s.raw_score),
            "" if s.weighted_score is None else str(s.weighted_score),
            s.confidence_level,
            s.evidence_completeness,
            str(s.findings_count),
            str(s.files_evaluated),
            s.override_of or "",
        ]
        rows.append(",".join(row))
    return "\n".join(rows)


def _csv_escape(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'


__all__ = ["to_assessment_markdown", "to_assessment_json", "to_findings_csv", "to_scores_csv"]
