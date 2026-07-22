from __future__ import annotations

import logging
from pathlib import Path

from core.config import Settings
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "phase2_bank_fixture"

# The fixture's fake secret values (tests/fixtures/phase2_bank_fixture/README.md
# documents these are synthetic, not real). A full scan run must never emit
# any of them to the logging system, even though structlog processes every
# scanner-warning/error path during the run.
_RAW_FAKE_SECRETS = ["fake_super_secret_pw_1", "fake_plaintext_pw_1", "hunter2value123"]


def test_scan_never_logs_a_raw_secret_value(tmp_path, caplog):
    settings = Settings(
        _env_file=None,
        allowed_scan_paths=[str(FIXTURE_ROOT.parent)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
    )
    handle = ingest_local_directory(str(FIXTURE_ROOT), settings)
    with caplog.at_level(logging.DEBUG):
        try:
            run_scan(handle, settings)
        finally:
            handle.cleanup()

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    for secret in _RAW_FAKE_SECRETS:
        assert secret not in log_text
