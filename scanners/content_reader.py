from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.config import Settings
from core.logging import get_logger

logger = get_logger(__name__)

# Phase 2 — Safe Content Reader (BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2
# brief, §3). Reads text only, never executes, never imports, never
# evaluates. No YAML/JSON parsing happens here — that belongs to individual
# scanner rules, and when it does happen it must use `yaml.safe_load`
# (never `yaml.load`) and never `pickle`/`eval`/`exec` — enforced by
# tests/security/test_no_unsafe_deserialization.py.

_DEFAULT_MAX_READ_BYTES = 2_000_000  # 2 MB of text content per file, independent of file-size limits
_NULL_BYTE = b"\x00"
_BINARY_SNIFF_WINDOW = 8192


@dataclass
class ReadResult:
    text: str
    encoding_used: str
    truncated: bool
    line_count: int


class BinaryContentError(Exception):
    """Raised when a file that was expected to be text looks binary."""


def looks_binary(raw: bytes) -> bool:
    """Cheap, dependency-free binary sniff: a null byte in the first
    window is a strong binary signal (this is the same heuristic git
    itself uses)."""
    return _NULL_BYTE in raw[:_BINARY_SNIFF_WINDOW]


def read_text_safely(
    path: Path,
    settings: Settings,
    max_bytes: int = _DEFAULT_MAX_READ_BYTES,
) -> ReadResult:
    """
    Read a file as text, safely.

    - Opens in binary mode first to sniff for null bytes (binary content)
      before attempting any text decoding.
    - Tries utf-8 first, falls back to latin-1 (which never fails to
      decode — every byte sequence is valid latin-1) rather than guessing
      via a third-party charset-detection dependency.
    - Truncates to `max_bytes` of raw content before decoding, so a
      pathologically large single line cannot blow up memory even though
      scanners/file_discovery.py already caps file size.
    - Never executes, imports, or evaluates the content in any way.
    """
    with open(path, "rb") as f:
        raw = f.read(max_bytes + 1)

    truncated = len(raw) > max_bytes
    if truncated:
        raw = raw[:max_bytes]

    if looks_binary(raw):
        raise BinaryContentError(f"{path} appears to be binary content")

    try:
        text = raw.decode("utf-8")
        encoding_used = "utf-8"
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
        encoding_used = "latin-1"

    line_count = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    return ReadResult(text=text, encoding_used=encoding_used, truncated=truncated, line_count=line_count)


def line_for_offset(text: str, offset: int) -> int:
    """1-indexed line number containing character offset `offset` in `text`."""
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def sanitize_for_log(text: str, max_len: int = 200) -> str:
    """Truncate and strip newlines before content ever reaches a log line
    — content is untrusted input and must never expand a log record
    arbitrarily or inject fake log lines via embedded newlines."""
    single_line = text.replace("\n", "\\n").replace("\r", "\\r")
    if len(single_line) > max_len:
        return single_line[:max_len] + "...[truncated]"
    return single_line
