from __future__ import annotations

from typing import Iterator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import Settings
from core.exceptions import ConfigurationError
from core.logging import get_logger

_logger = get_logger(__name__)

# Adapted from ai-project-control-tower/app/db/session.py (see
# BANKING_PLATFORM_INTEGRATION_PLAN.md §3: "Reuse with minor adaptation").
#
# Deliberate structural deviation from the source pattern: the source
# module creates `engine = create_engine(settings.database_url, ...)` eagerly
# at import time, which only worked because its Settings.database_url had a
# (insecure) default value. This platform's core.config.Settings.database_url
# has no default — engine creation is lazy instead, so importing this module
# never requires DATABASE_URL to be set, and a clear ConfigurationError is
# raised only when a session is actually requested without one configured.
# This is required for local imports/startup to not need a live database
# (see tests/unit/test_no_import_side_effects.py).

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine(settings: Settings) -> Engine:
    global _engine
    if not settings.database_url:
        raise ConfigurationError(
            "DATABASE_URL is not configured. Set it explicitly — no default "
            "credential is provided, by design (see core/config.py)."
        )
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_sessionmaker(settings: Settings) -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=get_engine(settings)
        )
    return _SessionLocal


def get_db(settings: Settings) -> Iterator[Session]:
    session_factory = get_sessionmaker(settings)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def check_database_connectivity(database_url: Optional[str], timeout_seconds: float = 2.0) -> bool:
    """Lightweight, timed connectivity probe for UI status display only.

    Deliberately independent of the module-level cached engine (get_engine):
    a UI status indicator must never share state with, or perturb, the
    engine the rest of the application relies on. Returns False on any
    failure (unset URL, auth failure, network failure, timeout) rather than
    raising — this is a status signal, not a startup gate. The underlying
    error is logged (sanitized), never returned to the caller, so it is safe
    to surface the boolean result directly in an unauthenticated UI.
    """
    if not database_url:
        return False
    probe_engine = None
    try:
        connect_args = {}
        if database_url.startswith("postgresql"):
            connect_args["connect_timeout"] = max(1, int(timeout_seconds))
        probe_engine = create_engine(database_url, connect_args=connect_args)
        with probe_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 — a probe failure is a status result, not a crash
        _logger.warning("database_connectivity_probe_failed", error=str(exc.__class__.__name__))
        return False
    finally:
        if probe_engine is not None:
            probe_engine.dispose()
