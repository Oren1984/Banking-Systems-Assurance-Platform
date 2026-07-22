from __future__ import annotations

import pytest

from core.exceptions import ValidationError
from governance.file_validation import validate_file


def test_accepts_allowed_extension():
    name = validate_file("policy.pdf", file_size_bytes=1000)
    assert name == "policy.pdf"


def test_rejects_disallowed_extension():
    with pytest.raises(ValidationError, match="not allowed"):
        validate_file("script.py", file_size_bytes=100)


def test_rejects_oversized_file():
    with pytest.raises(ValidationError, match="exceeds"):
        validate_file("policy.pdf", file_size_bytes=20 * 1024 * 1024, max_upload_mb=10)


def test_strips_directory_traversal_from_filename():
    name = validate_file("../../etc/passwd_policy.txt", file_size_bytes=10)
    assert "/" not in name
    assert ".." not in name


def test_rejects_empty_filename():
    with pytest.raises(ValidationError, match="empty"):
        validate_file("", file_size_bytes=10)
