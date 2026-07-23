from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from core.config import Settings
from core.exceptions import ConfigurationError
from scripts.seed_mock_banking_demo import seed
from storage.db.base import Base

# Phase 5 — scripts/seed_mock_banking_demo.py. Offline (SQLite) tests —
# live-PostgreSQL coverage is tests/integration/test_postgres_phase5_demo.py.

REPO_ROOT = Path(__file__).resolve().parents[2]


def _settings(tmp_path, **overrides) -> Settings:
    defaults = dict(
        _env_file=None,
        report_output_dir=str(tmp_path / "reports"),
        allowed_scan_paths=[str(REPO_ROOT)],
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _engine_and_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'seed_test.db'}")
    Base.metadata.create_all(engine)
    return engine, Session(engine)


def test_seed_requires_database_url_when_no_session_given(tmp_path):
    with pytest.raises(ConfigurationError):
        seed(settings=_settings(tmp_path))


def test_seed_runs_a_full_assessment_and_returns_a_summary(tmp_path):
    _, session = _engine_and_session(tmp_path)
    result = seed(settings=_settings(tmp_path), session=session)
    assert result["implemented"] is True
    assert result["findings_count"] == 42
    assert result["scores_count"] == 16
    assert result["control_evaluations_count"] == 68
    assert result["recommendations_count"] == 42
    assert result["audit_events_count"] == 4


def test_seed_writes_sample_exports_outside_the_scanned_tree(tmp_path):
    _, session = _engine_and_session(tmp_path)
    settings = _settings(tmp_path)
    result = seed(settings=settings, session=session)

    export_dir = Path(settings.report_output_dir) / "mock_banking_demo"
    json_path = export_dir / "latest_assessment.json"
    md_path = export_dir / "latest_assessment.md"
    assert json_path.exists()
    assert md_path.exists()
    assert result["sample_exports"] == [str(json_path), str(md_path)]

    # The export directory must never be inside mock_banking_system/ — see
    # docs/mock_banking_planted_findings.md and this module's own docstring
    # for why (a report scanned alongside the fixture that produced it
    # would corrupt the fixture's own deterministic finding count).
    mock_system_root = Path(__file__).resolve().parents[2] / "mock_banking_system"
    assert mock_system_root not in export_dir.parents and export_dir != mock_system_root


def test_seed_exports_never_contain_a_raw_planted_secret(tmp_path):
    _, session = _engine_and_session(tmp_path)
    settings = _settings(tmp_path)
    seed(settings=settings, session=session)

    export_dir = Path(settings.report_output_dir) / "mock_banking_demo"
    json_text = (export_dir / "latest_assessment.json").read_text(encoding="utf-8")
    md_text = (export_dir / "latest_assessment.md").read_text(encoding="utf-8")
    for raw_secret in ("fake_demo_secret_pw_9f2c", "fake-demo-gateway-key-abcXYZ123demo", "fake_demo_plaintext_pw_7c1a"):
        assert raw_secret not in json_text
        assert raw_secret not in md_text


def test_seed_is_safe_to_run_twice_and_creates_two_historical_scans(tmp_path):
    engine, session1 = _engine_and_session(tmp_path)
    settings = _settings(tmp_path)
    result1 = seed(settings=settings, session=session1)

    session2 = Session(engine)
    result2 = seed(settings=settings, session=session2)

    assert result1["scan_id"] != result2["scan_id"]
    assert result1["findings_count"] == result2["findings_count"] == 42


def test_seed_uses_the_configured_mock_path_from_the_allowlist(tmp_path):
    _, session = _engine_and_session(tmp_path)
    settings = _settings(tmp_path)
    result = seed(settings=settings, session=session)
    assert result["findings_count"] == 42
    assert settings.mock_banking_system_path == str(REPO_ROOT / "mock_banking_system")


def test_seed_does_not_bypass_allowed_scan_paths(tmp_path):
    _, session = _engine_and_session(tmp_path)
    settings = _settings(tmp_path, allowed_scan_paths=[str(tmp_path)])
    with pytest.raises(Exception, match="outside all allowed scan paths"):
        seed(settings=settings, session=session)
