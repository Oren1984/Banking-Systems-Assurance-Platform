from __future__ import annotations

import json
from datetime import datetime, timezone

from governance.report_sanitizer import sanitize_report
from scanners.scan_orchestrator import ScanResult

# Phase 2 — Report Export (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2
# brief, §11). JSON (machine-readable) and Markdown (human-readable).
# Every exported string field is passed through
# governance/report_sanitizer.py — the same sanitizer already used for
# Phase 1/5 reports — so this reuses the platform's one sanitization
# implementation rather than adding a second one. Findings only ever carry
# `masked_evidence` (see storage/db/models/finding.py), so no additional
# masking step is needed for evidence specifically, but sanitize_report()
# is still applied defensively to every free-text field (title,
# description, recommended_action) in case a scanner's fixed strings ever
# change to include something masking should catch.
#
# Absolute local paths are never included — every path in an export is the
# relative_path already computed by scanners/file_discovery.py.


def to_json(result: ScanResult) -> str:
    payload = _build_payload(result)
    return json.dumps(payload, indent=2, sort_keys=False, default=str)


def to_markdown(result: ScanResult) -> str:
    summary = result.summary
    lines: list[str] = []

    lines.append("# Banking Systems Assurance Platform — Scan Report")
    lines.append("")
    lines.append(
        "**Read-only statement:** This scan never wrote to, executed, or modified "
        "the scanned source in any way. Recommendations are advisory only — this "
        "platform never applies fixes automatically."
    )
    lines.append("")
    lines.append("## Scan Metadata")
    lines.append(f"- Scan ID: `{summary.scan_id}`")
    lines.append(f"- Status: `{summary.status.value}`")
    lines.append(f"- Source type: `{summary.source_type}`")
    lines.append(f"- Started: {summary.started_at.isoformat()}")
    lines.append(f"- Completed: {summary.completed_at.isoformat() if summary.completed_at else 'N/A'}")
    lines.append("")
    lines.append("## Source Integrity Verification")
    lines.append(f"- Integrity verified: **{summary.integrity_verified}**")
    lines.append(f"- Hash before: `{summary.source_hash_before}`")
    lines.append(f"- Hash after: `{summary.source_hash_after}`")
    lines.append("")
    lines.append("## File Inventory Summary")
    lines.append(f"- Total files found: {summary.total_files_found}")
    lines.append(f"- Files scanned: {summary.files_scanned}")
    lines.append(f"- Files skipped: {summary.files_skipped}")
    lines.append(f"- Scan truncated by a safety limit: {summary.truncated}")
    lines.append("")
    lines.append("## Domain Coverage")
    if summary.findings_by_domain:
        for domain, count in sorted(summary.findings_by_domain.items()):
            lines.append(f"- {domain}: {count} finding(s)")
    else:
        lines.append("- No findings were mapped to a banking domain in this scan.")
    lines.append("")
    lines.append("## Findings Summary")
    lines.append(f"- Total findings: {summary.total_findings}")
    for severity, count in sorted(summary.findings_by_severity.items()):
        lines.append(f"- {severity}: {count}")
    lines.append("")
    lines.append("## Scanner Execution Summary")
    for execution in result.scanner_executions:
        lines.append(
            f"- `{execution.scanner_id}` v{execution.scanner_version}: "
            f"{execution.status}, {execution.files_processed} file(s) processed, "
            f"{execution.files_errored} error(s), {execution.findings_produced} finding(s)"
        )
    if summary.scanner_warnings:
        lines.append("")
        lines.append("### Warnings")
        for warning in summary.scanner_warnings:
            lines.append(f"- {sanitize_report(warning)}")
    lines.append("")
    lines.append("## Detailed Findings (Sanitized)")
    if not result.findings:
        lines.append("No findings were produced by this scan.")
    for normalized in result.findings:
        raw = normalized.raw
        lines.append("")
        lines.append(f"### {sanitize_report(raw.title)}")
        lines.append(f"- Rule: `{raw.rule_id}` (`{normalized.scanner_id}` v{normalized.scanner_version})")
        lines.append(f"- Category: `{raw.category.value}`")
        lines.append(f"- Severity: `{raw.severity.value}` — Confidence: `{raw.confidence.value}`")
        lines.append(f"- Finding type: `{raw.finding_type.value}` (observed evidence vs. inference)")
        lines.append(f"- File: `{normalized.source_relative_path}` (line {raw.line_start})")
        if normalized.banking_domains:
            lines.append(f"- Banking domains: {', '.join(normalized.banking_domains)}")
        lines.append(f"- Evidence (masked): `{raw.masked_evidence}`")
        lines.append(f"- Description: {sanitize_report(raw.description)}")
        lines.append(f"- Impact: {sanitize_report(raw.impact)}")
        lines.append(f"- Recommended action (advisory only): {sanitize_report(raw.recommended_action)}")

    lines.append("")
    lines.append("## Limitations")
    lines.append(
        "- Phase 2 scanners are pattern-based and deterministic; they do not execute "
        "or semantically analyze code."
    )
    lines.append(
        "- PII/sensitive-data findings are pattern matches only and are not a "
        "regulatory compliance determination."
    )
    lines.append(
        "- Files skipped due to safety limits, unsupported types, or symlink "
        "restrictions were not evaluated by any scanner."
    )
    lines.append("")
    return "\n".join(lines)


