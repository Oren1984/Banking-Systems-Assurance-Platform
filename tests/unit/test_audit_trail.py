from __future__ import annotations

import pytest

from governance.audit_trail import AuditEventInput, build_audit_event
from models.enums import AuditEventType

# Phase 4 — governance/audit_trail.py. Pure function, no database.
# The single most important property this file must prove: a raw secret
# or credential-shaped string passed into an event's summary or payload
# must never survive into the built AuditEventResult unmasked (this table
# is append-only — see storage/db/models/audit_event.py's own docstring —
# so anything that reaches it can never be corrected after the fact).


def test_build_audit_event_produces_expected_shape():
    event = build_audit_event(
        AuditEventInput(
            event_type=AuditEventType.SCAN_PERSISTED,
            actor="system",
            summary="Scan persisted",
            scan_id="scan-1",
            payload={"count": 3},
        )
    )
    assert event.event_type == AuditEventType.SCAN_PERSISTED.value
    assert event.actor == "system"
    assert event.scan_id == "scan-1"
    assert event.payload == {"count": 3}


def test_build_audit_event_requires_a_non_empty_actor():
    with pytest.raises(ValueError):
        build_audit_event(
            AuditEventInput(event_type=AuditEventType.SCAN_PERSISTED, actor="   ", summary="x")
        )


def test_build_audit_event_sanitizes_a_raw_secret_in_the_summary():
    event = build_audit_event(
        AuditEventInput(
            event_type=AuditEventType.FINDING_REVIEWED,
            actor="reviewer@example.com",
            summary='Reviewed finding containing PASSWORD = "hunter2value123"',
        )
    )
    assert "hunter2value123" not in event.summary


def test_build_audit_event_sanitizes_nested_payload_values():
    event = build_audit_event(
        AuditEventInput(
            event_type=AuditEventType.FINDING_REVIEWED,
            actor="reviewer@example.com",
            summary="ok",
            payload={
                "reason": 'contains API_KEY = "hunter2value123"',
                "nested": {"deep": 'TOKEN="hunter2value123"'},
                "list": ['SECRET = "hunter2value123"'],
                "count": 5,
            },
        )
    )
    assert "hunter2value123" not in event.payload["reason"]
    assert "hunter2value123" not in event.payload["nested"]["deep"]
    assert "hunter2value123" not in event.payload["list"][0]
    assert event.payload["count"] == 5


def test_build_audit_event_scan_id_defaults_to_none():
    event = build_audit_event(
        AuditEventInput(event_type=AuditEventType.SCAN_PERSISTED, actor="system", summary="ok")
    )
    assert event.scan_id is None
