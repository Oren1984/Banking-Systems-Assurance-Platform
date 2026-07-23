# Architecture — Phase 1–6 Snapshot

This document describes what exists after Phase 1 through Phase 6, the project's final
implementation phase. For the full target architecture, rationale, and audit findings behind
every decision, see `BANKING_PLATFORM_INTEGRATION_PLAN.md` — this file does not repeat that
content, only points to what is actually implemented today. See `docs/phase2_scanning_guide.md`
for Phase 2's scanning-specific detail (supported file types, safety limits, scanner coverage),
and `PHASE_1_COMPLETION_REPORT.md` through `PHASE_6_COMPLETION_REPORT.md` for exactly what each
phase delivered and tested.

## Module boundary: trusted deterministic core vs. optional agent

Every module through Phase 5 — `scanners/`, `scoring/`, `assessment/` (engine, evaluators,
traceability), `evidence/`, `controls/`, `governance/approval_workflow.py`,
`storage/db/repositories.py`'s write paths, `reporting/` — forms the platform's trusted,
deterministic core. It produces every finding, score, control evaluation, governance decision,
and report, and it requires no external network access or AI provider to do so.

`agents/` and `providers/` (Phase 6) sit **outside** that boundary, one layer removed:

```
 trusted deterministic core                     optional agent boundary
 ───────────────────────────                    ───────────────────────
 scanners/ → assessment/ → scoring/              agents/sanitizer.py
   → governance/approval_workflow.py               (minimizes context)
   → storage/db/repositories.py (writes)          agents/local_agent.py (default)
   → reporting/                                    or providers/*_adapter.py (optional)
                                                   agents/agent_service.py
                                                     (never writes to the core's tables)
        ▲                                                  │
        │ read-only fetch of already-persisted             │ advisory-only output,
        │ Finding/Score rows                                │ AuditEvent only
        └────────────── ui/services/agent_ui_service.py ────┘
```

Nothing in the left column imports from `agents/` or `providers/`. Everything in the right
column that touches the database does so through `ui/services/agent_ui_service.py`, which only
ever *reads* already-persisted rows and *writes* an `AuditEvent` — it has no code path that
inserts or updates a `Finding`, `Score`, `ControlEvaluation`, or `Recommendation` row. See
`docs/agent_guide.md` for the full boundary description and `agents/README.md`/`providers/README.md`
for the module-level breakdown.

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

## Implemented in Phase 3

| Module | Contents | Source |
|---|---|---|
| `scoring/engine.py` | `score_domain`/`score_all_domains` — severity+confidence-weighted domain scoring; the core fix: an unevaluated domain resolves to `INSUFFICIENT_EVIDENCE`, never a false "clean" score | Net-new; mechanism pattern from `AI-Project-Scope-Guard/src/scope_guard/evaluator.py`, dimension aggregation from `ai-project-control-tower/app/audit/scoring.py` |
| `scoring/recommendations.py` | `generate_recommendations` — deterministic-template recommendation text | Net-new |
| `controls/catalog.py` | `CONTROL_CATALOG` (8 illustrative technical controls), `upsert_catalog`, `control_for_rule_id` | Net-new |
| `evidence/capture.py` | `build_evidence` — per-finding evidence capture from already-masked evidence | Net-new |
| `storage/db/models/{control,evidence,score,recommendation}.py` + 3 new `findings` columns | 4 new tables, `human_review_status`/`reviewed_by`/`reviewed_at` on `findings` | Net-new against the platform's own contract |
| `alembic/versions/0002_phase3_controls_evidence_scoring.py` | Migration for the above, applied and verified against a live Postgres instance | Net-new |
| `storage/db/repositories.py::ScoringRepository` | `score_scan`, `score_and_generate`, `get_scores`, `get_recommendations`, `get_evidence_for_finding`, `review_recommendation` | Net-new |

## Implemented in Phase 4

| Module | Contents | Source |
|---|---|---|
| `assessment/engine.py::run_assessment` | Thin, read-only orchestration: ingest → scan → persist → score/evidence/recommendations → control evaluation → audit trail | Net-new; adapted in spirit from `ai-project-control-tower/app/audit/audit_engine.py`, generalized from hardcoded agent classes |
| `assessment/evaluators/control_evaluator.py` | Per-(domain, control) evaluation — `satisfied`/`gap`/`insufficient_evidence` — the same core fix as `scoring/engine.py`, applied at control granularity | Net-new; generalized from `ai-project-control-tower/app/agents/*` |
| `assessment/traceability.py` | `TraceabilityRepository.trace_finding()` — full source file → rule → domain → control → evidence → score → recommendation chain for one finding | Net-new |
| `governance/approval_workflow.py` | `review_finding`, `override_score`, `check_finalization_policy` — pure validation/policy functions | Net-new |
| `governance/audit_trail.py` | `build_audit_event` — sanitized, append-only event construction | Net-new |
| `governance/retention.py` | `find_scans_eligible_for_retention` — identify-only retention foundations, never deletes | Net-new |
| `storage/db/models/{audit_event,control_evaluation}.py` | 2 new tables | Net-new |
| `alembic/versions/..._phase4_audit_trail_control_evaluations.py` | Migration for the above, applied and verified against a live Postgres instance | Net-new |
| `storage/db/repositories.py::{ControlEvaluationRepository,AuditRepository,GovernanceRepository}` | Persistence + policy application for the above | Net-new |
| `knowledge_base/controls/domain_coverage.json` | Generated (not hand-authored) domain-to-control coverage manifest across all 16 domains | Net-new (`scripts/generate_knowledge_base_manifest.py`) |
| `reporting/assessment_report_exporter.py` | Assessment-level Markdown/JSON export with governance disclaimers | Net-new |

