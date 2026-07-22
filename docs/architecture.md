# Architecture — Phase 1 + Phase 2 Snapshot

This document describes what exists after Phase 1 and Phase 2. For the full target
architecture, rationale, and audit findings behind every decision, see
`BANKING_PLATFORM_INTEGRATION_PLAN.md` — this file does not repeat that content, only points
to what is actually implemented today. See `docs/phase2_scanning_guide.md` for Phase 2's
scanning-specific detail (supported file types, safety limits, scanner coverage).

## Repository layout

This platform is built directly at the root of this git repository (not in a nested
`banking-systems-assurance-platform/` subdirectory), alongside the three untouched legacy
repositories (`RAG-Engineering-Lab/`, `ai-project-control-tower/`, `AI-Project-Scope-Guard/`),
which remain available as read-only reference material until superseded functionality is
fully ported and tested (see `BANKING_PLATFORM_INTEGRATION_PLAN.md` §15). This is a
deliberate structural decision, not an oversight: the repository is already scoped and named
for this platform, and a redundant nested folder would add no value while creating two
plausible "roots" for tooling to get confused about.

## Implemented in Phase 1

| Module | Contents | Source |
|---|---|---|
| `core/config.py` | `Settings` — unified typed configuration, local-first defaults, no embedded credentials | Merged from `RAG-Engineering-Lab/src/core/config.py` + `ai-project-control-tower/app/core/config.py` |
| `core/contracts.py` | `Document`, `Chunk`, `HealthStatus`, `EmbeddingProvider`, `Chunker`, `Reranker`, `VectorStore` | Adapted from `RAG-Engineering-Lab/src/core/contracts.py` (VectorStore extended) |
| `core/exceptions.py` | Platform exception hierarchy | Merged from both repos' exception hierarchies |
| `core/logging.py` | structlog JSON logging | Adapted from `ai-project-control-tower/app/core/logging.py` |
| `core/domains.py` | `BankingDomain` — the 16 approved domains, single source of truth | Net-new |
| `models/enums.py` | `Severity`, `ConfidenceLevel`, `EvidenceCompleteness`, `HumanReviewStatus`, `DecisionCategory`, `ControlType` | Net-new |
| `governance/*` | `secret_masker.py`, `report_sanitizer.py`, `pii_redaction.py`, `prompt_safety.py`, `file_validation.py` | Ported/adapted from both repos |
| `scanners/path_validator.py` | Allowlist-based, fail-closed scan-path validation | Adapted from `ai-project-control-tower/app/scanner/path_validator.py` |
| `rag/embeddings/mock_embedding_provider.py` | Deterministic offline embedding provider | Adapted from `RAG-Engineering-Lab/src/embeddings/mock_embedding_provider.py` |
| `rag/vectorstores/{chroma_store,pgvector_store,registry}.py` | Vector store contract implementations + factory | Chroma adapted from `RAG-Engineering-Lab`; pgvector net-new against the platform's own contract |
| `providers/{base,registry,openai_adapter,gemini_adapter,claude_adapter}.py` | Disabled-by-default external provider boundary | Net-new, pattern seeded by `RAG-Engineering-Lab`'s embedding providers |
| `storage/db/{base,session}.py` + `alembic.ini` + `alembic/env.py` | SQLAlchemy foundation + Alembic wiring, no domain tables yet | Adapted from `ai-project-control-tower/app/db/*` |
| `app/main.py` | FastAPI app with a `/health` endpoint | Net-new (minimal) |
| `scripts/seed_mock_banking_demo.py` | Documented Phase 5 interface placeholder | Net-new |
| `mock_banking_system/` | Directory scaffold + README | Net-new |
| `deployment/docker-compose.yml` | PostgreSQL/pgvector service only | Adapted from `ai-project-control-tower/docker-compose.yml` |

## Implemented in Phase 2

| Module | Contents | Source |
|---|---|---|
| `scanners/source_ingestion.py` | Safe local-directory + ZIP ingestion (Zip Slip/traversal/absolute-path/symlink/archive-bomb rejection) | Net-new |
| `scanners/file_discovery.py` | Recursive discovery with depth/count/size limits, symlink handling, hashing, source-integrity hashing | Net-new |
| `scanners/content_reader.py` | Safe text reading (binary sniff, encoding fallback, truncation, line numbering) | Net-new |
| `scanners/file_classifier.py` | Deterministic file/technology classification | Net-new (the plan's illustrative name; no analog existed in either source repo) |
| `scanners/domain_mapper.py` | Maps files to `core.domains.BankingDomain` with confidence + evidence | Net-new |
| `scanners/rules/*.py` | 8 deterministic content scanners (secret/PII/logging/audit/permissions/SQL/config/unsupported-file) | Net-new; `secret_scanner.py` reuses `governance/secret_masker.py`'s detection patterns rather than duplicating them |
| `scanners/scan_orchestrator.py` | Full scan pipeline, per-file/per-scanner error isolation, before/after integrity verification | Net-new |
| `storage/db/models/{scan,file_inventory,domain_mapping,finding,scanner_execution}.py` | 5 SQLAlchemy tables (moved earlier than originally planned — see the plan's Phase 2 status correction) | Net-new against the platform's own contract; `finding.py`'s shape adapted from `ai-project-control-tower/app/db/models/finding.py`, extended, and deliberately stores only `masked_evidence` (no raw `evidence` column) |
| `alembic/versions/0001_phase2_scan_findings_tables.py` | Migration for the above, autogenerated and applied against a live Postgres instance | Net-new |
| `storage/db/repositories.py` | `ScanRepository` — persists/reads a `ScanResult` | Net-new |
| `reporting/scan_report_exporter.py` | JSON/Markdown/CSV export, reuses `governance/report_sanitizer.py` | Net-new |
| `ui/streamlit_app.py` | Minimal scan workflow UI | Net-new (Phase 6 will replace this with the final production UI) |

## Not implemented (explicitly deferred, do not import)

`knowledge_base/`, `controls/`, `assessment/`, `evidence/`, `scoring/`, `rag/ingestion`,
`rag/chunking`, `rag/retrieval`, and `models/{control,policy,evidence,score,report,
provider_request,audit_event,human_review}.py` (the control-evaluation side of the schema —
`Finding` itself moved to Phase 2, see above). Each has a `README.md` in its directory stating
what phase it belongs to. See `BANKING_PLATFORM_INTEGRATION_PLAN.md` Part B for the phase
plan.

## Structural deviations from the illustrative tree

1. **No nested `banking-systems-assurance-platform/` folder** (see above).
2. **`core/config.py`, not `config/settings.py`** — the illustrative Phase 1 structure lists
   both `core/` and `config/` as top-level directories without specifying which holds the
   Settings class. This platform keeps the unified `Settings` model in `core/config.py`
   (matching the original approved architecture in `BANKING_PLATFORM_INTEGRATION_PLAN.md`
   §5.2) to avoid recreating the "three separate configuration systems" duplication problem
   the audit flagged. See `config/README.md`.
3. **`storage/db/session.py` uses lazy engine construction**, not the eager
   `engine = create_engine(...)` pattern from `ai-project-control-tower/app/db/session.py`.
   The source pattern only worked because its `database_url` had a (insecure) default value;
   this platform's `database_url` has no default, so eager construction would break import-time
   safety. See `storage/db/README.md`.
4. **`core/contracts.py::VectorStore` drops `persist()`/`load()`** from the original RAG-Lab
   contract and adds `delete_by_document`, `health_check`, `backend_name`, `collection_name`,
   and `filters` on `search()`. See the docstring in `core/contracts.py` for the rationale.
