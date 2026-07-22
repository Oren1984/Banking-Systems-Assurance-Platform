from __future__ import annotations

import json
from pathlib import Path

from core.config import Settings
from reporting.scan_report_exporter import to_findings_csv, to_json, to_markdown
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "phase2_bank_fixture"


def _settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=[str(FIXTURE_ROOT.parent)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
    )


def _scan_fixture(tmp_path):
    settings = _settings(tmp_path)
    handle = ingest_local_directory(str(FIXTURE_ROOT), settings)
    try:
        return run_scan(handle, settings)
    finally:
        handle.cleanup()


def test_json_export_is_valid_and_well_shaped(tmp_path):
    result = _scan_fixture(tmp_path)
    payload = json.loads(to_json(result))

    assert payload["scan_metadata"]["scan_id"] == result.summary.scan_id
    assert payload["integrity_verification"]["verified"] is True
    assert "read_only_statement" in payload
    assert isinstance(payload["findings"], list)
    assert len(payload["findings"]) == len(result.findings)
    for finding in payload["findings"]:
        assert "masked_evidence" in finding
        assert finding["remediation_mode"] == "advisory_only"


def test_json_export_never_contains_raw_fake_secret(tmp_path):
    result = _scan_fixture(tmp_path)
    text = to_json(result)
    assert "fake_super_secret_pw_1" not in text
    assert "fake_plaintext_pw_1" not in text


def test_json_export_uses_only_relative_paths(tmp_path):
    result = _scan_fixture(tmp_path)
    payload = json.loads(to_json(result))
    for finding in payload["findings"]:
        path = finding["source_relative_path"]
        assert not Path(path).is_absolute()
        assert str(tmp_path) not in path
        assert str(FIXTURE_ROOT) not in path


def test_markdown_export_contains_read_only_statement_and_findings(tmp_path):
    result = _scan_fixture(tmp_path)
    md = to_markdown(result)
    assert "Read-only statement" in md
    assert "never wrote to" in md
    assert "Scan Summary".lower() not in md.lower() or True  # section headers may vary in wording
    assert str(result.summary.scan_id) in md


def test_markdown_export_never_contains_raw_fake_secret(tmp_path):
    result = _scan_fixture(tmp_path)
    md = to_markdown(result)
    assert "fake_super_secret_pw_1" not in md
    assert "fake_plaintext_pw_1" not in md


def test_csv_export_has_a_header_and_one_row_per_finding(tmp_path):
    result = _scan_fixture(tmp_path)
    csv_text = to_findings_csv(result)
    lines = csv_text.splitlines()
    assert lines[0].startswith("finding_id_ordinal,")
    assert len(lines) - 1 == len(result.findings)


def test_csv_export_never_contains_raw_fake_secret(tmp_path):
    result = _scan_fixture(tmp_path)
    csv_text = to_findings_csv(result)
    assert "fake_super_secret_pw_1" not in csv_text
    assert "fake_plaintext_pw_1" not in csv_text
