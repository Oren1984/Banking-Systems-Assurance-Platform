from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from core.contracts import Chunk, HealthStatus, VectorStore
from core.exceptions import VectorStoreError

# Adapted from RAG-Engineering-Lab/src/vectorstores/chroma_store.py (see
# BANKING_PLATFORM_INTEGRATION_PLAN.md §3: "Reuse with minor adaptation").
# Chroma is the approved secondary local/portable vector backend (see
# docs/vector_backend_decision.md); pgvector (rag/vectorstores/pgvector_store.py)
# is the approved primary persistent backend.
#
# Additions relative to the source implementation, to satisfy the extended
# VectorStore contract in core/contracts.py:
#   - `filters` on search() -> Chroma `where` clause
#   - `delete_by_document` (the source only exposed a full `clear()`)
#   - `health_check`, `backend_name`, `collection_name`
# `persist()`/`load()` are dropped: PersistentClient persists automatically,
# so they no longer model this backend (see core/contracts.py docstring).

_DEFAULT_COLLECTION = "banking_assurance_chunks"
_DEFAULT_PERSIST_DIR = os.path.join("data", "chroma")


class ChromaVectorStore(VectorStore):
    """Vector store backed by ChromaDB with local persistence."""

    def __init__(
        self,
        persist_directory: str = _DEFAULT_PERSIST_DIR,
        collection_name: str = _DEFAULT_COLLECTION,
    ) -> None:
        self._persist_directory = persist_directory
        self._collection_name = collection_name
        self._client = None
        self._collection = None

    # ------------------------------------------------------------------
    # VectorStore interface
    # ------------------------------------------------------------------

    def add(self, chunks: List[Chunk]) -> None:
        if not chunks:
            return
        missing = [c.chunk_id for c in chunks if c.embedding is None]
        if missing:
            raise VectorStoreError(f"Chunks missing embeddings: {missing}")
        collection = self._get_collection()
        ids = [c.chunk_id for c in chunks]
        embeddings = [c.embedding for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [self._build_chroma_metadata(c) for c in chunks]
        try:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
        except Exception as exc:
            raise VectorStoreError(f"ChromaDB add failed: {exc}") from exc

    def search(
        self,
        query_embedding: List[float],
        top_k: int,
        filters: Optional[dict] = None,
    ) -> List[Chunk]:
        collection = self._get_collection()
        try:
            count = collection.count()
        except Exception as exc:
            raise VectorStoreError(f"ChromaDB count failed: {exc}") from exc
        if count == 0:
            return []
        n = min(top_k, count)
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n,
                where=filters or None,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise VectorStoreError(f"ChromaDB search failed: {exc}") from exc
        return self._parse_results(results)

    def delete_by_document(self, doc_id: str) -> None:
        collection = self._get_collection()
        try:
            collection.delete(where={"doc_id": doc_id})
        except Exception as exc:
            raise VectorStoreError(f"ChromaDB delete_by_document failed: {exc}") from exc

    def clear(self) -> None:
        client = self._ensure_client()
        try:
            client.delete_collection(self._collection_name)
        except Exception:
            pass  # Collection may not exist yet; that's fine
        self._collection = None

    def health_check(self) -> HealthStatus:
        try:
            collection = self._get_collection()
            count = collection.count()
            return HealthStatus(
                healthy=True,
                backend=self.backend_name,
                detail=f"collection '{self._collection_name}' reachable, {count} chunks",
            )
        except Exception as exc:
            return HealthStatus(healthy=False, backend=self.backend_name, detail=str(exc))

    @property
    def backend_name(self) -> str:
        return "chroma"

    @property
    def collection_name(self) -> str:
        return self._collection_name

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            import chromadb
        except ImportError as exc:
            raise VectorStoreError(
                "chromadb package is required for ChromaVectorStore. "
                "Install it with: pip install chromadb"
            ) from exc
        os.makedirs(self._persist_directory, exist_ok=True)
        try:
            self._client = chromadb.PersistentClient(path=self._persist_directory)
        except Exception as exc:
            raise VectorStoreError(
                f"Failed to create ChromaDB client at '{self._persist_directory}': {exc}"
            ) from exc
        return self._client

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        client = self._ensure_client()
        try:
            self._collection = client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            raise VectorStoreError(
                f"Failed to get/create ChromaDB collection '{self._collection_name}': {exc}"
            ) from exc
        return self._collection

    @staticmethod
    def _build_chroma_metadata(chunk: Chunk) -> Dict[str, Any]:
        meta: Dict[str, Any] = {"doc_id": chunk.doc_id}
        for k, v in chunk.metadata.items():
            if isinstance(v, (str, int, float, bool)):
                meta[k] = v
            elif v is not None:
                meta[k] = str(v)
        return meta

    @staticmethod
    def _parse_results(results: dict) -> List[Chunk]:
        ids_list = results.get("ids", [[]])[0]
        docs_list = results.get("documents", [[]])[0]
        metas_list = results.get("metadatas", [[]])[0]
        dists_list = results.get("distances", [[]])[0]

        chunks: List[Chunk] = []
        for rank, (cid, text, raw_meta, dist) in enumerate(
            zip(ids_list, docs_list, metas_list, dists_list), start=1
        ):
            meta = dict(raw_meta)
            doc_id = meta.pop("doc_id", "")
            chunks.append(
                Chunk(
                    chunk_id=cid,
                    doc_id=doc_id,
                    text=text,
                    metadata=meta,
                    score=1.0 - dist,
                    rank=rank,
                )
            )
        return chunks
