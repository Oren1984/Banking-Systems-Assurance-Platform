from __future__ import annotations

import json
from typing import List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from core.contracts import Chunk, HealthStatus, VectorStore
from core.exceptions import VectorStoreError

# New for the unified platform (see BANKING_PLATFORM_INTEGRATION_PLAN.md §3:
# ai-project-control-tower's app/rag/* hybrid TF-IDF+vector stack was
# "Refactor before reuse" — this class is the pgvector-conformant
# replacement, built against the platform's own VectorStore contract rather
# than adapting the old hybrid retriever directly.
#
# Approved as the platform's PRIMARY persistent vector backend (Part A §2 of
# the approved plan revision). PostgreSQL and pgvector are not removed or
# treated as legacy — Chroma (chroma_store.py) is the secondary/portable
# backend, not a replacement for this one.
#
# Phase 1 scope boundary (see BANKING_PLATFORM_INTEGRATION_PLAN.md Part C
# §9 of the approved revision): this class implements the full VectorStore
# contract and a schema-creation helper, but full ingestion/retrieval
# correctness against a live database has NOT been verified in this
# session — no PostgreSQL/pgvector server is available in this planning
# environment. health_check() is designed to fail gracefully (return
# healthy=False) rather than raise, precisely so the rest of the platform
# can start up and report status without a live database. Full end-to-end
# verification against a real pgvector instance is Phase 2 work.

_DEFAULT_COLLECTION = "banking_assurance_chunks"


class PgVectorStore(VectorStore):
    """Vector store backed by PostgreSQL + the pgvector extension."""

    def __init__(
        self,
        database_url: str,
        collection_name: str = _DEFAULT_COLLECTION,
        dimension: int = 128,
    ) -> None:
        if not database_url:
            raise VectorStoreError(
                "PgVectorStore requires a non-empty database_url "
                "(set DATABASE_URL — no default is provided, by design)."
            )
        self._database_url = database_url
        self._collection_name = collection_name
        self._dimension = dimension
        self._engine: Optional[Engine] = None

    # ------------------------------------------------------------------
    # VectorStore interface
    # ------------------------------------------------------------------

    def ensure_schema(self) -> None:
        """
        Idempotently create the pgvector extension and this collection's
        table. Not called automatically — the caller decides when schema
        creation is appropriate (e.g. once, from an Alembic migration or an
        explicit setup step), consistent with "do not migrate all future
        domain tables unless required by Phase 1".
        """
        engine = self._ensure_engine()
        table = self._table_name()
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        chunk_id TEXT PRIMARY KEY,
                        doc_id TEXT NOT NULL,
                        text TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        embedding VECTOR({self._dimension}) NOT NULL
                    )
                    """
                )
            )

    def add(self, chunks: List[Chunk]) -> None:
        if not chunks:
            return
        missing = [c.chunk_id for c in chunks if c.embedding is None]
        if missing:
            raise VectorStoreError(f"Chunks missing embeddings: {missing}")
        engine = self._ensure_engine()
        table = self._table_name()
        try:
            with engine.begin() as conn:
                for c in chunks:
                    conn.execute(
                        text(
                            f"""
                            INSERT INTO {table} (chunk_id, doc_id, text, metadata, embedding)
                            VALUES (:chunk_id, :doc_id, :text, :metadata, :embedding)
                            ON CONFLICT (chunk_id) DO UPDATE SET
                                doc_id = EXCLUDED.doc_id,
                                text = EXCLUDED.text,
                                metadata = EXCLUDED.metadata,
                                embedding = EXCLUDED.embedding
                            """
                        ),
                        {
                            "chunk_id": c.chunk_id,
                            "doc_id": c.doc_id,
                            "text": c.text,
                            "metadata": json.dumps(c.metadata),
                            "embedding": str(list(c.embedding)),
                        },
                    )
        except Exception as exc:
            raise VectorStoreError(f"pgvector add failed: {exc}") from exc

    def search(
        self,
        query_embedding: List[float],
        top_k: int,
        filters: Optional[dict] = None,
    ) -> List[Chunk]:
        engine = self._ensure_engine()
        table = self._table_name()
        where_clause = ""
        params = {"embedding": str(list(query_embedding)), "top_k": top_k}
        if filters:
            conditions = []
            for i, (key, value) in enumerate(filters.items()):
                param_name = f"filter_{i}"
                conditions.append(f"metadata ->> '{key}' = :{param_name}")
                params[param_name] = str(value)
            where_clause = "WHERE " + " AND ".join(conditions)
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        f"""
                        SELECT chunk_id, doc_id, text, metadata,
                               1 - (embedding <=> CAST(:embedding AS VECTOR)) AS score
                        FROM {table}
                        {where_clause}
                        ORDER BY embedding <=> CAST(:embedding AS VECTOR)
                        LIMIT :top_k
                        """
                    ),
                    params,
                ).fetchall()
        except Exception as exc:
            raise VectorStoreError(f"pgvector search failed: {exc}") from exc

        chunks: List[Chunk] = []
        for rank, row in enumerate(rows, start=1):
            metadata = row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata)
            chunks.append(
                Chunk(
                    chunk_id=row.chunk_id,
                    doc_id=row.doc_id,
                    text=row.text,
                    metadata=metadata,
                    score=float(row.score),
                    rank=rank,
                )
            )
        return chunks

    def delete_by_document(self, doc_id: str) -> None:
        engine = self._ensure_engine()
        table = self._table_name()
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(f"DELETE FROM {table} WHERE doc_id = :doc_id"),
                    {"doc_id": doc_id},
                )
        except Exception as exc:
            raise VectorStoreError(f"pgvector delete_by_document failed: {exc}") from exc

    def clear(self) -> None:
        engine = self._ensure_engine()
        table = self._table_name()
        try:
            with engine.begin() as conn:
                conn.execute(text(f"TRUNCATE TABLE {table}"))
        except Exception as exc:
            raise VectorStoreError(f"pgvector clear failed: {exc}") from exc

    def health_check(self) -> HealthStatus:
        try:
            engine = self._ensure_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return HealthStatus(
                healthy=True,
                backend=self.backend_name,
                detail=f"connected, collection table '{self._table_name()}'",
            )
        except Exception as exc:
            # Deliberately does not raise: health_check must let the rest of
            # the platform start and report status even with no live DB.
            return HealthStatus(healthy=False, backend=self.backend_name, detail=str(exc))

    @property
    def backend_name(self) -> str:
        return "pgvector"

    @property
    def collection_name(self) -> str:
        return self._collection_name

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _ensure_engine(self) -> Engine:
        if self._engine is None:
            self._engine = create_engine(self._database_url, pool_pre_ping=True)
        return self._engine

    def _table_name(self) -> str:
        # Collection name is only ever sourced from configuration/code
        # (core.config.Settings), never from end-user input, so direct
        # interpolation into DDL/table references here is not a SQL
        # injection vector. All data values use bound parameters above.
        safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in self._collection_name)
        return f"vs_{safe}"
