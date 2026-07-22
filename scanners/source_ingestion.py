from __future__ import annotations

import shutil
import stat
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from core.config import Settings
from core.exceptions import SourceIngestionError
from core.logging import get_logger
from scanners.path_validator import validate_scan_path

logger = get_logger(__name__)

# Phase 2 — Local Source Ingestion (BANKING_PLATFORM_INTEGRATION_PLAN.md
# Phase 2 brief, §1). Accepts an already-approved local directory or a ZIP
# archive and produces a SourceHandle pointing at a read-only-safe root to
# scan. Never modifies the original source. ZIP extraction always goes to
# an isolated temp directory under settings.scan_temp_dir, cleaned up by
# the caller via SourceHandle.cleanup().


@dataclass
class SourceHandle:
    """A validated, ready-to-scan source root.

    `is_temporary` is True only for extracted archives — `cleanup()` is a
    no-op for a plain local directory (its original files are never
    touched, and there is nothing to remove).
    """

    root: Path
    source_type: str  # "directory" | "archive"
    is_temporary: bool
    original_path: Path

    def cleanup(self) -> None:
        if self.is_temporary and self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)


def ingest_local_directory(path: str, settings: Settings) -> SourceHandle:
    """Validate and accept an already-approved local directory as a scan source."""
    resolved = validate_scan_path(path, settings)
    return SourceHandle(
        root=resolved,
        source_type="directory",
        is_temporary=False,
        original_path=resolved,
    )


def ingest_zip_archive(path: str, settings: Settings) -> SourceHandle:
    """
    Validate and safely extract a ZIP archive into an isolated temp
    directory. Rejects Zip Slip, path traversal, absolute paths, symlink
    abuse, and archive-bomb patterns before writing a single file.
    """
    archive_path = validate_scan_path(str(Path(path).parent), settings) / Path(path).name
    if not archive_path.is_file():
        raise SourceIngestionError(f"Archive not found: {archive_path}")
    if archive_path.suffix.lower() != ".zip":
        raise SourceIngestionError(f"Only .zip archives are supported, got: {archive_path.suffix}")

    if not zipfile.is_zipfile(archive_path):
        raise SourceIngestionError(f"Not a valid zip archive: {archive_path}")

    temp_root = Path(settings.scan_temp_dir).resolve()
    temp_root.mkdir(parents=True, exist_ok=True)
    extract_dir = temp_root / f"scan_{uuid.uuid4().hex}"
    extract_dir.mkdir(parents=True, exist_ok=False)

    try:
        with zipfile.ZipFile(archive_path) as zf:
            _validate_archive_members(zf, settings)
            _safe_extract(zf, extract_dir)
    except SourceIngestionError:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise SourceIngestionError(f"Failed to extract archive: {exc}") from exc

    return SourceHandle(
        root=extract_dir,
        source_type="archive",
        is_temporary=True,
        original_path=archive_path,
    )


def _validate_archive_members(zf: zipfile.ZipFile, settings: Settings) -> None:
    infos = zf.infolist()

    if len(infos) > settings.max_archive_entry_count:
        raise SourceIngestionError(
            f"Archive has {len(infos)} entries, exceeding the limit of "
            f"{settings.max_archive_entry_count} (possible archive bomb)."
        )

    total_uncompressed = 0
    for info in infos:
        _reject_unsafe_member_name(info.filename)

        # Zip-bomb heuristic: reject any single entry whose uncompressed
        # size vastly exceeds its compressed size.
        if info.compress_size > 0:
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > settings.max_archive_compression_ratio:
                raise SourceIngestionError(
                    f"Archive entry '{info.filename}' has a suspicious "
                    f"compression ratio ({ratio:.0f}x) — rejected as a "
                    f"possible archive bomb."
                )

        # Symlink abuse: reject entries whose external_attr Unix mode bits
        # indicate a symbolic link.
        unix_mode = info.external_attr >> 16
        if stat.S_ISLNK(unix_mode):
            raise SourceIngestionError(
                f"Archive entry '{info.filename}' is a symbolic link — not permitted."
            )

        total_uncompressed += info.file_size

    if total_uncompressed > settings.max_archive_uncompressed_bytes:
        raise SourceIngestionError(
            f"Archive would expand to {total_uncompressed} bytes, exceeding the "
            f"limit of {settings.max_archive_uncompressed_bytes} bytes."
        )


def _reject_unsafe_member_name(name: str) -> None:
    if not name or name.strip() == "":
        raise SourceIngestionError("Archive contains an entry with an empty name.")
    if name.startswith("/") or name.startswith("\\"):
        raise SourceIngestionError(f"Archive entry uses an absolute path: {name!r}")
    # Windows drive-letter absolute path, e.g. "C:\\..."
    if len(name) > 1 and name[1] == ":":
        raise SourceIngestionError(f"Archive entry uses an absolute path: {name!r}")
    normalized = name.replace("\\", "/")
    parts = normalized.split("/")
    if ".." in parts:
        raise SourceIngestionError(f"Archive entry attempts path traversal: {name!r}")


def _safe_extract(zf: zipfile.ZipFile, extract_dir: Path) -> None:
    extract_dir_resolved = extract_dir.resolve()
    for info in zf.infolist():
        if info.is_dir():
            continue
        target = (extract_dir_resolved / info.filename).resolve()
        # Defense in depth: even though _validate_archive_members already
        # rejected traversal/absolute-path names, re-verify the resolved
        # path is still inside extract_dir before writing.
        if extract_dir_resolved not in target.parents and target != extract_dir_resolved:
            raise SourceIngestionError(
                f"Archive entry resolves outside the extraction root: {info.filename!r}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)


def make_temp_dir(settings: Settings) -> Path:
    """Create and return a fresh isolated temp directory under scan_temp_dir."""
    root = Path(settings.scan_temp_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="scan_", dir=str(root)))
