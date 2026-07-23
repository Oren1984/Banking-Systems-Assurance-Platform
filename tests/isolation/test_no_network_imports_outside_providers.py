from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Modules allowed to import network-client / external-provider-SDK
# libraries. Only providers/ may do this (BANKING_PLATFORM_INTEGRATION_PLAN.md
# §6/§7: "only providers/*_adapter.py modules are permitted to import
# network client libraries"). Everything else in the new platform code must
# stay import-clean of these.
_ALLOWED_DIRS = {"providers"}

_NETWORK_MODULES = {
    "requests",
    "httpx",
    "urllib3",
    "openai",
    "anthropic",
    "google.generativeai",
    "aiohttp",
}

# Only scan the new platform's own top-level packages — not the three
# untouched legacy repositories, not tests/ or scripts/ themselves.
_SCANNED_TOP_LEVEL_DIRS = [
    "core",
    "governance",
    "scanners",
    "rag",
    "models",
    "storage",
    "app",
    "config",
    "reporting",
    # Phase 3/4 additions — these packages are exactly as deterministic and
    # local-only as everything above; extended here to close a gap where
    # they were added to the platform without being added to this scan list.
    "controls",
    "evidence",
    "scoring",
    "assessment",
    # Phase 5 additions — ui/services (no Streamlit-side network calls of
    # its own; only ever talks to the local database) and the demo seed
    # script.
    "ui",
    "scripts",
    # Phase 6 addition — the optional agent boundary. Deliberately scanned
    # here too: agents/ orchestrates providers/ (the one directory allowed
    # to import a network client) but must never import one directly
    # itself — every outbound call, if one is ever really implemented,
    # must go through a provider adapter, not agents/ reaching around it.
    "agents",
]


def _iter_python_files():
    for top in _SCANNED_TOP_LEVEL_DIRS:
        top_dir = REPO_ROOT / top
        if not top_dir.exists():
            continue
        yield from top_dir.rglob("*.py")


def _imported_module_names(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_no_disallowed_module_imports_network_clients():
    violations = []
    for path in _iter_python_files():
        rel = path.relative_to(REPO_ROOT)
        top_level_dir = rel.parts[0]
        if top_level_dir in _ALLOWED_DIRS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module_name in _imported_module_names(tree):
            root_module = module_name.split(".")[0]
            full_prefix_hit = any(
                module_name == m or module_name.startswith(m + ".") for m in _NETWORK_MODULES
            )
            if root_module in _NETWORK_MODULES or full_prefix_hit:
                violations.append(f"{rel}: imports {module_name!r}")

    assert not violations, "Network-client imports found outside providers/:\n" + "\n".join(
        violations
    )