def to_findings_csv(result: ScanResult) -> str:
    """Optional CSV export, findings only (per the Phase 2 brief's
    'Optional: CSV for findings')."""
    header = [
        "finding_id_ordinal",
        "scanner_id",
        "rule_id",
        "title",
        "category",
        "severity",
        "confidence",
        "finding_type",
        "source_relative_path",
        "line_start",
        "line_end",
        "banking_domains",
        "masked_evidence",
    ]
    rows = [",".join(header)]
    for i, normalized in enumerate(result.findings, start=1):
        raw = normalized.raw
        row = [
            str(i),
            normalized.scanner_id,
            raw.rule_id,
            _csv_escape(raw.title),
            raw.category.value,
            raw.severity.value,
            raw.confidence.value,
            raw.finding_type.value,
            _csv_escape(normalized.source_relative_path),
            str(raw.line_start),
            str(raw.line_end),
            _csv_escape("|".join(normalized.banking_domains)),
            _csv_escape(raw.masked_evidence),
        ]
        rows.append(",".join(row))
    return "\n".join(rows)


def _csv_escape(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'


def _build_payload(result: ScanResult) -> dict:
    summary = result.summary
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only_statement": (
            "This scan never wrote to, executed, or modified the scanned source. "
            "Recommendations are advisory only."
        ),
        "scan_metadata": {
            "scan_id": summary.scan_id,
            "status": summary.status.value,
            "source_type": summary.source_type,
            "started_at": summary.started_at.isoformat(),
            "completed_at": summary.completed_at.isoformat() if summary.completed_at else None,
        },
        "integrity_verification": {
            "verified": summary.integrity_verified,
            "hash_before": summary.source_hash_before,
            "hash_after": summary.source_hash_after,
        },
        "file_inventory_summary": {
            "total_files_found": summary.total_files_found,
            "files_scanned": summary.files_scanned,
            "files_skipped": summary.files_skipped,
            "truncated": summary.truncated,
        },
        "domain_coverage": summary.findings_by_domain,
        "findings_summary": {
            "total": summary.total_findings,
            "by_severity": summary.findings_by_severity,
        },
        "scanner_execution_summary": [
            {
                "scanner_id": e.scanner_id,
                "scanner_version": e.scanner_version,
                "status": e.status,
                "files_processed": e.files_processed,
                "files_errored": e.files_errored,
                "findings_produced": e.findings_produced,
                "error_summary": sanitize_report(e.error_summary) if e.error_summary else None,
            }
            for e in result.scanner_executions
        ],
        "findings": [
            {
                "scanner_id": n.scanner_id,
                "scanner_version": n.scanner_version,
                "rule_id": n.raw.rule_id,
                "title": sanitize_report(n.raw.title),
                "finding_type": n.raw.finding_type.value,
                "category": n.raw.category.value,
                "severity": n.raw.severity.value,
                "confidence": n.raw.confidence.value,
                "banking_domains": n.banking_domains,
                "source_relative_path": n.source_relative_path,
                "line_start": n.raw.line_start,
                "line_end": n.raw.line_end,
                "masked_evidence": n.raw.masked_evidence,
                "description": sanitize_report(n.raw.description),
                "impact": sanitize_report(n.raw.impact),
                "recommended_action": sanitize_report(n.raw.recommended_action),
                "remediation_mode": n.raw.remediation_mode.value,
                "read_only_confirmation": n.raw.read_only_confirmation,
            }
            for n in result.findings
        ],
        "warnings": summary.scanner_warnings,
        "limitations": [
            "Phase 2 scanners are pattern-based and deterministic; no code is executed or semantically analyzed.",
            "PII/sensitive-data findings are pattern matches only, not a regulatory compliance determination.",
            "Files skipped due to safety limits, unsupported types, or symlink restrictions were not evaluated.",
        ],
    }
