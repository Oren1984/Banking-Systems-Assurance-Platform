from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = Path(__file__).resolve().parent / "fixtures" / "original_repos_baseline.json"
EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".mypy_cache"}

# Byte-for-byte hash-comparison pattern, adapted from
# ai-project-control-tower/tests/e2e/test_no_repo_modification.py (see
# BANKING_PLATFORM_INTEGRATION_PLAN.md §3: "Reuse as-is"). The baseline
# manifest (tests/e2e/fixtures/original_repos_baseline.json) was generated
# by hashing all three legacy repositories at the start of Phase 1
# implementation, before any platform code was written. This test proves
# that building the new platform did not write, delete, or rename a single
# file inside any of the three source repositories.


def _hash_repo(repo_name: str) -> dict:
    repo_dir = REPO_ROOT / repo_name
    files = {}
    for root, dirs, filenames in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fn in filenames:
            path = Path(root) / fn
            rel = path.relative_to(repo_dir).as_posix()
            files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def _load_baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def test_baseline_manifest_exists():
    assert BASELINE_PATH.exists(), (
        "Baseline manifest missing — regenerate before trusting this test's result."
    )


def test_no_files_added_removed_or_changed_in_rag_engineering_lab():
    _assert_repo_unchanged("RAG-Engineering-Lab")


def test_no_files_added_removed_or_changed_in_control_tower():
    _assert_repo_unchanged("ai-project-control-tower")


def test_no_files_added_removed_or_changed_in_scope_guard():
    _assert_repo_unchanged("AI-Project-Scope-Guard")


def _assert_repo_unchanged(repo_name: str) -> None:
    baseline = _load_baseline()[repo_name]["files"]
    current = _hash_repo(repo_name)

    added = sorted(set(current) - set(baseline))
    removed = sorted(set(baseline) - set(current))
    changed = sorted(
        path for path in (set(current) & set(baseline)) if current[path] != baseline[path]
    )

    assert not added, f"{repo_name}: unexpected new files: {added}"
    assert not removed, f"{repo_name}: unexpected missing files: {removed}"
    assert not changed, f"{repo_name}: unexpected content changes: {changed}"
