from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import storage.db.models  # noqa: F401 — registers tables with Base.metadata
from core.config import Settings
from core.exceptions import ConfigurationError
from storage.db.base import Base

# Session factory for the auth/ package. Same shape as
# ui/services/assessment_service.py::_session (expire_on_commit=False,
# create_all so SQLite test databases work without Alembic), except the
# engine is cached per URL: session validation runs on every Streamlit
# rerun and every protected action, so a fresh engine per call would be
# needlessly expensive.


@lru_cache(maxsize=8)
def _engine(database_url: str) -> Engine:
    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return engine


def open_session(settings: Settings) -> Session:
    if not settings.database_url:
        raise ConfigurationError("DATABASE_URL is not configured. Sign-in requires the platform database.")
    return Session(_engine(settings.database_url), expire_on_commit=False)


__all__ = ["open_session"]
