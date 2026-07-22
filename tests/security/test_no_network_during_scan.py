from __future__ import annotations

import socket
from pathlib import Path

from core.config import Settings
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "phase2_bank_fixture"


def test_no_socket_is_ever_opened_during_a_full_scan(tmp_path, monkeypatch):
    def _blocked_socket(*args, **kwargs):
        raise AssertionError("A socket was opened during a read-only local scan — network access is prohibited")

    monkeypatch.setattr(socket, "socket", _blocked_socket)

    settings = Settings(
        _env_file=None,
        allowed_scan_paths=[str(FIXTURE_ROOT.parent)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
    )
    handle = ingest_local_directory(str(FIXTURE_ROOT), settings)
    try:
        result = run_scan(handle, settings)
    finally:
        handle.cleanup()

    assert result.summary.total_findings > 0  # scan still ran to completion with no network
