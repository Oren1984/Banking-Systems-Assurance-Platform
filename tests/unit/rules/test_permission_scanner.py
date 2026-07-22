from __future__ import annotations

from scanners.rules.permission_scanner import BroadPermissionScanner


def test_detects_wildcard_action_json_style():
    scanner = BroadPermissionScanner()
    findings = scanner.scan("policy.json", '{"Action": "*", "Effect": "Allow"}')
    assert any(f.rule_id == "PERM-001" for f in findings)


def test_detects_wildcard_action_hcl_style():
    scanner = BroadPermissionScanner()
    findings = scanner.scan("main.tf", '"Action" = "*"')
    assert any(f.rule_id == "PERM-001" for f in findings)


def test_detects_wildcard_resource():
    scanner = BroadPermissionScanner()
    findings = scanner.scan("policy.json", '{"Resource": "*"}')
    assert any(f.rule_id == "PERM-002" for f in findings)


def test_detects_admin_role_assignment():
    scanner = BroadPermissionScanner()
    findings = scanner.scan("app.py", 'role = "admin"')
    assert any(f.rule_id == "PERM-003" for f in findings)


def test_detects_public_access_flag():
    scanner = BroadPermissionScanner()
    findings = scanner.scan("config.yaml", "public: true")
    assert any(f.rule_id == "PERM-004" for f in findings)


def test_detects_anonymous_access_flag():
    scanner = BroadPermissionScanner()
    findings = scanner.scan("config.yaml", "allow_anonymous: true")
    assert any(f.rule_id == "PERM-005" for f in findings)


def test_detects_chmod_777():
    scanner = BroadPermissionScanner()
    findings = scanner.scan("setup.sh", "chmod 777 /data")
    assert any(f.rule_id == "PERM-006" for f in findings)


def test_clean_text_produces_no_findings():
    scanner = BroadPermissionScanner()
    findings = scanner.scan("app.py", "def add(a, b):\n    return a + b\n")
    assert findings == []
