from __future__ import annotations

from scanners.rules.insecure_config_scanner import InsecureConfigurationScanner


def test_detects_debug_enabled():
    scanner = InsecureConfigurationScanner()
    findings = scanner.scan("settings.py", "DEBUG = true")
    assert any(f.rule_id == "CFG-001" for f in findings)


def test_detects_tls_verification_disabled():
    scanner = InsecureConfigurationScanner()
    findings = scanner.scan("settings.py", "ssl_verify: false")
    assert any(f.rule_id == "CFG-002" for f in findings)


def test_detects_requests_verify_false():
    scanner = InsecureConfigurationScanner()
    findings = scanner.scan("client.py", "requests.get(url, verify=False)")
    assert any(f.rule_id == "CFG-002" for f in findings)


def test_detects_authentication_disabled():
    scanner = InsecureConfigurationScanner()
    findings = scanner.scan("settings.ini", "auth_enabled = false")
    assert any(f.rule_id == "CFG-003" for f in findings)


def test_detects_encryption_disabled():
    scanner = InsecureConfigurationScanner()
    findings = scanner.scan("settings.ini", "encryption_enabled = false")
    assert any(f.rule_id == "CFG-004" for f in findings)


def test_detects_permissive_cors():
    scanner = InsecureConfigurationScanner()
    findings = scanner.scan("app.py", 'Access-Control-Allow-Origin: "*"')
    assert any(f.rule_id == "CFG-005" for f in findings)


def test_detects_public_bind():
    scanner = InsecureConfigurationScanner()
    findings = scanner.scan("server.py", 'host = "0.0.0.0"')
    assert any(f.rule_id == "CFG-006" for f in findings)


def test_detects_default_weak_credential():
    scanner = InsecureConfigurationScanner()
    findings = scanner.scan("settings.ini", "admin = admin")
    assert any(f.rule_id == "CFG-007" for f in findings)


def test_detects_verbose_error_exposure():
    scanner = InsecureConfigurationScanner()
    findings = scanner.scan("settings.py", "display_errors = true")
    assert any(f.rule_id == "CFG-008" for f in findings)


def test_clean_config_produces_no_findings():
    scanner = InsecureConfigurationScanner()
    findings = scanner.scan(
        "settings.py",
        "DEBUG = false\nssl_verify = true\nauth_enabled = true\n",
    )
    assert findings == []
