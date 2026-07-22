from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_SCANNED_DIRS = ["scanners", "reporting", "storage", "core", "governance", "app", "ui"]

# BANKING_PLATFORM_INTEGRATION_PLAN.md Phase 2 brief, "Mandatory Security
# Requirements": unsafe YAML loading, pickle, eval, and exec are not used
# anywhere in the platform's own code (the scanners only ever read text
# and pattern-match it — see scanners/content_reader.py's module
# docstring). This is a static AST check, not a runtime guarantee, but it
# covers every code path, including ones no test happens to exercise.

_FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "pickle.load",
    "pickle.loads",
    "yaml.load",  # yaml.safe_load is fine and not flagged
}


def _iter_python_files():
    for top in _SCANNED_DIRS:
        top_dir = REPO_ROOT / top
        if not top_dir.exists():
            continue
        yield from top_dir.rglob("*.py")


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts = []
        cur = func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            return ".".join(reversed(parts))
    return None


def test_no_forbidden_deserialization_or_dynamic_execution_calls():
    violations = []
    for path in _iter_python_files():
        rel = path.relative_to(REPO_ROOT)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name is None:
                continue
            if name in _FORBIDDEN_CALLS:
                violations.append(f"{rel}:{node.lineno}: calls {name!r}")

    assert not violations, "Forbidden unsafe call found:\n" + "\n".join(violations)


def test_no_sql_execution_anywhere_in_scanner_rules():
    # scanners/rules/sql_scanner.py must detect SQL patterns via regex
    # only — it must never import a DB driver or call .execute()/.executemany().
    sql_scanner_dir = REPO_ROOT / "scanners" / "rules"
    violations = []
    for path in sql_scanner_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in ("execute", "executemany", "executescript"):
                violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: calls .{node.attr}(...)")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for n in names:
                    if n and n.split(".")[0] in ("sqlite3", "psycopg2", "pymysql", "pyodbc"):
                        violations.append(f"{path.relative_to(REPO_ROOT)}: imports {n!r}")

    assert not violations, "scanners/rules must never execute SQL:\n" + "\n".join(violations)
