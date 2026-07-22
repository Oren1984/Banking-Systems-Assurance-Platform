from __future__ import annotations

import pytest

from core.config import Settings
from core.exceptions import ConfigurationError
from rag.vectorstores.chroma_store import ChromaVectorStore
from rag.vectorstores.pgvector_store import PgVectorStore
from rag.vectorstores.registry import get_vector_store


def test_selects_chroma_backend(tmp_path):
    settings = Settings(
        _env_file=None,
        vector_backend="chroma",
        chroma_persist_directory=str(tmp_path / "chroma"),
    )
    store = get_vector_store(settings)
    assert isinstance(store, ChromaVectorStore)
    assert store.backend_name == "chroma"


def test_selects_pgvector_backend_when_database_url_set():
    settings = Settings(
        _env_file=None,
        vector_backend="pgvector",
        database_url="postgresql://user:pass@localhost:5432/db",
    )
    store = get_vector_store(settings)
    assert isinstance(store, PgVectorStore)
    assert store.backend_name == "pgvector"


def test_pgvector_backend_without_database_url_raises_clear_error():
    settings = Settings(_env_file=None, vector_backend="pgvector", database_url=None)
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        get_vector_store(settings)


def test_no_automatic_dual_write(tmp_path):
    # Selecting one backend must never also construct the other.
    settings = Settings(
        _env_file=None,
        vector_backend="chroma",
        chroma_persist_directory=str(tmp_path / "chroma"),
    )
    store = get_vector_store(settings)
    assert not isinstance(store, PgVectorStore)
