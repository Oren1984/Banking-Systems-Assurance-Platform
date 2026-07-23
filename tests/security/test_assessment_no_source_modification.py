from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from assessment.engine import run_assessment
from core.config import Settings
from storage.db.base import Base

# Phase 4 — extends tests/security/test_scan_no_source_modification.py's
# hash-comparison proof to the full assessment/engine.py orchestration
# layer (ingest -> scan -> persist -> score -> control-evaluate -> audit
# trail), not just the raw scanner
# (BANKING_PLATFORM_INTEGRATION_PLAN.md §12/§13 Phase 4: "Extend
# tests/e2e/test_original_repos_not_modified.py-style hash-comparison
# coverage to the full pipeline"). Persistence/scoring/control-evaluation
# code has no filesystem access to the scanned target at all — this test
# is the concrete proof, not just an architectural claim.

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "phase2_bank_fixture"


def _hash_tree(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def test_running_a_full_assessment_never_modifies_the_fixture(tmp_path):
    before = _hash_tree(FIXTURE_ROOT)

    settings = Settings(
        _env_file=None,
        allowed_scan_paths=[str(FIXTURE_ROOT.parent)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = run_assessment(str(FIXTURE_ROOT), settings, session)
        assert result.scan_result.summary.integrity_verified is True

    after = _hash_tree(FIXTURE_ROOT)
    assert before == after, "Running a full assessment modified, added, or removed a fixture file"


# Phase 5 — the same proof, specifically against mock_banking_system/, the
# actual Phase 5 demonstration target (BANKING_PLATFORM_INTEGRATION_PLAN.md
# §13 Phase 5 completion gate: "The read-only guarantee is re-proven").

MOCK_SYSTEM_ROOT = Path(__file__).resolve().parents[2] / "mock_banking_system"


def test_running_the_mock_banking_demo_assessment_never_modifies_the_fixture(tmp_path):
    before = _hash_tree(MOCK_SYSTEM_ROOT)

    settings = Settings(
        _env_file=None,
        allowed_scan_paths=[str(MOCK_SYSTEM_ROOT)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = run_assessment(str(MOCK_SYSTEM_ROOT), settings, session)
        assert result.scan_result.summary.integrity_verified is True
        assert result.scan_result.summary.total_findings == 42

    after = _hash_tree(MOCK_SYSTEM_ROOT)
    assert before == after, "Running the mock banking demo assessment modified, added, or removed a fixture file"
