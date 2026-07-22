from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

# ---------------------------------------------------------------------------
# Reused as-is from RAG-Engineering-Lab/src/core/contracts.py (see
# BANKING_PLATFORM_INTEGRATION_PLAN.md §3): these DTOs and the
# EmbeddingProvider/Chunker/Reranker interfaces are provider-agnostic and
# require no changes for the unified platform.
# ---------------------------------------------------------------------------


@dataclass
class Document:
    """A loaded source document before chunking."""

    doc_id: str
    text: str
    source: str
    file_type: str
    page_number: Optional[int] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Chunk:
    """
    A single text chunk derived from a Document.

    The unit of storage, retrieval, and evidence throughout the pipeline.
    `score`/`rank` are populated by the retrieval layer; `metadata` (source,
    file path, line numbers) is what ultimately populates a Finding's
    `source_reference` field (see BANKING_PLATFORM_INTEGRATION_PLAN.md §11).
    """

    chunk_id: str
    doc_id: str
    text: str
    metadata: dict = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    score: Optional[float] = None
    rank: Optional[int] = None


@dataclass
class HealthStatus:
    """Result of a backend health/status check (vector store, provider, DB)."""

    healthy: bool
    backend: str
    detail: str = ""


class EmbeddingProvider(ABC):
    """Common interface for all embedding providers."""

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts and return one vector per text."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier (e.g. 'mock', 'local', 'openai')."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors produced by this provider."""


class Chunker(ABC):
    """Common interface for text chunking strategies."""

    @abstractmethod
    def chunk(self, document: Document) -> List[Chunk]:
        """Split a Document into a list of Chunks."""


class Reranker(ABC):
    """Optional interface for cross-encoder re-ranking."""

    @abstractmethod
    def rerank(self, query: str, chunks: List[Chunk]) -> List[Chunk]:
        """Re-rank retrieved chunks by relevance to the query, descending."""


# ---------------------------------------------------------------------------
# VectorStore: extended relative to RAG-Engineering-Lab's original contract.
#
# Additions required by this platform (see Part C §4 of the approved
# revision brief) that the source contract did not have:
#   - `filters` on search(), for metadata-scoped retrieval
#   - `delete_by_document`, for per-document deletion/re-indexing (the
#     source contract only exposed a full `clear()`)
#   - `health_check`, `backend_name`, `collection_name`, so the platform can
#     report vector-store status without a full search round-trip
# `persist`/`load` from the original contract are dropped: pgvector persists
# implicitly (it's a database) and Chroma's PersistentClient also persists
# implicitly, so an explicit persist/load step no longer models either
# concrete backend.
# ---------------------------------------------------------------------------


class VectorStore(ABC):
    """
    Common interface for vector store implementations.

    Both the primary pgvector backend and the secondary Chroma backend
    implement this same interface (see docs/vector_backend_decision.md).
    All methods operate on Chunk objects so that text and metadata are
    preserved alongside embeddings regardless of the underlying store.
    """

    @abstractmethod
    def add(self, chunks: List[Chunk]) -> None:
        """Add chunks (with embeddings already set) to the store."""

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int,
        filters: Optional[dict] = None,
    ) -> List[Chunk]:
        """Return the top_k most similar chunks, optionally filtered by metadata."""

    @abstractmethod
    def delete_by_document(self, doc_id: str) -> None:
        """Remove all chunks belonging to a single document (for re-indexing)."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all stored vectors and metadata from the collection."""

    @abstractmethod
    def health_check(self) -> HealthStatus:
        """Report whether this backend is reachable and usable right now."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Backend identifier (e.g. 'pgvector', 'chroma')."""

    @property
    @abstractmethod
    def collection_name(self) -> str:
        """Name of the collection/namespace/table this instance operates on."""


__all__ = [
    "Document",
    "Chunk",
    "HealthStatus",
    "EmbeddingProvider",
    "Chunker",
    "Reranker",
    "VectorStore",
]
