from __future__ import annotations

from pathlib import Path

from core.config import Settings
from core.exceptions import PathValidationError
from core.logging import get_logger

# Adapted from ai-project-control-tower/app/scanner/path_validator.py (see
# BANKING_PLATFORM_INTEGRATION_PLAN.md §3: "Reuse as-is"). Settings are now
# passed explicitly rather than imported as a module-level singleton, so this
# function has no import-time dependency on environment state — needed for
# the fail-closed-by-default unit tests in tests/unit/test_path_validator.py.

logger = get_logger(__name__)


def validate_scan_path(requested_path: str, settings: Settings) -> Path:
    """
    Resolve to a canonical absolute path and verify it falls within an
    allowed scan path. Resolving first naturally blocks path-traversal
    (e.g. ../../) attempts. Fails closed: an empty allowlist is always
    rejected, never treated as "allow everything".
    """
    allowed_paths = settings.allowed_scan_paths

    if not allowed_paths:
        raise PathValidationError(
            "No allowed scan paths configured. Set ALLOWED_SCAN_PATHS in environment."
        )

    try:
        resolved = Path(requested_path).resolve()
    except Exception as exc:
        raise PathValidationError(f"Cannot resolve path '{requested_path}': {exc}") from exc

    if not resolved.exists():
        raise PathValidationError(f"Path does not exist: {resolved}")

    if not resolved.is_dir():
        raise PathValidationError(f"Path is not a directory: {resolved}")

    for allowed_raw in allowed_paths:
        try:
            allowed_resolved = Path(allowed_raw).resolve()
            resolved.relative_to(allowed_resolved)
            logger.debug("path_validated", path=str(resolved), allowed=str(allowed_resolved))
            return resolved
        except ValueError:
            continue

    raise PathValidationError(
        f"Path '{resolved}' is outside all allowed scan paths. Allowed: {allowed_paths}"
    )
