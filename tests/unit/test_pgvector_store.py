from __future__ import annotations

import pytest

from core.exceptions import VectorStoreError
from rag.vectorstores.pgvector_store import PgVectorStore

# Phase 1 limitation (documented, not silently assumed away): no live
# PostgreSQL/pgvector server is available in this environment, so these
# tests cover construction, identity, and graceful-failure behavior only.
# Real add()/search()/delete_by_document() correctness against a live
# database is Phase 2 work — see rag/README.md and PHASE_1_COMPLETION_REPORT.md.


def test_requires_nonempty_database_url():
    with pytest.raises(VectorStoreError):
        PgVectorStore(database_url="")


def test_backend_name_and_collection_name():
    store = PgVectorStore(
        database_url="postgresql://user:pass@localhost:5432/db",
        collection_name="test_collection",
    )
    assert store.backend_name == "pgvector"
    assert store.collection_name == "test_collection"


def test_health_check_fails_gracefully_without_a_live_database():
    # Points at a port nothing is listening on in this environment;
    # health_check() must return a HealthStatus, never raise.
    store = PgVectorStore(
        database_url="postgresql://user:pass@localhost:1/nonexistent_db"
    )
    status = store.health_check()
    assert status.healthy is False
    assert status.backend == "pgvector"
    assert status.detail  # some explanation is present
