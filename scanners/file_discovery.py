from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

from core.config import Settings
from core.logging import get_logger
from models.enums import SkipReason

logger = get_logger(__name__)

# Phase 2 — File Discovery and Inventory (BANKING_PLATFORM_INTEGRATION_PLAN.md
# Phase 2 brief, §2). Read-only: only ever opens files in "rb" mode to hash
# them, never writes, never touches timestamps.

DEFAULT_IGNORED_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".github",
        "node_modules",
        "venv",
        ".venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "coverage",
        "dist",
        "build",
        "target",
        "bin",
        "obj",
        ".idea",
        ".vscode",
        ".tox",
        ".eggs",
        "htmlcov",
    }
)

DEFAULT_IGNORED_FILE_NAMES: frozenset[str] = frozenset({".coverage", ".DS_Store", "Thumbs.db"})

# Extensions this platform will attempt to read as text. Deliberately does
# not include binary formats — see governance/file_validation.py and
# scanners/content_reader.py for why unsafe binary parsing is out of scope.
SUPPORTED_TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".cs",
        ".go",
        ".sh",
        ".bash",
        ".ps1",
        ".sql",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".md",
        ".txt",
        ".csv",
        ".tf",
        ".tfvars",
        ".env",
        ".properties",
        ".dockerfile",
    }
)

# Filenames without a matching extension that are still supported text.
SUPPORTED_TEXT_FILENAMES: frozenset[str] = frozenset(
    {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", "Makefile"}
)


@dataclass
class FileInventoryItem:
    """One discovered, successfully hashed, in-scope file. This is the
    Phase 2 pipeline's in-memory record — scanners/scan_orchestrator.py
    persists it as storage/db/models/file_inventory.py::FileInventoryRecord.
    Kept separate deliberately: this dataclass has no database/session
    dependency, so file_discovery.py can be unit-tested with zero I/O
    beyond the filesystem itself."""

    relative_path: str
    file_name: str
    extension: str
    size_bytes: int
    content_hash: str
    is_supported: bool
    metadata: dict = field(default_factory=dict)


@dataclass
class SkippedFile:
    """A file that was found but not included in the inventory, and why."""

    relative_path: str
    reason: SkipReason
    detail: str = ""


@dataclass
class DiscoveryResult:
    inventory: list[FileInventoryItem]
    skipped: list[SkippedFile]
    total_files_found: int
    total_bytes_scanned: int
    truncated: bool  # True if a count/size/depth limit stopped discovery early


def is_supported_file(path: Path) -> bool:
    if path.name in SUPPORTED_TEXT_FILENAMES:
        return True
    return path.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS


def discover_files(
    root: Path,
    settings: Settings,
    ignored_dir_names: frozenset[str] = DEFAULT_IGNORED_DIR_NAMES,
) -> DiscoveryResult:
    """
    Recursively walk `root`, respecting ignore rules and the configured
    depth/count/size limits. Never follows symlinks unless
    settings.scan_follow_symlinks is explicitly True (default False).
    """
    root = root.resolve()
    inventory: list[FileInventoryItem] = []
    skipped: list[SkippedFile] = []
    total_files_found = 0
    total_bytes_scanned = 0
    truncated = False

    for current_dir, dir_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current_dir)
        depth = len(current_path.relative_to(root).parts)

        if depth > settings.max_scan_depth:
            dir_names[:] = []
            continue

        # Prune ignored directories in place so os.walk doesn't descend into them.
        dir_names[:] = [d for d in dir_names if d not in ignored_dir_names]

        for file_name in sorted(file_names):
            if file_name in DEFAULT_IGNORED_FILE_NAMES:
                continue

            total_files_found += 1
            file_path = current_path / file_name
            rel_path = file_path.relative_to(root).as_posix()

            if total_files_found > settings.max_scan_file_count:
                skipped.append(
                    SkippedFile(rel_path, SkipReason.COUNT_LIMIT, "max_scan_file_count exceeded")
                )
                truncated = True
                continue

            try:
                if file_path.is_symlink():
                    if not settings.scan_follow_symlinks:
                        skipped.append(
                            SkippedFile(rel_path, SkipReason.SYMLINK, "symlinks are not followed by default")
                        )
                        continue
                    # Even if allowed, refuse to follow a symlink that escapes root.
                    resolved_target = file_path.resolve()
                    if root not in resolved_target.parents and resolved_target != root:
                        skipped.append(
                            SkippedFile(rel_path, SkipReason.SYMLINK, "symlink target escapes scan root")
                        )
                        continue

                st = file_path.stat()
            except OSError as exc:
                skipped.append(SkippedFile(rel_path, SkipReason.UNREADABLE, str(exc)))
                continue

            if st.st_size > settings.max_scan_file_size_bytes:
                skipped.append(
                    SkippedFile(
                        rel_path,
                        SkipReason.SIZE_LIMIT,
                        f"{st.st_size} bytes exceeds max_scan_file_size_bytes",
                    )
                )
                continue

            if total_bytes_scanned + st.st_size > settings.max_scan_total_size_bytes:
                skipped.append(
                    SkippedFile(rel_path, SkipReason.TOTAL_SIZE_LIMIT, "max_scan_total_size_bytes exceeded")
                )
                truncated = True
                continue

            if not is_supported_file(file_path):
                skipped.append(SkippedFile(rel_path, SkipReason.UNSUPPORTED_TYPE, "extension not supported"))
                continue

            try:
                content_hash = _hash_file(file_path)
            except OSError as exc:
                skipped.append(SkippedFile(rel_path, SkipReason.UNREADABLE, str(exc)))
                continue

            total_bytes_scanned += st.st_size
            inventory.append(
                FileInventoryItem(
                    relative_path=rel_path,
                    file_name=file_name,
                    extension=file_path.suffix.lower(),
                    size_bytes=st.st_size,
                    content_hash=content_hash,
                    is_supported=True,
                )
            )

    return DiscoveryResult(
        inventory=inventory,
        skipped=skipped,
        total_files_found=total_files_found,
        total_bytes_scanned=total_bytes_scanned,
        truncated=truncated,
    )


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_source_integrity_hash(
    root: Path,
    ignored_dir_names: frozenset[str] = DEFAULT_IGNORED_DIR_NAMES,
) -> str:
    """
    A single aggregate hash over every regular file under `root` (pruning
    the same ignored directories as discover_files, but with no size/count
    limits — this is an integrity check, not a scan). Computed before and
    after a scan by scanners/scan_orchestrator.py to prove the scan never
    wrote to the source. Same technique as
    tests/e2e/test_original_repos_not_modified.py's baseline manifest:
    sorted "relative_path:sha256" lines, hashed together.
    """
    root = root.resolve()
    entries: list[str] = []
    for current_dir, dir_names, file_names in os.walk(root, followlinks=False):
        dir_names[:] = [d for d in dir_names if d not in ignored_dir_names]
        for file_name in file_names:
            file_path = Path(current_dir) / file_name
            rel = file_path.relative_to(root).as_posix()
            try:
                if file_path.is_symlink():
                    entries.append(f"{rel}:symlink")
                    continue
                entries.append(f"{rel}:{_hash_file(file_path)}")
            except OSError:
                entries.append(f"{rel}:unreadable")
    entries.sort()
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
