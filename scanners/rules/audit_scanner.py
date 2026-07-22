from __future__ import annotations

import re
from typing import List

from models.enums import ConfidenceLevel, FindingCategory, FindingType, Severity
from scanners.content_reader import line_for_offset
from scanners.rules.base import BaseScanner, RawFinding

# Phase 2 scanner D — Weak or Missing Audit Indicators
# (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2 brief, §6.D). Deliberately
# conservative: the two heuristic rules (sensitive-operation-without-audit,
# audit-record-missing-fields) are marked FindingType.INFERENCE with LOW
# confidence, since regex-based control-flow/scope analysis cannot prove
# absence — it can only note that no matching call was found nearby.

_AUDIT_DISABLED_RE = re.compile(
    r"(?i)\b(audit(?:_log(?:ging)?)?_enabled)\s*[:=]\s*(false|0|off|no)\b"
)

_SENSITIVE_OP_DEF_RE = re.compile(
    r"(?im)^[ \t]*(?:def|function)\s+"
    r"(\w*(?:transfer|withdraw|deposit|approve|reject|delete_account|"
    r"close_account|grant_access|revoke_access|update_permission|"
    r"override)\w*)\s*\("
)
_AUDIT_CALL_HINT_RE = re.compile(
    r"(?i)\b(audit_log|audit\.record|log_audit|auditlogger|record_audit|audit_event)\b"
)

_AUDIT_BLOCK_HINT_RE = re.compile(r"(?i)\baudit")
_AUDIT_FIELD_HINTS = ("user", "actor", "action", "timestamp", "correlation_id", "request_id")

_BODY_WINDOW_LINES = 25


class AuditGapScanner(BaseScanner):
    scanner_id = "audit_gap"
    scanner_version = "1.0.0"
    category = FindingCategory.AUDIT_GAP

    def scan(self, relative_path: str, text: str) -> List[RawFinding]:
        findings: List[RawFinding] = []
        findings += self._audit_disabled(text)
        findings += self._sensitive_op_without_audit(text)
        findings += self._audit_record_missing_fields(text)
        return findings

    def _audit_disabled(self, text: str) -> List[RawFinding]:
        out = []
        for m in _AUDIT_DISABLED_RE.finditer(text):
            line_no = line_for_offset(text, m.start())
            out.append(
                RawFinding(
                    title="Audit logging appears disabled in configuration",
                    finding_type=FindingType.OBSERVED_EVIDENCE,
                    category=self.category,
                    severity=Severity.HIGH,
                    confidence=ConfidenceLevel.HIGH,
                    line_start=line_no,
                    line_end=line_no,
                    evidence=m.group(0),
                    masked_evidence=m.group(0),
                    description="A configuration key matching an audit-logging enable flag is set to a disabled value.",
                    impact="If audit logging is genuinely disabled, actions in this system may not be traceable after the fact.",
                    recommended_action="Confirm whether audit logging is intentionally disabled here; if not, re-enable it.",
                    rule_id="AUDIT-001",
                )
            )
        return out

    def _sensitive_op_without_audit(self, text: str) -> List[RawFinding]:
        out = []
        lines = text.splitlines()
        for m in _SENSITIVE_OP_DEF_RE.finditer(text):
            op_name = m.group(1)
            line_no = line_for_offset(text, m.start())
            window = "\n".join(lines[line_no - 1 : line_no - 1 + _BODY_WINDOW_LINES])
            if _AUDIT_CALL_HINT_RE.search(window):
                continue
            out.append(
                RawFinding(
                    title=f"Sensitive operation '{op_name}' has no obvious nearby audit call",
                    finding_type=FindingType.INFERENCE,
                    category=self.category,
                    severity=Severity.MEDIUM,
                    confidence=ConfidenceLevel.LOW,
                    line_start=line_no,
                    line_end=min(line_no + _BODY_WINDOW_LINES, len(lines)),
                    evidence=lines[line_no - 1].strip(),
                    masked_evidence=lines[line_no - 1].strip(),
                    description=(
                        f"The function/method '{op_name}' matches a sensitive-operation "
                        f"naming pattern, but no known audit-call pattern "
                        f"was found in the following {_BODY_WINDOW_LINES} lines. This is "
                        "a heuristic based on nearby text, not a control-flow analysis — "
                        "it may miss an audit call made elsewhere (e.g. via a decorator "
                        "or middleware)."
                    ),
                    impact="A sensitive operation without traceable audit records is harder to investigate after an incident.",
                    recommended_action="Confirm manually whether this operation is audited (directly or via middleware/decorator).",
                    rule_id="AUDIT-002",
                    metadata={"operation_name": op_name},
                )
            )
        return out

    def _audit_record_missing_fields(self, text: str) -> List[RawFinding]:
        out = []
        lines = text.splitlines()
        reported_lines: set[int] = set()
        for m in _AUDIT_BLOCK_HINT_RE.finditer(text):
            line_no = line_for_offset(text, m.start())
            if line_no in reported_lines:
                continue
            window_start = max(0, line_no - 1)
            window = "\n".join(lines[window_start : window_start + _BODY_WINDOW_LINES]).lower()
            present = sum(1 for hint in _AUDIT_FIELD_HINTS if hint in window)
            if present >= 2:
                continue
            reported_lines.add(line_no)
            out.append(
                RawFinding(
                    title="Audit-related content may be missing standard metadata fields",
                    finding_type=FindingType.INFERENCE,
                    category=self.category,
                    severity=Severity.LOW,
                    confidence=ConfidenceLevel.LOW,
                    line_start=line_no,
                    line_end=min(line_no + _BODY_WINDOW_LINES, len(lines)),
                    evidence=lines[line_no - 1].strip(),
                    masked_evidence=lines[line_no - 1].strip(),
                    description=(
                        "Audit-related content was found, but fewer than two of the "
                        f"standard fields ({', '.join(_AUDIT_FIELD_HINTS)}) were found "
                        "nearby. This is a keyword-proximity heuristic, not a schema "
                        "validation."
                    ),
                    impact="Audit records missing actor/action/timestamp/correlation identifiers are harder to use during an investigation.",
                    recommended_action="Confirm manually whether this audit record includes who did what, when, and how it correlates to a request.",
                    rule_id="AUDIT-003",
                )
            )
        return out
