from __future__ import annotations

import pytest

from core.config import Settings
from scanners.content_reader import (
    BinaryContentError,
    line_for_offset,
    read_text_safely,
    sanitize_for_log,
)


def _settings() -> Settings:
    return Settings(_env_file=None)


def test_reads_utf8_text(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("héllo wörld", encoding="utf-8")
    result = read_text_safely(f, _settings())
    assert result.text == "héllo wörld"
    assert result.encoding_used == "utf-8"
    assert result.truncated is False


def test_falls_back_to_latin1_on_invalid_utf8(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"\xe9\xe8 latin text")  # invalid utf-8, valid latin-1
    result = read_text_safely(f, _settings())
    assert result.encoding_used == "latin-1"


def test_binary_content_raises(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"\x00\x01\x02binary")
    with pytest.raises(BinaryContentError):
        read_text_safely(f, _settings())


def test_truncates_large_content(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x" * 1000)
    result = read_text_safely(f, _settings(), max_bytes=100)
    assert result.truncated is True
    assert len(result.text) == 100


def test_line_for_offset():
    text = "line1\nline2\nline3"
    assert line_for_offset(text, 0) == 1
    assert line_for_offset(text, 6) == 2  # start of "line2"
    assert line_for_offset(text, 12) == 3  # start of "line3"


def test_line_for_offset_negative_offset_is_line_one():
    assert line_for_offset("abc", -1) == 1


def test_sanitize_for_log_strips_newlines_and_truncates():
    result = sanitize_for_log("line1\nline2\r\nline3", max_len=1000)
    assert "\n" not in result
    assert "\r" not in result
    assert "\\n" in result


def test_sanitize_for_log_truncates_long_content():
    result = sanitize_for_log("x" * 500, max_len=50)
    assert len(result) <= 50 + len("...[truncated]")
    assert result.endswith("...[truncated]")
