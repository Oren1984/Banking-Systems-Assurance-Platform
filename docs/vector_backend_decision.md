# Vector Backend Decision

**Status:** Approved (stakeholder decision recorded in the Phase 1 revision brief; implemented
in `rag/vectorstores/`).

## Decision

- **Primary persistent backend: PostgreSQL + pgvector.** Retained and extended from
  `ai-project-control-tower`'s existing PostgreSQL/pgvector foundation — not treated as
  temporary or legacy. Used for platform data, assessments, controls, policies, findings,
  evidence, scores, reports, audit events, human review history, provider request metadata,
  and vector embeddings where appropriate (see `BANKING_PLATFORM_INTEGRATION_PLAN.md`, Part A
  §2 of the approved revision).
- **Secondary local/portable backend: Chroma.** Not FAISS. `rag/vectorstores/chroma_store.py`
  is adapted from `RAG-Engineering-Lab/src/vectorstores/chroma_store.py`.
- **FAISS is not selected for the active platform.** It remains referenced only as an
  archived `RAG-Engineering-Lab` component (see `BANKING_PLATFORM_INTEGRATION_PLAN.md` §15)
  and adds no implementation or maintenance burden to the new system.
- **No automatic dual write.** `rag/vectorstores/registry.py::get_vector_store()` returns
  exactly one backend, selected by `core.config.Settings.vector_backend`
  (`VECTOR_BACKEND=pgvector` or `VECTOR_BACKEND=chroma`). Both operating modes remain
  local-first: pgvector runs against a local Docker Compose Postgres instance
  (`deployment/docker-compose.yml`), and Chroma's `PersistentClient` writes to local disk with
  no server process at all.

## Why this supports the long-term platform

Chroma was chosen over FAISS as the secondary backend because it natively supports
persistent collections, metadata filtering, per-document deletion, and re-indexing — all of
which the platform's document lifecycle requirements need (see
`BANKING_PLATFORM_INTEGRATION_PLAN.md` §6) and which the original FAISS implementation in
`RAG-Engineering-Lab` did not fully expose. PostgreSQL/pgvector remains the primary backend
because it is already the proven, most-complete persistence layer among the three audited
repositories (see `BANKING_PLATFORM_INTEGRATION_PLAN.md` §2.1) and because full-platform
persistence (assessments, controls, findings, audit trail) needs a relational database
regardless of which vector store is used — colocating vectors there for the primary
deployment mode avoids running two databases in the common case.

## Operating modes

| Mode | `VECTOR_BACKEND` | Use case |
|---|---|---|
| Full platform (default) | `pgvector` | Standard local deployment via Docker Compose |
| Portable / demonstration | `chroma` | Local testing, isolated demos, environments without a Postgres server |

## What was actually verified

- `rag/vectorstores/chroma_store.py`: real, functional add/search/delete/clear/health-check
  behavior, verified against a live local Chroma instance in
  `tests/integration/test_chroma_vectorstore.py` (5 tests, all passing — Phase 1).
- `rag/vectorstores/pgvector_store.py`: **Phase 1** — implemented the full contract but not
  verified against a live server (none was available in that session); only construction and
  graceful-failure `health_check()` behavior were covered.
  **Phase 2 (this closes the gap)** — Docker was available; `deployment/docker-compose.yml`'s
  `db` service was started locally with a non-default test credential, and
  `tests/integration/test_postgres_persistence.py` verified, against that live instance: a
  real connection and `pg_extension` check for `vector`, the Phase 2 Alembic migration's
  tables existing, and — the specific gap Phase 1 named — a real `add()`/`search()` round-trip
  through `PgVectorStore` returning the correct chunk. 5/5 tests passed. This is still a
  narrow, single-round-trip verification, not a claim of production-scale performance or
  correctness under concurrent writes — see `PHASE_2_COMPLETION_REPORT.md`.
