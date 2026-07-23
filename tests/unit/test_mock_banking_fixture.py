from __future__ import annotations

from pathlib import Path

from core.config import Settings
from core.domains import BankingDomain
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory

# Phase 5 — mock_banking_system/ fixture integrity and regression coverage.
# Every number asserted here was captured by actually running the real
# scanner/assessment pipeline against this exact fixture — see
# docs/mock_banking_planted_findings.md, which is the authoritative,
# human-readable record these tests pin as a regression guard. If a future
# change to a scanner or to this fixture changes these numbers, that is
# exactly what this file exists to catch — not to be "fixed" by loosening
# the assertion without first checking which side actually drifted.

REPO_ROOT = Path(__file__).resolve().parents[2]
MOCK_SYSTEM_PATH = REPO_ROOT / "mock_banking_system"


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=[str(REPO_ROOT)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
    )


def _scan(tmp_path):
    settings = _settings(tmp_path)
    handle = ingest_local_directory(str(MOCK_SYSTEM_PATH), settings)
    try:
        return run_scan(handle, settings)
    finally:
        handle.cleanup()


def test_no_real_secret_shaped_values_are_present_in_the_fixture():
    # A cheap, direct guard against ever accidentally committing something
    # that looks like a real credential — every synthetic value in this
    # fixture is deliberately prefixed "fake_"/"demo_"/contains "DEMO"/"mock".
    forbidden_substrings = ("BEGIN PRIVATE KEY", "BEGIN RSA PRIVATE KEY")
    for path in MOCK_SYSTEM_PATH.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for forbidden in forbidden_substrings:
            assert forbidden not in text, f"{path} contains a forbidden real-secret-shaped marker"


def test_scanning_the_mock_system_produces_exactly_forty_two_findings(tmp_path):
    result = _scan(tmp_path)
    assert result.summary.total_findings == 42
    assert result.summary.integrity_verified is True


def test_scanning_the_mock_system_severity_distribution(tmp_path):
    result = _scan(tmp_path)
    assert result.summary.findings_by_severity == {
        "critical": 4,
        "high": 18,
        "medium": 10,
        "low": 10,
    }


def test_scanning_the_mock_system_touches_fifteen_of_sixteen_domains(tmp_path):
    result = _scan(tmp_path)
    evaluated = set()
    for mappings in result.domain_mappings.values():
        for m in mappings:
            evaluated.add(m.domain.value)
    all_domains = {d.value for d in BankingDomain}
    assert evaluated == all_domains - {"model_ai_governance"}


def test_model_ai_governance_has_zero_findings_and_zero_evaluated_files(tmp_path):
    result = _scan(tmp_path)
    assert "model_ai_governance" not in result.summary.findings_by_domain
    for mappings in result.domain_mappings.values():
        for m in mappings:
            assert m.domain != BankingDomain.MODEL_AI_GOVERNANCE


def test_designated_clean_files_produce_no_findings(tmp_path):
    result = _scan(tmp_path)
    findings_by_path = {}
    for n in result.findings:
        findings_by_path.setdefault(n.source_relative_path, []).append(n.raw.rule_id)

    clean_files = [
        "app/accounts/account_lookup_clean.py",
        "app/payments/payment_processor_clean.py",
        "app/credit/loan_approval.py",
        "app/investments/portfolio_service_clean.py",
        "app/auth/login_handler.py",
        "app/audit/audit_trail_service_clean.py",
        "app/business_continuity/disaster_recovery_plan.py",
        "database/migrations/0001_create_accounts_schema.sql",
        "observability/monitoring_config.yaml",
    ]
    for relative_path in clean_files:
        assert findings_by_path.get(relative_path, []) == [], (
            f"{relative_path} was expected to be a clean (no-finding) negative example"
        )


def test_planted_positive_findings_fire_with_expected_rule_ids(tmp_path):
    result = _scan(tmp_path)
    findings_by_path = {}
    for n in result.findings:
        findings_by_path.setdefault(n.source_relative_path, set()).add(n.raw.rule_id)

    expected = {
        "app/accounts/account_service.py": {"SECRET-001", "AUDIT-002", "AUDIT-003", "SQL-001", "SQL-005"},
        "app/payments/payment_processor.py": {"SECRET-001", "LOG-001"},
        "app/credit/underwriter_access.py": {"PERM-003"},
        "app/investments/portfolio_service.py": {"AUDIT-002", "AUDIT-003"},
        "app/identity/onboarding.py": {
            "PII-EMAIL",
            "PII-PHONE",
            "PII-NATIONAL_ID_SHAPED",
            "PII-DATE_OF_BIRTH",
            "PII-ACCOUNT_NUMBER_FIELD",
        },
        "app/fraud/aml_screening.py": {"AUDIT-002", "SQL-003"},
        "app/privacy/data_retention_policy.py": {"CFG-004"},
        "app/security/access_control.py": {"PERM-001", "PERM-002"},
        "app/audit/audit_trail_service.py": {"AUDIT-003"},
        "app/reconciliation/ledger_reconciliation.py": {"SQL-001"},
        "database/migrations/0002_drop_legacy_ledger.sql": {"SQL-004"},
        "config/security_baseline.ini": {
            "CFG-001",
            "CFG-002",
            "CFG-003",
            "CFG-005",
            "CFG-006",
            "CFG-007",
            "CFG-008",
        },
        "config/db_schema_credentials.env": {"SQL-005"},
        "config/legacy_vault_password.secrets": {"SKIP-001"},
        "api/routes/openapi_routes.yaml": {"PERM-004"},
        "infra/terraform/iam_policy.tf": {"PERM-001", "PERM-002"},
        "infra/k8s/configmap.yaml": {"PERM-005"},
        "deployment/docker-compose.yml": {"CFG-006"},
        "logging/app_logger.py": {"LOG-001"},
    }
    for relative_path, expected_rules in expected.items():
        actual = findings_by_path.get(relative_path, set())
        assert expected_rules <= actual, f"{relative_path}: expected {expected_rules}, got {actual}"


def test_scanning_the_mock_system_twice_is_deterministic(tmp_path):
    result_a = _scan(tmp_path)
    result_b = _scan(tmp_path)

    def _fingerprint(result):
        return sorted((n.raw.rule_id, n.raw.severity.value, n.source_relative_path) for n in result.findings)

    assert _fingerprint(result_a) == _fingerprint(result_b)
    assert result_a.summary.total_findings == result_b.summary.total_findings == 42


def test_scanning_the_mock_system_never_modifies_it(tmp_path):
    import hashlib

    def _hash_tree(root: Path) -> dict:
        return {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }

    before = _hash_tree(MOCK_SYSTEM_PATH)
    _scan(tmp_path)
    after = _hash_tree(MOCK_SYSTEM_PATH)
    assert before == after