See `PHASE_4_COMPLETION_REPORT.md` for exactly what was tested and verified, and what remains
deferred to Phase 5.

## Implemented in Phase 5

| Module | Contents | Source |
|---|---|---|
| `ui/streamlit_app.py` | Extended (not replaced) into a two-mode app: "Quick Scan" (Phase 2, unchanged, no database) and "Full Assessment" (Phase 5 — run/select an assessment, view scores/findings/traceability/control evaluations, governance review, export) | Extends `ui/streamlit_app.py`; Phase 2's Quick Scan code is unmodified |
| `ui/services/assessment_service.py` | Every business-logic function the UI calls — no Streamlit import, fully unit-tested | Net-new; renamed/reshaped illustrative `ui/services/api_client.py` (see below) |
| `reporting/assessment_report_exporter.py::{to_findings_csv,to_scores_csv}` | CSV export, added to the existing Phase 4 exporter | Net-new functions in an existing Phase 4 module |
| `mock_banking_system/` | 27 synthetic source files, 15 of 16 domains represented, planted positive/negative findings across 4 severities | Net-new content (directory scaffolding was Phase 1) |
| `scripts/seed_mock_banking_demo.py` | Fully implemented: runs a real `run_assessment()` against `mock_banking_system/`, writes sample exports under `<report_output_dir>/mock_banking_demo/` | Replaces the Phase 1 documented-placeholder version |
| `docs/demo_guide.md`, `docs/mock_banking_planted_findings.md` | Reproducible demo walkthrough; authoritative, actually-executed finding/score inventory | Net-new |

See `PHASE_5_COMPLETION_REPORT.md` for exactly what was tested and verified.

## Implemented in Phase 6 (final phase)

| Module | Contents | Source |
|---|---|---|
| `agents/{contracts,sanitizer,local_agent,registry,agent_service}.py` | The optional agent boundary — see "Module boundary" above and `agents/README.md` | Net-new |
| `ui/services/agent_ui_service.py` | Database glue for the agent boundary: fetches persisted rows, calls `agents/agent_service.py`, records one `AuditEvent` per action | Net-new |
| `ui/streamlit_app.py`'s "AI Assistant (Optional)" tab | Explain a finding, summarize a domain, ask a question, generate an executive summary — clearly labeled local/external, advisory-only | Extends the existing Full Assessment tab set; every other tab unchanged |
| `providers/{openai,gemini,claude}_adapter.py` | Finalized: `model`/`timeout_seconds`/`max_retries` configuration surface added; `send()` remains a documented stub (see `providers/README.md`) | Extends Phase 1 scaffolding |
| `docs/agent_guide.md` | Provider architecture, setup, security/privacy boundaries, consent, failure handling, audit behavior, limitations, cost | Net-new |

See `PHASE_6_COMPLETION_REPORT.md` for exactly what was tested and verified, the documentation
cleanup inventory, and the final closure recommendation.

### Structural deviations from the illustrative tree (Phase 5 addition)

5. **`ui/services/assessment_service.py`, not `ui/services/api_client.py`.** The illustrative
   Phase 1 tree names this file `api_client.py`, implying a FastAPI backend the UI calls over
   HTTP (`ai-project-control-tower`'s pattern). This platform never built that backend layer
   for assessments — `app/main.py` still only exposes `/health` (Phase 1). `ui/streamlit_app.py`
   instead calls `ui/services/assessment_service.py`, which talks to the same SQLAlchemy
   repositories (`storage/db/repositories.py`) every other caller (the seed script, tests) uses
   directly. Renamed to reflect what the file actually does, per this project's established
   practice of documenting deviations rather than silently diverging (see deviations #1–#4
   above).
6. **`ui/pages/`, `ui/components/` remain empty.** A single-file, tabbed app was judged
   sufficient for Phase 5's "avoid unnecessary design complexity" instruction rather than
   Streamlit's native multipage convention — see `ui/README.md`.

## Not implemented (deliberately, confirmed out of scope as of Phase 6 — the project's final phase)

`knowledge_base/controls/` content beyond the generated coverage manifest (real regulatory
control text remains an open question — §16 #4, never resolved, not an engineering task),
`rag/ingestion`, `rag/chunking`, `rag/retrieval`, `rag/pipeline.py` (the *document* RAG
lifecycle — unchanged since Phase 1; the agent boundary does not use retrieval, see
`docs/agent_guide.md`'s "Limitations"), and `models/provider_request.py`/real
`providers/*_adapter.py::send()` implementations (confirmed a deliberate Phase 6 scope
boundary, not deferred to a future phase — no further phase is planned; see
`providers/README.md`).
Each has a `README.md` in its directory stating what phase it belongs to. See
`BANKING_PLATFORM_INTEGRATION_PLAN.md` Part B for the phase plan.

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
