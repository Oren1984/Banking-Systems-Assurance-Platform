from __future__ import annotations

import pytest

from core.config import Settings
from core.exceptions import PathValidationError
from scanners.path_validator import validate_scan_path


def test_fails_closed_when_no_allowed_paths_configured(tmp_path):
    settings = Settings(_env_file=None, allowed_scan_paths=[])
    with pytest.raises(PathValidationError, match="No allowed scan paths"):
        validate_scan_path(str(tmp_path), settings)


def test_accepts_path_within_allowlist(tmp_path):
    target = tmp_path / "project"
    target.mkdir()
    settings = Settings(_env_file=None, allowed_scan_paths=[str(tmp_path)])
    resolved = validate_scan_path(str(target), settings)
    assert resolved == target.resolve()


def test_rejects_path_outside_allowlist(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    settings = Settings(_env_file=None, allowed_scan_paths=[str(allowed)])
    with pytest.raises(PathValidationError, match="outside all allowed"):
        validate_scan_path(str(outside), settings)


def test_rejects_traversal_attempt(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    settings = Settings(_env_file=None, allowed_scan_paths=[str(allowed)])
    traversal = str(allowed / ".." / "outside")
    with pytest.raises(PathValidationError):
        validate_scan_path(traversal, settings)


def test_rejects_nonexistent_path(tmp_path):
    settings = Settings(_env_file=None, allowed_scan_paths=[str(tmp_path)])
    with pytest.raises(PathValidationError, match="does not exist"):
        validate_scan_path(str(tmp_path / "does_not_exist"), settings)
