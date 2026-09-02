from __future__ import annotations

from pathlib import Path

from core.config import Settings
from core.domains import BankingDomain
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory

# Post-Phase-6 hardening recap — Candidate 1 ("Reference Banking System"),
# the second, well-governed demo fixture. Mirrors
# tests/unit/test_mock_banking_fixture.py's own pattern and rationale:
# every number asserted here was captured by actually running the real
# scanner/assessment pipeline against this exact fixture (see
# docs/reference_banking_system_findings.md, the authoritative record), not
# predicted by hand. This file does not touch mock_banking_system/ or any
# of its own pinned tests.

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_SYSTEM_PATH = REPO_ROOT / "reference_banking_system"


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=[str(REPO_ROOT)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
    )


def _scan(tmp_path):
    settings = _settings(tmp_path)
    handle = ingest_local_directory(str(REFERENCE_SYSTEM_PATH), settings)
    try:
        return run_scan(handle, settings)
    finally:
        handle.cleanup()


def test_no_real_secret_shaped_values_are_present_in_the_fixture():
    forbidden_substrings = ("BEGIN PRIVATE KEY", "BEGIN RSA PRIVATE KEY")
    for path in REFERENCE_SYSTEM_PATH.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for forbidden in forbidden_substrings:
            assert forbidden not in text, f"{path} contains a forbidden real-secret-shaped marker"


def test_scanning_the_reference_system_produces_exactly_one_finding(tmp_path):
    result = _scan(tmp_path)
    assert result.summary.total_findings == 1
    assert result.summary.integrity_verified is True
    assert result.summary.files_scanned == 11


def test_scanning_the_reference_system_severity_distribution(tmp_path):
    result = _scan(tmp_path)
    assert result.summary.findings_by_severity == {"low": 1}


def test_the_one_planted_finding_is_the_expected_low_severity_config_gap(tmp_path):
    result = _scan(tmp_path)
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.raw.rule_id == "CFG-008"
    assert finding.source_relative_path == "api/routes/openapi_routes.yml"


def test_scanning_the_reference_system_touches_exactly_five_domains(tmp_path):
    result = _scan(tmp_path)
    evaluated = set()
    for mappings in result.domain_mappings.values():
        for m in mappings:
            evaluated.add(m.domain.value)
    assert evaluated == {
        "application_security",
        "core_banking",
        "infrastructure_api_security",
        "model_ai_governance",
        "payments",
    }


def test_model_ai_governance_is_evaluated_here_unlike_the_mock_banking_system(tmp_path):
    # The contrast this fixture exists to demonstrate: mock_banking_system/
    # deliberately never evaluates this domain (see
    # test_mock_banking_fixture.py::test_model_ai_governance_has_zero_findings_and_zero_evaluated_files).
    # This fixture deliberately does, with zero findings.
    result = _scan(tmp_path)
    domain_findings = [
        f for f in result.findings if BankingDomain.MODEL_AI_GOVERNANCE.value in (f.banking_domains or [])
    ]
    assert domain_findings == []
    evaluated = {m.domain for mappings in result.domain_mappings.values() for m in mappings}
    assert BankingDomain.MODEL_AI_GOVERNANCE in evaluated


def test_designated_clean_files_produce_no_findings(tmp_path):
    result = _scan(tmp_path)
    findings_by_path: dict[str, list[str]] = {}
    for n in result.findings:
        findings_by_path.setdefault(n.source_relative_path, []).append(n.raw.rule_id)

    clean_files = [
        "app/security/access_control_policy.py",
        "app/security/encryption_config.py",
        "app/security/permission_review.py",
        "app/payments/payment_processor.py",
        "app/payments/settlement_service.py",
        "app/accounts/account_service.py",
        "app/accounts/statement_generator.py",
        "app/ml_model_risk/risk_scoring_model_notes.md",
        "infra/terraform/iam_policy.tf",
    ]
    for relative_path in clean_files:
        assert findings_by_path.get(relative_path, []) == [], (
            f"{relative_path} was expected to be a clean (no-finding) positive example"
        )


def test_scanning_the_reference_system_twice_is_deterministic(tmp_path):
    result_a = _scan(tmp_path)
    result_b = _scan(tmp_path)

    def _fingerprint(result):
        return sorted((n.raw.rule_id, n.raw.severity.value, n.source_relative_path) for n in result.findings)

    assert _fingerprint(result_a) == _fingerprint(result_b)
    assert result_a.summary.total_findings == result_b.summary.total_findings == 1


def test_scanning_the_reference_system_never_modifies_it(tmp_path):
    import hashlib

    def _hash_tree(root: Path) -> dict:
        return {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }

    before = _hash_tree(REFERENCE_SYSTEM_PATH)
    _scan(tmp_path)
    after = _hash_tree(REFERENCE_SYSTEM_PATH)
    assert before == after


def test_mock_banking_system_is_untouched_by_this_fixtures_existence():
    # This new fixture must never be nested inside, or otherwise alter,
    # mock_banking_system/ — see reference_banking_system/README.md's "Hard
    # rules". A cheap, direct structural guard.
    mock_system_path = REPO_ROOT / "mock_banking_system"
    assert not str(REFERENCE_SYSTEM_PATH).startswith(str(mock_system_path))
    assert not str(mock_system_path).startswith(str(REFERENCE_SYSTEM_PATH))
