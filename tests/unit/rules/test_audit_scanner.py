from __future__ import annotations

from models.enums import ConfidenceLevel, FindingType
from scanners.rules.audit_scanner import AuditGapScanner


def test_detects_audit_disabled_config():
    scanner = AuditGapScanner()
    findings = scanner.scan("config.ini", "audit_enabled = false")
    assert any(f.rule_id == "AUDIT-001" for f in findings)
    disabled = next(f for f in findings if f.rule_id == "AUDIT-001")
    assert disabled.finding_type == FindingType.OBSERVED_EVIDENCE
    assert disabled.confidence == ConfidenceLevel.HIGH


def test_flags_sensitive_operation_without_nearby_audit_call():
    text = "def transfer_funds(a, b, amount):\n    a.balance -= amount\n    b.balance += amount\n"
    scanner = AuditGapScanner()
    findings = scanner.scan("service.py", text)
    op_findings = [f for f in findings if f.rule_id == "AUDIT-002"]
    assert len(op_findings) == 1
    assert op_findings[0].finding_type == FindingType.INFERENCE
    assert op_findings[0].confidence == ConfidenceLevel.LOW


def test_does_not_flag_sensitive_operation_with_nearby_audit_call():
    text = (
        "def approve_loan(loan_id):\n"
        "    audit_log('loan_approved', loan_id=loan_id)\n"
        "    return True\n"
    )
    scanner = AuditGapScanner()
    findings = scanner.scan("service.py", text)
    assert not [f for f in findings if f.rule_id == "AUDIT-002"]


def test_flags_audit_block_missing_standard_fields():
    text = "audit_entry = {'note': 'something happened'}\n"
    scanner = AuditGapScanner()
    findings = scanner.scan("audit.py", text)
    assert any(f.rule_id == "AUDIT-003" for f in findings)


def test_does_not_flag_audit_block_with_standard_fields_present():
    text = "audit_entry = {'user': u, 'action': a, 'timestamp': t}\n"
    scanner = AuditGapScanner()
    findings = scanner.scan("audit.py", text)
    assert not [f for f in findings if f.rule_id == "AUDIT-003"]


def test_clean_text_produces_no_findings():
    scanner = AuditGapScanner()
    findings = scanner.scan("app.py", "def add(a, b):\n    return a + b\n")
    assert findings == []
