from __future__ import annotations

from pathlib import Path

from core.config import Settings
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "phase2_bank_fixture"


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=[str(FIXTURE_ROOT.parent)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
    )


def test_full_scan_of_synthetic_fixture_produces_expected_categories(tmp_path):
    settings = _settings(tmp_path)
    handle = ingest_local_directory(str(FIXTURE_ROOT), settings)
    try:
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    assert result.summary.integrity_verified is True
    assert result.summary.files_scanned > 0
    assert result.summary.total_findings > 0

    categories_found = {f.raw.category.value for f in result.findings}
    expected = {
        "secret_exposure",
        "pii_exposure",
        "unsafe_logging",
        "audit_gap",
        "broad_permissions",
        "unsafe_sql",
        "insecure_configuration",
        "unsupported_sensitive_file",
    }
    missing = expected - categories_found
    assert not missing, f"Expected scanner categories not triggered by the fixture: {missing}"


def test_full_scan_maps_findings_to_approved_domains_only(tmp_path):
    from core.domains import BankingDomain

    settings = _settings(tmp_path)
    handle = ingest_local_directory(str(FIXTURE_ROOT), settings)
    try:
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    approved_values = {d.value for d in BankingDomain}
    for f in result.findings:
        for domain in f.banking_domains:
            assert domain in approved_values


def test_full_scan_true_negative_approve_loan_has_no_audit_gap_finding(tmp_path):
    settings = _settings(tmp_path)
    handle = ingest_local_directory(str(FIXTURE_ROOT), settings)
    try:
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    loan_audit_gap_findings = [
        f
        for f in result.findings
        if "loan_approval.py" in f.source_relative_path and f.raw.rule_id == "AUDIT-002"
    ]
    assert loan_audit_gap_findings == []


def test_full_scan_flags_transfer_funds_missing_audit(tmp_path):
    settings = _settings(tmp_path)
    handle = ingest_local_directory(str(FIXTURE_ROOT), settings)
    try:
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    transfer_findings = [
        f
        for f in result.findings
        if "account_service.py" in f.source_relative_path and f.raw.rule_id == "AUDIT-002"
    ]
    assert len(transfer_findings) >= 1


def test_full_scan_never_leaks_raw_fake_secret_values(tmp_path):
    settings = _settings(tmp_path)
    handle = ingest_local_directory(str(FIXTURE_ROOT), settings)
    try:
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    raw_secret_fragments = ["fake_super_secret_pw_1", "fake_plaintext_pw_1"]
    for f in result.findings:
        for fragment in raw_secret_fragments:
            assert fragment not in f.raw.masked_evidence
            assert fragment not in f.raw.description
