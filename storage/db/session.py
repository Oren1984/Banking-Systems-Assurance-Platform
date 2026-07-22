from __future__ import annotations

from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import Settings
from core.exceptions import ConfigurationError

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
