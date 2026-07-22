from __future__ import annotations

import os

import pytest

from core.config import Settings
from models.enums import SkipReason
from scanners.file_discovery import compute_source_integrity_hash, discover_files


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_discovers_supported_files(tmp_path):
    (tmp_path / "main.py").write_text("print('hi')")
    (tmp_path / "notes.txt").write_text("hello")
    result = discover_files(tmp_path, _settings())
    paths = {i.relative_path for i in result.inventory}
    assert paths == {"main.py", "notes.txt"}
    assert result.total_files_found == 2


def test_ignores_default_ignored_directories(tmp_path):
    (tmp_path / "app.py").write_text("x = 1")
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "lib.js").write_text("var x = 1;")
    result = discover_files(tmp_path, _settings())
    paths = {i.relative_path for i in result.inventory}
    assert paths == {"app.py"}


def test_unsupported_extension_is_skipped(tmp_path):
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")
    result = discover_files(tmp_path, _settings())
    assert result.inventory == []
    assert result.skipped[0].reason == SkipReason.UNSUPPORTED_TYPE


def test_file_size_limit_is_enforced(tmp_path):
    big = tmp_path / "big.py"
    big.write_text("x" * 2000)
    result = discover_files(tmp_path, _settings(max_scan_file_size_bytes=100))
    assert result.inventory == []
    assert result.skipped[0].reason == SkipReason.SIZE_LIMIT


def test_total_size_limit_is_enforced(tmp_path):
    for i in range(3):
        (tmp_path / f"f{i}.py").write_text("x" * 500)
    result = discover_files(tmp_path, _settings(max_scan_total_size_bytes=600))
    assert result.truncated is True
    assert any(s.reason == SkipReason.TOTAL_SIZE_LIMIT for s in result.skipped)


def test_file_count_limit_is_enforced(tmp_path):
    for i in range(5):
        (tmp_path / f"f{i}.py").write_text("x")
    result = discover_files(tmp_path, _settings(max_scan_file_count=2))
    assert result.truncated is True
    assert any(s.reason == SkipReason.COUNT_LIMIT for s in result.skipped)


def test_depth_limit_is_enforced(tmp_path):
    nested = tmp_path
    for i in range(5):
        nested = nested / f"level{i}"
        nested.mkdir()
    (nested / "deep.py").write_text("x = 1")
    (tmp_path / "shallow.py").write_text("x = 1")
    result = discover_files(tmp_path, _settings(max_scan_depth=1))
    paths = {i.relative_path for i in result.inventory}
    assert "shallow.py" in paths
    assert not any("deep.py" in p for p in paths)


def test_symlinks_are_skipped_by_default(tmp_path):
    real_file = tmp_path / "real.py"
    real_file.write_text("x = 1")
    link = tmp_path / "link.py"
    try:
        os.symlink(real_file, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted in this environment")

    result = discover_files(tmp_path, _settings(scan_follow_symlinks=False))
    paths = {i.relative_path for i in result.inventory}
    assert "link.py" not in paths
    assert any(s.reason == SkipReason.SYMLINK for s in result.skipped)


def test_content_hash_is_deterministic(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    r1 = discover_files(tmp_path, _settings())
    r2 = discover_files(tmp_path, _settings())
    assert r1.inventory[0].content_hash == r2.inventory[0].content_hash


def test_inaccessible_directory_does_not_crash_discovery(tmp_path):
    # A file discovery run over an empty tree must not fail.
    result = discover_files(tmp_path, _settings())
    assert result.inventory == []
    assert result.skipped == []


def test_integrity_hash_changes_when_a_file_is_added(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    before = compute_source_integrity_hash(tmp_path)
    (tmp_path / "b.py").write_text("y = 2")
    after = compute_source_integrity_hash(tmp_path)
    assert before != after


def test_integrity_hash_stable_with_no_changes(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("y = 2")
    h1 = compute_source_integrity_hash(tmp_path)
    h2 = compute_source_integrity_hash(tmp_path)
    assert h1 == h2
