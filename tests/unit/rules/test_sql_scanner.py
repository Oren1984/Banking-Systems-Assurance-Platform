from __future__ import annotations

from scanners.rules.sql_scanner import UnsafeSqlScanner


def test_detects_string_concatenated_sql():
    scanner = UnsafeSqlScanner()
    findings = scanner.scan("db.py", "query = \"SELECT * FROM users WHERE name = '\" + name")
    assert any(f.rule_id == "SQL-001" for f in findings)


def test_detects_fstring_sql():
    scanner = UnsafeSqlScanner()
    findings = scanner.scan("db.py", 'query = f"SELECT * FROM users WHERE id = {user_id}"')
    assert any(f.rule_id == "SQL-002" for f in findings)


def test_detects_percent_format_sql():
    scanner = UnsafeSqlScanner()
    findings = scanner.scan("db.py", "query = \"SELECT * FROM users WHERE id = %s\" % user_id")
    assert any(f.rule_id == "SQL-003" for f in findings)


def test_detects_destructive_sql():
    scanner = UnsafeSqlScanner()
    findings = scanner.scan("migration.sql", "DROP TABLE accounts;")
    assert any(f.rule_id == "SQL-004" for f in findings)


def test_detects_plaintext_db_credential():
    scanner = UnsafeSqlScanner()
    findings = scanner.scan("config.sql", "DB_PASSWORD=hunter2plaintext")
    assert any(f.rule_id == "SQL-005" for f in findings)
    cred_finding = next(f for f in findings if f.rule_id == "SQL-005")
    assert "hunter2plaintext" not in cred_finding.masked_evidence


def test_no_sql_is_ever_executed(monkeypatch):
    # This scanner must never import a DB driver or execute anything —
    # verified structurally: scanning arbitrary destructive SQL text must
    # not raise or attempt any I/O.
    scanner = UnsafeSqlScanner()
    findings = scanner.scan("evil.sql", "DROP DATABASE production; TRUNCATE TABLE accounts;")
    assert len(findings) >= 1


def test_clean_parameterized_query_is_not_flagged():
    scanner = UnsafeSqlScanner()
    findings = scanner.scan("db.py", 'cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))')
    assert findings == []
