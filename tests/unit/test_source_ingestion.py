from __future__ import annotations

import zipfile

import pytest

from core.config import Settings
from core.exceptions import PathValidationError, SourceIngestionError
from scanners.source_ingestion import ingest_local_directory, ingest_zip_archive


def _settings(tmp_path, allowed=None, **overrides) -> Settings:
    return Settings(
        _env_file=None,
        allowed_scan_paths=allowed if allowed is not None else [str(tmp_path)],
        scan_temp_dir=str(tmp_path / "scan_tmp"),
        **overrides,
    )


def test_ingest_local_directory_accepts_allowed_path(tmp_path):
    target = tmp_path / "project"
    target.mkdir()
    (target / "file.py").write_text("print('hi')")
    settings = _settings(tmp_path)

    handle = ingest_local_directory(str(target), settings)
    assert handle.root == target.resolve()
    assert handle.source_type == "directory"
    assert handle.is_temporary is False
    handle.cleanup()
    assert target.exists()  # cleanup() must never touch a plain directory source


def test_ingest_local_directory_rejects_outside_allowlist(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    settings = _settings(tmp_path, allowed=[str(allowed)])

    with pytest.raises(PathValidationError):
        ingest_local_directory(str(outside), settings)


def test_ingest_zip_archive_extracts_safely(tmp_path):
    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("app/main.py", "print('hello')")
        zf.writestr("README.md", "# fake")
    settings = _settings(tmp_path)

    handle = ingest_zip_archive(str(zip_path), settings)
    try:
        assert handle.source_type == "archive"
        assert handle.is_temporary is True
        assert (handle.root / "app" / "main.py").read_text() == "print('hello')"
    finally:
        handle.cleanup()
    assert not handle.root.exists()  # cleanup() must remove the temp extraction dir


def test_ingest_zip_archive_rejects_zip_slip(tmp_path):
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../etc/passwd", "malicious")
    settings = _settings(tmp_path)

    with pytest.raises(SourceIngestionError, match="traversal"):
        ingest_zip_archive(str(zip_path), settings)


def test_ingest_zip_archive_rejects_absolute_path_entry(tmp_path):
    zip_path = tmp_path / "evil_abs.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("/etc/passwd", "malicious")
    settings = _settings(tmp_path)

    with pytest.raises(SourceIngestionError, match="absolute path"):
        ingest_zip_archive(str(zip_path), settings)


def test_ingest_zip_archive_rejects_windows_absolute_path_entry(tmp_path):
    zip_path = tmp_path / "evil_win.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("C:\\Windows\\System32\\evil.dll", "malicious")
    settings = _settings(tmp_path)

    with pytest.raises(SourceIngestionError, match="absolute path"):
        ingest_zip_archive(str(zip_path), settings)


def test_ingest_zip_archive_rejects_excessive_entry_count(tmp_path):
    zip_path = tmp_path / "many_entries.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for i in range(5):
            zf.writestr(f"file_{i}.txt", "x")
    settings = _settings(tmp_path, max_archive_entry_count=2)

    with pytest.raises(SourceIngestionError, match="entries"):
        ingest_zip_archive(str(zip_path), settings)


def test_ingest_zip_archive_rejects_excessive_total_uncompressed_size(tmp_path):
    zip_path = tmp_path / "big.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        # Uncompressed (STORED) so the compression-ratio check doesn't
        # trigger first — isolates the total-uncompressed-size check.
        zf.writestr("big.txt", "a" * 5000)
    settings = _settings(tmp_path, max_archive_uncompressed_bytes=1000)

    with pytest.raises(SourceIngestionError, match="expand"):
        ingest_zip_archive(str(zip_path), settings)


def test_ingest_zip_archive_rejects_suspicious_compression_ratio(tmp_path):
    zip_path = tmp_path / "bomb.zip"
    # Highly compressible content produces a large compression ratio —
    # simulates the shape of a zip-bomb entry without needing gigabytes.
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bomb.txt", "0" * 2_000_000)
    settings = _settings(tmp_path, max_archive_compression_ratio=10, max_archive_uncompressed_bytes=10_000_000)

    with pytest.raises(SourceIngestionError, match="compression ratio"):
        ingest_zip_archive(str(zip_path), settings)


def test_ingest_zip_archive_rejects_non_zip_file(tmp_path):
    fake_zip = tmp_path / "not_a_zip.zip"
    fake_zip.write_text("this is not a zip file")
    settings = _settings(tmp_path)

    with pytest.raises(SourceIngestionError, match="valid zip"):
        ingest_zip_archive(str(fake_zip), settings)


def test_ingest_zip_archive_rejects_missing_file(tmp_path):
    settings = _settings(tmp_path)
    with pytest.raises(SourceIngestionError, match="not found"):
        ingest_zip_archive(str(tmp_path / "does_not_exist.zip"), settings)
