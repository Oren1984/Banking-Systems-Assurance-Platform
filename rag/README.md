# rag/

## Phase 1 (implemented — foundation only)

- `embeddings/mock_embedding_provider.py` — deterministic, offline, dependency-free default
  embedding provider. Adapted from `RAG-Engineering-Lab/src/embeddings/mock_embedding_provider.py`.
- `vectorstores/chroma_store.py` — Chroma (secondary/portable local backend). Functionally
  complete and exercised by `tests/integration/test_chroma_vectorstore.py` against a real,
  local, on-disk Chroma instance (no server, no network).
- `vectorstores/pgvector_store.py` — PostgreSQL + pgvector (primary persistent backend).
  Implements the full `VectorStore` contract. **Phase 1:** construction/config-validation and
  graceful-failure `health_check()` only (`tests/unit/test_pgvector_store.py`) — no live server
  was available. **Phase 2:** a real add()/search() round-trip was verified against a live,
  Docker-Compose-provisioned PostgreSQL/pgvector instance
  (`tests/integration/test_postgres_persistence.py`) — see `docs/vector_backend_decision.md`
  and `PHASE_2_COMPLETION_REPORT.md`.
- `vectorstores/registry.py` — selects exactly one backend from `core.config.Settings`; no
  automatic dual write.

## Local-RAG document lifecycle (still not implemented — status corrected)

`ingestion/`, `chunking/`, `retrieval/` (dense + hybrid), and `pipeline.py` — for ingesting
*policy/control documents* into the vector store — were **not** built in Phase 2. Phase 2
built a different thing entirely: a read-only *source-scanning* engine (see `scanners/`,
not `rag/`). This directory's document-ingestion pipeline remains future work; `rag/retrieval/`
still contains only `__init__.py`. Do not import a retrieval module from this package.
