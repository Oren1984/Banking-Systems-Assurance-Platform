from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from governance.report_sanitizer import sanitize_report
from models.enums import AuditEventType

# Phase 4 — Audit trail event construction
# (BANKING_PLATFORM_INTEGRATION_PLAN.md §13 Phase 4:
# "governance/audit_trail.py"). Pure function, no database — mirrors
# evidence/capture.py and scoring/recommendations.py's design:
# storage/db/repositories.py::AuditRepository is the only place that
# persists the result this module returns.
#
# APPEND-ONLY BY DESIGN: this module has no "update" or "delete" concept —
# it only ever builds a new event. Every free-text field is sanitized
# before an event is ever constructed, so a raw secret or an unmasked
# finding value can never reach the audit_events table through this path
# (see storage/db/models/audit_event.py's own module docstring).


@dataclass
class AuditEventInput:
    event_type: AuditEventType
    actor: str
    summary: str
    scan_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEventResult:
    event_type: str
    actor: str
    summary: str
    scan_id: Optional[str]
    payload: Dict[str, Any]


def build_audit_event(event: AuditEventInput) -> AuditEventResult:
    if not event.actor.strip():
        raise ValueError("audit event actor must not be empty")
    return AuditEventResult(
        event_type=event.event_type.value,
        actor=event.actor,
        summary=sanitize_report(event.summary),
        scan_id=event.scan_id,
        payload=_sanitize_payload(event.payload),
    )


def _sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Every string value (recursively, for nested dicts/lists) is passed
    through the same sanitizer used for human-facing reports — there is
    one sanitization implementation, not two."""
    sanitized: Dict[str, Any] = {}
    for key, value in payload.items():
        sanitized[key] = _sanitize_value(value)
    return sanitized


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_report(value)
    if isinstance(value, dict):
        return _sanitize_payload(value)
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    return value


__all__ = ["AuditEventInput", "AuditEventResult", "build_audit_event"]
