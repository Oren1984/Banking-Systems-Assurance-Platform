from __future__ import annotations

import hashlib
from pathlib import Path

from core.config import Settings
from scanners.scan_orchestrator import run_scan
from scanners.source_ingestion import ingest_local_directory

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "phase2_bank_fixture"


def _hash_tree(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def test_scanning_the_synthetic_fixture_never_modifies_it(tmp_path):
    before = _hash_tree(FIXTURE_ROOT)

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

    after = _hash_tree(FIXTURE_ROOT)

    assert before == after, "Scanning modified, added, or removed a file in the fixture tree"
    assert result.summary.integrity_verified is True
    assert result.summary.source_hash_before == result.summary.source_hash_after


def test_scanning_a_zip_archive_never_modifies_the_original_zip(tmp_path):
    import zipfile

    from scanners.source_ingestion import ingest_zip_archive

    zip_path = tmp_path / "src" / "archive.zip"
    zip_path.parent.mkdir()
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("app.py", "x = 1\n")
    original_bytes = zip_path.read_bytes()

    settings = Settings(
        _env_file=None,
        allowed_scan_paths=[str(tmp_path)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
    )
    handle = ingest_zip_archive(str(zip_path), settings)
    try:
        run_scan(handle, settings)
    finally:
        handle.cleanup()

    assert zip_path.read_bytes() == original_bytes
    assert not handle.root.exists()  # temp extraction dir was cleaned up
