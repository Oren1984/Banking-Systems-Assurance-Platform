from __future__ import annotations

from core.config import Settings
from core.contracts import VectorStore
from core.exceptions import ConfigurationError

# Factory/registry required by BANKING_PLATFORM_INTEGRATION_PLAN.md Part C
# §4 (approved revision): "The configuration and factory/registry must
# select one backend explicitly. No automatic dual write." This function is
# the single place that decision is made.


def get_vector_store(settings: Settings) -> VectorStore:
    """
    Construct the configured VectorStore backend. Exactly one backend is
    ever returned — pgvector and Chroma are never run simultaneously.
    """
    if settings.vector_backend == "pgvector":
        from rag.vectorstores.pgvector_store import PgVectorStore

        if not settings.database_url:
            raise ConfigurationError(
                "VECTOR_BACKEND=pgvector requires DATABASE_URL to be set."
            )
        return PgVectorStore(
            database_url=settings.database_url,
            collection_name=settings.chroma_collection_name,
        )

    if settings.vector_backend == "chroma":
        from rag.vectorstores.chroma_store import ChromaVectorStore

        return ChromaVectorStore(
            persist_directory=settings.chroma_persist_directory,
            collection_name=settings.chroma_collection_name,
        )

    # Unreachable while settings.vector_backend is validated by core.config's
    # Literal["pgvector", "chroma"] type at Settings construction time; kept
    # as an explicit, defensive failure rather than silently picking a
    # default backend.
    raise ConfigurationError(f"Unknown vector backend: {settings.vector_backend!r}")
