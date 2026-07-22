from __future__ import annotations

from core.config import Settings
from models.enums import ScanStatus
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory


def _settings(tmp_path, **overrides) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=[str(tmp_path)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
        **overrides,
    )


def test_run_scan_against_clean_project_produces_no_findings(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def add(a, b):\n    return a + b\n")
    settings = _settings(tmp_path)

    handle = ingest_local_directory(str(project), settings)
    try:
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    assert result.summary.status == ScanStatus.COMPLETED
    assert result.summary.integrity_verified is True
    assert result.summary.total_findings == 0
    assert result.summary.files_scanned == 1


def test_run_scan_detects_findings_and_preserves_source(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text('PASSWORD = "hunter2value123"\n')
    settings = _settings(tmp_path)
    original_content = (project / "app.py").read_bytes()

    handle = ingest_local_directory(str(project), settings)
    try:
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    assert result.summary.total_findings >= 1
    assert result.summary.integrity_verified is True
    assert (project / "app.py").read_bytes() == original_content  # never modified


def test_run_scan_marks_completed_with_warnings_when_truncated(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    for i in range(5):
        (project / f"f{i}.py").write_text("x = 1")
    settings = _settings(tmp_path, max_scan_file_count=2)

    handle = ingest_local_directory(str(project), settings)
    try:
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    assert result.summary.status == ScanStatus.COMPLETED_WITH_WARNINGS
    assert result.summary.truncated is True


def test_unreadable_file_does_not_fail_the_whole_scan(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "a.py").write_text("x = 1")
    (project / "b.py").write_text("y = 2")
    settings = _settings(tmp_path)

    handle = ingest_local_directory(str(project), settings)
    try:
        import scanners.scan_orchestrator as orch

        original_read = orch.read_text_safely
        call_count = {"n": 0}

        def flaky_read(path, settings_arg):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise OSError("simulated unreadable file")
            return original_read(path, settings_arg)

        monkeypatch.setattr(orch, "read_text_safely", flaky_read)
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    # The scan must complete despite one simulated per-file read failure
    # per scanner — this is exactly the "one unreadable file must not fail
    # the entire scan" requirement.
    assert result.summary.status in (ScanStatus.COMPLETED, ScanStatus.COMPLETED_WITH_WARNINGS)


def test_scan_id_and_domains_are_attached_to_findings(tmp_path):
    project = tmp_path / "project"
    (project / "app" / "payments").mkdir(parents=True)
    (project / "app" / "payments" / "processor.py").write_text('PASSWORD = "hunter2value123"\n')
    settings = _settings(tmp_path)

    handle = ingest_local_directory(str(project), settings)
    try:
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    assert len(result.findings) >= 1
    for f in result.findings:
        assert f.scan_id == result.summary.scan_id
    payments_findings = [f for f in result.findings if "payments" in f.source_relative_path]
    assert any("payments" in d for f in payments_findings for d in f.banking_domains)
