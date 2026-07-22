# Banking Systems Assurance Platform — Integration Plan

**Status:** Revised and approved in principle. Phase 1 ("Unified Foundation") and Phase 2
("Banking Source Ingestion and Read-Only Scanning Engine") are both implemented — see
`PHASE_1_COMPLETION_REPORT.md` and `PHASE_2_COMPLETION_REPORT.md` for exactly what exists,
what was tested, and what remains open. Phases 3–6 are planning only; no code for them has
been written. The three source repositories (`RAG-Engineering-Lab`, `ai-project-control-tower`,
`AI-Project-Scope-Guard`) remain unmodified, unmoved, undeleted, and unmerged throughout —
verified by a hash-comparison test, see `tests/e2e/test_original_repos_not_modified.py`
(re-run and re-verified at the end of Phase 2 as well).

**Phase 2 status correction (factual, not a plan revision):** §11 below originally described
`Finding` and its supporting tables as Phase 3 ("Assessment, Evidence, and Scoring") work.
Phase 2's own brief required a working structured finding model, scan orchestration, and
persistence *before* Phase 3 — so `storage/db/models/{scan,file_inventory,domain_mapping,
finding,scanner_execution}.py` were implemented in Phase 2, ahead of the schedule in §11's
original table. This does not change §11's field-level design, only when it was built — see
`models/README.md` and `PHASE_2_COMPLETION_REPORT.md` for the corrected phase mapping. Full
`Control`/`Evidence`/`Score`/`Report`/`ProviderRequest`/`AuditEvent` (the control-evaluation
side of the schema) remain Phase 3+, unchanged.

**Scope of this document:** Repository audit, architecture design, and phased migration plan for combining `RAG-Engineering-Lab`, `ai-project-control-tower`, and `AI-Project-Scope-Guard` into a unified, local-first, read-only banking assurance platform.

## Plan revision notice

This document was revised after stakeholder review of the original audit-only draft. The
revision made the following decisions **final** (previously they were open questions):

1. **All 16 banking/financial assurance domains are in scope** for the target architecture,
   data model, scoring model, and reports — not a reduced pilot subset. Implementation
   remains incremental by phase (§9, §13).
2. **PostgreSQL + pgvector is the approved primary persistent backend** for the whole
   platform, not a temporary or unwanted dependency. `ai-project-control-tower`'s existing
   database/migration foundation is retained and adapted, with unsafe default credentials
   removed (§5, §6, §10, `docs/vector_backend_decision.md`).
3. **Chroma (not FAISS) is the approved secondary, local/portable vector backend** (§5, §6,
   `docs/vector_backend_decision.md`). FAISS is not part of the active platform.
4. **`ai-project-control-tower` is the primary operational skeleton** for the new repository
   (FastAPI + Streamlit + scanner + persistence pattern); `RAG-Engineering-Lab` contributes
   the RAG contracts/isolation/Chroma pattern; `AI-Project-Scope-Guard` contributes only the
   scoring/explainability mechanism, never its idea-evaluation workflow (§5).
5. **Test status wording corrected** (§2.1, §12): `ai-project-control-tower`'s test suite was
   previously validated in its original development environment — 59 tests passing, per the
   project owner's own historical record, not independently re-verified in this audit. It was
   not re-executed during either the original planning audit or the Phase 1 implementation
   session because this environment lacks its dependencies (`structlog`, `fastapi`,
   `sqlalchemy` were not installed at audit time; they were installed for Phase 1 — see
   `PHASE_1_COMPLETION_REPORT.md` — but that only made Phase 1's own new tests runnable, not
   the legacy suite, which was not executed either way).
6. **Mock banking system is a mandatory future deliverable** (new, §5.2, §13 Phase 5) — a
   controlled, entirely synthetic demonstration environment, scaffolded in Phase 1
   (`mock_banking_system/`, `scripts/seed_mock_banking_demo.py`) and populated in Phase 5.
7. **Migration phases renumbered and re-scoped** (§13): the previous Phase 0–7 plan is
   replaced by an approved Phase 1–6 plan. Phase 1 ("Unified Foundation") is implemented; see
   `PHASE_1_COMPLETION_REPORT.md`.

Everything else in this document — the repository audit findings (§2, §3, §4), the security
findings (§10), and the core architectural reasoning — was reviewed and is **unchanged**,
because it consists of verified facts about the three source repositories, not decisions
this revision was asked to revisit.

---

## How to read this document

Every claim below is labeled, implicitly or explicitly, by how it was obtained:

- **Confirmed fact** — verified by directly reading the source file (file:line references given) or by actually executing a command in this environment.
- **Architectural recommendation** — a design decision proposed for the new platform, not a description of existing code.
- **Assumption** — a reasonable inference not directly verified (e.g., contents of files inventoried but not opened).
- **Open question** — something that needs a stakeholder decision before Phase 1 can start.

No test was reported as "passing" unless it was actually executed in this session. No component is described as "production-ready." Where dependencies were missing and a test could not be run, that limitation is stated explicitly rather than assumed away.

---

## 1. Executive Summary

**What is being built:** A single, local-first "Banking Systems Assurance Platform" that scans software repositories and supporting artifacts for banking/financial systems, compares them against a control/knowledge library using a local RAG engine, produces evidence-linked findings with severity/confidence scoring, and generates human-reviewable reports — without ever writing to the inspected target and without requiring any external AI provider by default.

**Why combine three separate projects:** Each of the three source repositories already implements a materially different third of the target system, at different levels of maturity:

| Repository | What it already provides | Maturity |
|---|---|---|
| `ai-project-control-tower` | A working, if lightweight, read-only scan → RAG-retrieve → multi-agent analyze → score → report pipeline, with a FastAPI backend, Postgres/pgvector persistence, and a 9-page Streamlit UI. This is structurally the closest thing to the target platform that exists today. | Most complete; real persistence layer, real (if deterministic, non-LLM) agents, a genuinely enforced read-only invariant with a dedicated E2E test. |
| `RAG-Engineering-Lab` | A cleaner, more general-purpose local RAG core: provider-agnostic interfaces (`EmbeddingProvider`, `VectorStore`, `Chunker`, `Reranker`), four embedding providers (mock/local HuggingFace/OpenAI/Gemini) that are opt-in and disabled by default, a real security/validation layer (file validation, PII redaction, query validation, advisory prompt-injection scanning), and file-based vector stores (Chroma, FAISS) requiring no database server. | Architecturally the best RAG foundation, but has **zero executable automated tests** despite extensive testing documentation (verified — see §D and §10). |
| `AI-Project-Scope-Guard` | A small, self-contained, fully tested (14/14 tests passing, verified in this session) weighted-scoring and rule-based-explanation engine, originally built to answer "should we build this idea," not to score a system's compliance posture. | Smallest and simplest; only the scoring/explainability *mechanism* is relevant, not its build/don't-build decision semantics. |

None of the three, alone, is the target platform. `ai-project-control-tower` has the orchestration and persistence shape but a Postgres-coupled, LLM-provider-agnostic-in-name-only RAG stack and no banking domain model. `RAG-Engineering-Lab` has the right RAG isolation architecture but is not wired into any audit/governance workflow and has no real tests. `AI-Project-Scope-Guard` has a clean scoring/explanation pattern but conflates severity and confidence, and has no notion of evidence, control libraries, or human override history.

**Recommended approach:** Do not fork or "pick a winner" among the three RAG or scoring implementations. Instead:
1. Adopt `RAG-Engineering-Lab`'s **contracts and local-isolation design** (`src/core/contracts.py`, `src/core/config.py`, `src/security/*`) as the architectural foundation of the new `rag/` module, because it is the only one of the three designed from the start to be provider-agnostic, local-by-default, and network-call-auditable.
2. Adopt `ai-project-control-tower`'s **scanning, agent-orchestration, finding/scoring/report data model, and read-only enforcement pattern** as the foundation of `scanners/`, `assessment/`, `evidence/`, `scoring/`, and `governance/`, because it is the only one of the three that already runs an end-to-end pipeline with persistence and a verified non-modification test.
3. Extract only the **weighting/threshold/explainability mechanism** from `AI-Project-Scope-Guard`'s `ScopeGuardEvaluator`, generalized to score *control domains* instead of *build decisions*, and merged with `ai-project-control-tower`'s severity/category taxonomy.
4. Build net-new: a banking domain/control model, an evidence-confidence distinction (which **neither existing scoring engine currently has** — this is the single most important gap found in this audit, see §9), a human-approval/audit-history workflow, and a provider-adapter layer for optional external LLMs.

**Expected outcome of this planning phase:** A concrete, reviewable target architecture (§5–§11), an honest reuse/rewrite classification for every major component (§3), a security review with file-level evidence (§E, folded into §10), and a phased, testable migration plan (§13) that a stakeholder can approve before any code is written.

---

## 2. Current-State Summary

### 2.1 `ai-project-control-tower`

- **Purpose (as stated in its own README/CLAUDE.md):** "A local-first, read-only AI audit and governance system" that scans a repository, compares it to an uploaded Markdown "Blueprint," and produces scored, evidence-linked findings.
- **Actual architecture (verified):** FastAPI backend (`app/main.py`, `app/api/routes/*`) + SQLAlchemy models over PostgreSQL/pgvector (`app/db/models/*`) + Alembic migrations + a hybrid TF-IDF/vector RAG layer (`app/rag/*`) + six deterministic "agent" classes plus an orchestrator (`app/agents/*`) + Jinja2-based Markdown/HTML/JSON report generation with a sanitization pass (`app/reports/*`) + a 9-page Streamlit UI that talks to the API (`ui/*`) + Prometheus metrics and a pre-provisioned Grafana dashboard (`observability/*`).
- **Strengths:**
  - A real `Finding` SQLAlchemy model (`app/db/models/finding.py:7-23`) with `category`, `severity`, `title`, `description`, `evidence`, `recommendation`, `file_path`, `line_number` — very close to the target evidence-based finding schema already.
  - A genuinely read-only scanner (`app/scanner/repo_scanner.py`), verified by direct code read to only call `os.walk`, `Path.stat()`, and read-mode file opens, and backed by a real E2E test (`tests/e2e/test_no_repo_modification.py`) that hashes every file before/after a scan and asserts byte-for-byte identity, no new files, no deleted files, and idempotent results.
  - Path-traversal-safe scan-target validation (`app/scanner/path_validator.py:13-47`) that fails closed if no allowlist is configured.
  - A two-layer secret-redaction system: `app/scanner/secret_masker.py` (AWS/GitHub/OpenAI/Anthropic/Google key patterns, JWTs, `KEY=value` env-style secrets, Bearer tokens) applied again at the report layer by `app/reports/report_sanitizer.py`, which additionally strips any auto-fix/patch-plan content from generated reports (`report_sanitizer.py:7-21`) — a code-level enforcement of the "recommend, never auto-fix" principle.
- **Limitations (self-reported in `docs/04-quality-security/known_limitations.md`, and independently verified):**
  - The "7 specialist agents" are **not** LLM-backed. Direct read of `app/agents/security_agent.py` and a repo-wide grep for LLM API call patterns (`chat.completions`, `generate_content`, `messages.create`, `anthropic`) confirm zero real LLM calls anywhere in the codebase; matches are limited to docs, a settings page, and secret-masking regexes. Findings are produced by deterministic keyword/presence checks over scanned files and retrieved text chunks.
  - The RAG layer requires a live PostgreSQL instance with the `pgvector` extension (default `DATABASE_URL` in `app/core/config.py:89-91` embeds a placeholder credential, `control_tower_pass`) — it is not file-based/portable the way `RAG-Engineering-Lab`'s stores are, and has no external-embedding-provider option (`app/rag/embedding_provider.py` only supports a local `sentence-transformers` model or a zero-vector null fallback).
  - No authentication, no rate limiting, synchronous single-audit-at-a-time execution, `.git` internals and submodules not scanned, files over 1 MB skipped, Prometheus metrics reset on restart (all self-reported, `docs/04-quality-security/known_limitations.md`).
  - `CLAUDE.md` and `README.md` both refer to a `Doces/` directory as the project's "source of truth," but `git ls-tree -r HEAD` confirms this directory does not exist in the delivered repository — a documentation/reality gap, not a code defect.
  - `AI-System-Templates-Library/` and `Project-Blueprint-System/` exist as directories but are **empty** (verified via directory listing) — referenced by `AI-Project-Scope-Guard`'s UI as downstream pipeline stages, but not implemented anywhere.
- **Test status (corrected in this revision):** This repository's test suite was previously validated in its own original development environment — **59 tests passing**, per the project owner's own historical record (see `CLAUDE.md`'s Wave 5 status: "Tests + Prometheus + Grafana + docs — Complete"). This was **not independently re-verified** in either the original planning audit or the Phase 1 implementation session, because this environment did not have the suite's dependencies installed at audit time. Do not read "not re-executed here" as "unknown" or "failing" — it is a distinct, narrower claim: the suite's prior passing status is taken on the project's own record, not re-demonstrated in this session.
- **Decision (this revision):** Coupling the audit engine to a live Postgres/pgvector instance does **not** conflict with "local and isolated by default" — local-first does not mean file-only. PostgreSQL + pgvector is the platform's approved primary persistent backend (see "Plan revision notice" above and `docs/vector_backend_decision.md`); it runs locally via Docker Compose. `app/rag/*`'s hybrid TF-IDF+vector logic is still **refactored, not reused as-is** (§3): it must be rebuilt against the platform's own `VectorStore` contract (`core/contracts.py`, implemented in Phase 1) rather than its original ad hoc coupling to scan chunks.

### 2.2 `RAG-Engineering-Lab`

- **Purpose (per `docs/architecture.md` and README):** A modular, local-first RAG retrieval-evaluation framework with pluggable chunkers, embedding providers, and vector stores, and IR evaluation metrics (Recall@K, Precision@K, MRR, nDCG).
- **Actual architecture (verified):** Clean abstract contracts (`src/core/contracts.py`: `Document`, `Chunk`, `EmbeddingProvider`, `VectorStore`, `Chunker`, `Reranker`) consumed by a thin orchestrator (`src/pipeline/rag_pipeline.py`), four embedding providers (`mock` — default, local hash-based; `huggingface` — local `sentence-transformers`; `openai`/`gemini` — external, opt-in, fail fast at construction if no API key, verified never logged), two local vector stores (`chroma_store.py`, `faiss_store.py`), a dedicated `security/` package, and a lightweight zero-dependency `observability/` package (counters + latency timers + health-check dicts).
- **Strengths:**
  - `AppSettings` (`src/core/config.py:8-62`) defaults `mock_mode=True`, `embedding_provider="mock"`, and both `openai_api_key`/`gemini_api_key` to empty — the local-only default is enforced in code, not just documentation.
  - `src/security/file_validation.py` sanitizes uploaded filenames via `os.path.basename()` plus a character allowlist (`file_validation.py:42-70`), preventing path traversal on ingestion; wired into the Streamlit app's `_save_upload()` (`app/streamlit_app.py:117-128`), confirmed by direct read.
  - `src/security/prompt_safety.py` and `src/security/pii_redaction.py` are the only prompt-injection-awareness and PII-redaction code found across all three repositories.
  - Genuinely provider-agnostic interfaces make this the best available seed for a provider-adapter pattern (embeddings today; the same shape generalizes to LLM providers, see §7).
- **Limitations (verified, not assumed):**
  - **`tests/unit/`, `tests/integration/`, and `tests/e2e/` contain only `__init__.py` files — zero test functions.** Confirmed by directory listing and by actually running `pytest tests/` in this session, which reported `no tests ran in 0.01s`.
  - `docs/testing_strategy.md` describes an elaborate four-layer testing approach (stage smoke tests, unit, integration, e2e) in detail, including a table of `_stageN_smoke_test.py` files with specific claimed coverage — none of these files exist anywhere in the repository (verified via `find`). This is a documentation-vs-reality gap that must not be carried forward into the new platform's documentation.
  - `src/retrieval/hybrid_retriever.py` is an intentional stub that raises `RetrievalError("Hybrid retrieval is planned for a future version.")` on every call (verified by reading the file in full) — dense-only retrieval is the only working retrieval mode.
  - No multi-user auth/session isolation (by design, per `docs/known_limitations.md` — acceptable for a local single-user lab, not acceptable as-is for a shared assurance platform).
- **Technical risk:** The gap between documented and actual test coverage means this codebase's correctness has **not** been independently verified by its own test suite; adopting it as the platform's RAG foundation requires writing the tests that were promised but never delivered before it can be trusted with banking-sensitive documents.

### 2.3 `AI-Project-Scope-Guard`

- **Purpose:** A "Build / Don't Build" evaluator for AI *project ideas* (not for auditing existing systems) — four inputs (name/description/target user) plus eight 1–10 dimension scores, producing one of five hardcoded decisions.
- **Actual architecture (verified, full file read):** `src/scope_guard/models.py` defines `ProjectIdea` and `EvaluationResult` dataclasses; `src/scope_guard/evaluator.py`'s `ScopeGuardEvaluator.evaluate()` computes `positive = bv*2 + pf*2 + tu + lv + dr`, `negative = ef + rl + ow*2`, `score = clamp(0, 100, positive*10 - negative*5)`, applies two hardcoded override rules, then five score-threshold bands, and generates strengths/risks/next-steps text via simple per-field `if` checks. All weights and thresholds are hardcoded Python literals — there is no external config file.
- **Strengths:**
  - Small, readable, and **the only one of the three repositories whose test suite was actually run and passed in this session**: `pytest tests/test_evaluator.py` → `14 passed in 0.02s`.
  - A genuinely useful pattern for the new platform: deterministic, rule-based, human-readable rationale generation (strengths/risks/next-steps) attached to a numeric score — this maps directly onto the "explain how the score was calculated" requirement in §9.
  - `static-site/app.js` was verified to contain only cosmetic scroll-reveal animation code — **no duplicate scoring logic exists in JavaScript**, so there is no cross-language scoring conflict to resolve.
- **Limitations (verified):**
  - Conflates confidence and severity entirely — there is exactly one score, one decision, and no notion of "we don't have enough evidence yet" versus "we checked and it's fine." This is a structural gap, not a missing feature.
  - No persistence, no audit history of decisions, no human-override mechanism, no domain/weight configurability.
  - Its core decision semantics ("should this idea be built") are not meaningful for a compliance/assurance platform and must **not** be carried forward — only the scoring/weighting/explainability *mechanism* is reusable, exactly as this audit's brief specified.
- **Technical risk:** Low — this is the least architecturally significant of the three repositories and carries the least risk; the risk is entirely in how much of its (currently very simple) approach is deemed sufficient for banking-grade explainability, which will need real hardening (see §9).

---

## 3. Component Reuse Matrix

| Repository | Component | Current Responsibility | Proposed Responsibility | Action | Reason | Dependencies | Risk |
|---|---|---|---|---|---|---|---|
| RAG-Engineering-Lab | `src/core/contracts.py` | Provider-agnostic DTOs + ABCs for embeddings/vector store/chunker/reranker | Core contracts for `rag/` module | **Reuse as-is** | Clean, dependency-free, already the right abstraction boundary | None (stdlib + dataclasses) | Low |
| RAG-Engineering-Lab | `src/core/config.py` | Pydantic settings, local-mode defaults | Base for `config/` module's RAG section | **Reuse with minor adaptation** | Needs to merge with control-tower's `Settings` and add platform-wide fields (allowed scan paths, provider enablement flags) | pydantic-settings | Low |
| RAG-Engineering-Lab | `src/embeddings/mock_embedding_provider.py`, `huggingface_provider.py` | Local embedding generation | Default local embedding providers | **Reuse as-is** | Fully local, no network calls found in these two files | sentence-transformers (huggingface only) | Low |
| RAG-Engineering-Lab | `src/embeddings/openai_provider.py`, `gemini_provider.py` | Optional external embeddings | Seed pattern for the optional external-provider *adapter* layer (§7), not necessarily embeddings specifically | **Refactor before reuse** | Correct fail-closed/no-log-key pattern, but needs to move behind the platform's approval/sanitization gate rather than being called directly from the pipeline | openai, google-generativeai (both optional) | Medium — must not become a silent default path |
| RAG-Engineering-Lab | `src/vectorstores/chroma_store.py` | Local, file-based vector persistence | Secondary/portable vector store backend (**implemented in Phase 1** as `rag/vectorstores/chroma_store.py`) | **Reuse with minor adaptation — done** | Adapted with a document-deletion/re-indexing API and metadata filters the original interface didn't expose; verified against a real local Chroma instance in `tests/integration/test_chroma_vectorstore.py` (5 tests, passing) | chromadb | Low |
| RAG-Engineering-Lab | `src/vectorstores/faiss_store.py` | Local, file-based vector persistence | N/A | **Archive — not selected** (this revision) | Chroma was chosen as the platform's secondary backend instead (better persistent-collection/metadata-filtering/deletion support); FAISS adds no implementation or maintenance burden to the new system. See `docs/vector_backend_decision.md`. | — | Low |
| RAG-Engineering-Lab | `src/retrieval/retriever.py` | Dense retrieval with validation | Base dense retriever | **Reuse as-is** | Clean separation of concerns, already validates inputs via `security/` | — | Low |
| RAG-Engineering-Lab | `src/retrieval/hybrid_retriever.py` | Stub, raises `NotImplementedError`-equivalent | N/A — superseded | **Remove / replace** | Non-functional; `ai-project-control-tower`'s `app/rag/hybrid_retriever.py` (TF-IDF + vector, weighted merge) is an actual working implementation and should be adapted instead | — | Low (dead code) |
| RAG-Engineering-Lab | `src/security/file_validation.py`, `query_validation.py` | Upload/query input validation | Core `governance/` input-validation layer | **Reuse as-is** | Correct path-traversal handling, no dependencies | — | Low |
| RAG-Engineering-Lab | `src/security/pii_redaction.py`, `prompt_safety.py` | Regex PII redaction; advisory-only prompt-injection scan | Seed for `governance/sanitization` module | **Refactor before reuse** | Both are explicitly documented as non-exhaustive/advisory-only; banking use requires the injection scan to become a configurable hard gate, and PII patterns need extension (see §10) | — | Medium |
| RAG-Engineering-Lab | `src/chunking/*` | Fixed and recursive chunking | Default chunkers | **Reuse as-is** | Self-contained, well-structured, no external deps beyond stdlib | — | Low |
| RAG-Engineering-Lab | `src/observability/*` | In-process counters, timers, health dicts | Baseline for `governance/` metrics until Prometheus is wired platform-wide | **Reuse with minor adaptation** | Useful, but should ultimately be superseded by control-tower's Prometheus integration for the unified platform | — | Low |
| RAG-Engineering-Lab | `tests/` (unit/integration/e2e) | Documented but **empty** | N/A | **Rewrite** | Zero executable tests exist despite detailed docs describing them; must be authored from scratch before this code is trusted with banking data | pytest | High if skipped |
| RAG-Engineering-Lab | `static-site/`, notebooks | Personal portfolio marketing page / demo notebooks | N/A | **Archive** | Personal-brand marketing content ("built by Oren Salami"); not part of a bank-facing product and not functional application code | — | Low |
| ai-project-control-tower | `app/scanner/repo_scanner.py`, `file_classifier.py` | Read-only repository crawl + classification | Core of `scanners/` module | **Reuse as-is** | Verified read-only via direct code read and a passing-by-design E2E hash-comparison test; well-isolated, minimal deps | — | Low |
| ai-project-control-tower | `app/scanner/path_validator.py` | Allowlist-based path traversal prevention, fail-closed | Core of `governance/` scan-target validation | **Reuse as-is** | Correct, minimal, fails closed when unconfigured | — | Low |
| ai-project-control-tower | `app/scanner/secret_masker.py` | Regex secret detection/masking | Core of `governance/sanitization` | **Reuse with minor adaptation** | Solid pattern coverage (AWS/GitHub/OpenAI/Anthropic/Google/JWT/env-style); extend with banking-specific PANs, IBANs, routing numbers before production use | — | Low |
| ai-project-control-tower | `app/reports/report_sanitizer.py` | Strips auto-fix content + re-masks secrets in generated reports | Core enforcement of "recommend, never auto-fix" at the reporting boundary | **Reuse as-is** | Directly implements a hard platform requirement | secret_masker | Low |
| ai-project-control-tower | `app/audit/audit_engine.py`, `base_agent.py`, `orchestrator_agent.py` | Orchestrates scan → RAG-index → agents → score → persist | Core of `assessment/` orchestration | **Refactor before reuse** | Correct control flow and per-agent failure isolation, but "agents" are hardcoded Python classes with no plug-in registry, no confidence output, and no banking-domain awareness — needs generalizing into a control-driven (not agent-class-driven) evaluation loop | app/rag, app/scanner | Medium |
| ai-project-control-tower | `app/agents/*.py` (6 concrete agents) | Deterministic keyword/presence checks | Seed logic for specific banking-domain scanners (e.g., security checks → `scanners/security_controls.py`) | **Refactor before reuse** | The checks themselves (`.gitignore` presence, hidden files, hardcoded-credential keyword scan) are generic-repo-hygiene checks, not banking controls; the *pattern* (produce a `FindingModel` per rule) is reusable, the *rules* are not banking-specific and need to be replaced/extended | — | Medium |
| ai-project-control-tower | `app/audit/models.py` (`FindingModel`, `Severity`, `AuditScores`, `AuditResult`) | Pydantic finding/score schema | Base of `models/finding.py` and `models/score.py` | **Reuse with minor adaptation** | Very close to the target schema already; missing `confidence`, `source_reference` (beyond `file_path`), and `human_review_status` fields (§D, §11) | pydantic | Low |
| ai-project-control-tower | `app/db/models/finding.py`, `audit_run.py`, `blueprint.py`, `report.py`, `project.py` | SQLAlchemy persistence schema | Base of `storage/` schema | **Reuse with minor adaptation** | Solid relational shape; needs new tables for controls, evidence, audit/override history, and provider-request logging (§11) | SQLAlchemy, Alembic | Low |
| ai-project-control-tower | `app/audit/scoring.py` | Per-dimension, severity-weighted deduction from 100 | Seed for `scoring/` engine | **Refactor before reuse** | Reasonable aggregation mechanics, but hardcoded weights, a fixed 8-dimension taxonomy not aligned to banking domains, and — critically — no way to distinguish "no findings because it's clean" from "no findings because we never checked" (§9) | app/audit/models | Medium |
| ai-project-control-tower | `app/rag/*` (hybrid TF-IDF+vector, chunker, indexer) | Postgres/pgvector-backed hybrid retrieval, tightly coupled to scan chunks | Retained as an *optional* hybrid retrieval strategy layered on the new `rag/` `VectorStore` interface | **Refactor before reuse** | Working hybrid-merge logic (`hybrid_retriever.py:40-81`) is worth keeping, but the hard Postgres/pgvector dependency conflicts with "local and isolated by default"; must be re-pointed at the RAG-Lab-style local store interface, or offered as an alternate, explicitly opt-in backend | PostgreSQL + pgvector | Medium-High (infra dependency conflict) |
| ai-project-control-tower | `app/reports/report_generator.py` + Jinja2 templates | MD/HTML/JSON report rendering | Core of `reporting/` | **Reuse with minor adaptation** | Working, sanitized, three formats already; needs new banking-domain report sections (§9 of the source brief) | jinja2 | Low |
| ai-project-control-tower | `ui/` (9-page Streamlit app calling a FastAPI backend via `ui/services/api_client.py`) | Interactive audit UI | Template/pattern for the new platform's `app/` UI layer | **Refactor before reuse** | The page/component/service separation is the right pattern (better than RAG-Lab's single-file UI or Scope-Guard's single page); page content itself needs a full banking-domain rewrite | streamlit, FastAPI backend | Medium |
| ai-project-control-tower | `observability/` (Prometheus config + Grafana dashboard), `app/core/metrics.py` | Metrics collection and dashboarding | Platform-wide observability | **Reuse with minor adaptation** | Existing pattern is sound; dashboard content needs banking-assurance-specific panels | prometheus-client | Low |
| ai-project-control-tower | `AI-System-Templates-Library/`, `Project-Blueprint-System/` | Referenced by Scope-Guard's UI narrative; **empty directories** | N/A | **Remove** | Zero content to reuse; purely aspirational placeholders | — | Low |
| ai-project-control-tower | `static-demo/`, `notebooks/` | Personal portfolio marketing site / demo notebooks | N/A | **Archive** | Same rationale as RAG-Lab's static-site — portfolio branding, not product code | — | Low |
| ai-project-control-tower | `Doces/` (referenced in `CLAUDE.md` as source of truth) | Unknown — **directory does not exist in this repository** | N/A | **Not relevant / unresolved** | Cannot classify content that was not delivered; flag as an open question (§16) rather than guess | — | N/A |
| AI-Project-Scope-Guard | `src/scope_guard/evaluator.py` — weighting/threshold/explanation *mechanism* | Weighted-sum scoring, threshold-to-label mapping, rule-based strengths/risks/next-steps text | Pattern seed for `scoring/` explainability layer | **Rewrite** | The mechanism (weights → score → banded decision → generated rationale) is worth keeping conceptually, but every weight, threshold, and decision label is specific to "should we build this idea" and must be replaced wholesale with banking-domain weights/decision categories; safest to rewrite against the new schema rather than adapt in place | — | Low |
| AI-Project-Scope-Guard | `src/scope_guard/evaluator.py` — build/reduce/postpone/reject *decision workflow* | Idea-acceptance decision | N/A | **Remove** | Explicitly out of scope per this audit's brief; not a meaningful concept for a compliance/assurance platform | — | Low |
| AI-Project-Scope-Guard | `tests/test_evaluator.py` | Verifies evaluator arithmetic/decisions | N/A | **Archive** | Tests the old decision semantics being removed; useful only as a reference for testing style (well-structured, arrange/act/assert, boundary-value coverage) | pytest | Low |
| AI-Project-Scope-Guard | `static-site/`, `app/streamlit_app.py`, notebooks | Marketing/demo UI for the idea-evaluator | N/A | **Archive** | Portfolio content and a single-purpose demo UI, superseded entirely by the new platform's scoring UI | streamlit | Low |

---

## 4. Duplicate and Obsolete Components

**Duplicate/competing RAG implementations (resolved in this revision):**
- `RAG-Engineering-Lab`'s file-based Chroma/FAISS stack (no DB server, 4 embedding providers) vs. `ai-project-control-tower`'s Postgres/pgvector hybrid TF-IDF+vector stack (1 local embedding provider or null fallback, requires a live database). These were not drop-in compatible. **Resolved:** neither implementation is adopted wholesale. The platform defines its own `VectorStore` contract (`core/contracts.py`) with two conformant backends — `rag/vectorstores/pgvector_store.py` (primary, net-new against the platform's own contract, not a reuse of `app/rag/hybrid_retriever.py`) and `rag/vectorstores/chroma_store.py` (secondary, adapted from `RAG-Engineering-Lab`). FAISS is not selected for the active platform. See `docs/vector_backend_decision.md`.

**Duplicate scoring philosophies:**
- `AI-Project-Scope-Guard`'s single weighted linear score with two override rules, vs. `ai-project-control-tower`'s per-dimension severity-weighted deduction from 100. Neither distinguishes confidence from severity or missing evidence from a clean check — this is a shared gap, not just a duplication, and is addressed in §9.

**Duplicate/near-duplicate Streamlit UIs:**
- Three separate Streamlit apps (`RAG-Engineering-Lab/app/streamlit_app.py`, `AI-Project-Scope-Guard/app/streamlit_app.py`, `ai-project-control-tower/ui/main.py` + 9 pages) with three different structural patterns (single 633-line file; single ~260-line file; multi-file page/component/service package). Only the control-tower pattern is recommended going forward (§5).

**Duplicate/inconsistent configuration systems:**
- Three separate `pydantic-settings`-based (or ad hoc) configuration objects: `RAG-Engineering-Lab/src/core/config.py`, `ai-project-control-tower/app/core/config.py`, and no formal settings object in `AI-Project-Scope-Guard` (hardcoded constants). These need to be unified into one `config/` module (§5).

**Demo-only / portfolio-only code (not product code):**
- `RAG-Engineering-Lab/static-site/`, `ai-project-control-tower/static-demo/`, `AI-Project-Scope-Guard/static-site/` — all three are personal-portfolio marketing pages (confirmed by reading `RAG-Engineering-Lab/static-site/index.html`, which is branded "RAG Engineering Lab — Oren Salami"). None of these should be carried into a bank-facing product surface.
- All three repositories' `notebooks/` directories are demonstration/conceptual notebooks, not part of the runtime system.

**Obsolete/placeholder scaffolding:**
- `ai-project-control-tower/AI-System-Templates-Library/` and `ai-project-control-tower/Project-Blueprint-System/` are empty directories referenced only by `AI-Project-Scope-Guard`'s UI narrative diagram. There is nothing to migrate.
- `RAG-Engineering-Lab/src/retrieval/hybrid_retriever.py` is dead-stub code (raises on every call) superseded by a working implementation in the other repository.

**Documentation that does not match delivered code (flag, do not silently inherit):**
- `RAG-Engineering-Lab/docs/testing_strategy.md` describes tests and smoke-test scripts that do not exist in the repository.
- `ai-project-control-tower/CLAUDE.md` / `README.md` reference a `Doces/` "source of truth" directory absent from the delivered repository.

**Recommended removals (not performed in this phase — see §15 for the full plan):** the three `static-site`/`static-demo` marketing directories, `AI-System-Templates-Library/`, `Project-Blueprint-System/`, `RAG-Engineering-Lab/src/retrieval/hybrid_retriever.py` (stub), and `AI-Project-Scope-Guard`'s idea-decision workflow (`_decide`, `_label`, `_next_steps` methods and their five build/reduce/postpone/reject labels).

---

## 5. Target Architecture

### 5.1 Overview

The platform is organized as a single local application (FastAPI backend + Streamlit UI, following `ai-project-control-tower`'s pattern, which is the only one of the three with a working API/UI separation) with four hard boundaries:

1. **Scan boundary** — read-only access to inspection targets, enforced by an allowlist validator and a filesystem-hash-verifying test, both inherited from `ai-project-control-tower`.
2. **Local RAG boundary** — all document/embedding/vector storage stays on local disk by default, enforced by config defaults inherited from `RAG-Engineering-Lab`.
3. **Governance boundary** — every report and every piece of retrieved/generated content passes through sanitization (secret masking, auto-fix stripping, PII redaction) before it reaches a human or an optional external provider.
4. **External-provider boundary** — disabled by default; when enabled, only sanitized, size-limited, explicitly-approved context can cross it, and every call is logged.

### 5.2 Proposed directory structure

**Note (this revision):** the structure below is the original target design. What is
actually implemented as of Phase 1 — including where it deviates from this illustrative tree
(e.g. no nested `banking-systems-assurance-platform/` folder; `core/config.py` rather than a
second settings module under `config/`; a `rag/vectorstores/pgvector_store.py` alongside
`chroma_store.py`, both behind `rag/vectorstores/registry.py`) — is recorded in
`docs/architecture.md`, not here. Treat this tree as design intent; treat `docs/architecture.md`
and `PHASE_1_COMPLETION_REPORT.md` as the record of what exists.

```
banking-systems-assurance-platform/
├── app/                      # FastAPI backend entrypoint + API routes
│   └── api/routes/           # REUSE (adapt): ai-project-control-tower/app/api/routes/*
├── ui/                       # Streamlit UI: pages + components + services
│   ├── pages/                # REWRITE: banking-domain pages, control-tower's ui/pages/ as structural template
│   ├── components/           # REUSE (adapt): ai-project-control-tower/ui/components/
│   └── services/              # REUSE (adapt): ai-project-control-tower/ui/services/api_client.py
├── core/                     # Shared config, logging, exceptions, contracts
│   ├── config.py             # REWRITE (merge): RAG-Lab AppSettings + control-tower Settings
│   ├── contracts.py          # REUSE as-is: RAG-Engineering-Lab/src/core/contracts.py
│   ├── exceptions.py         # REUSE (merge): both repos' exception hierarchies
│   └── logging.py            # REUSE as-is: ai-project-control-tower/app/core/logging.py (structlog)
├── scanners/                 # Read-only inspection of targets
│   ├── repo_scanner.py       # REUSE as-is: ai-project-control-tower/app/scanner/repo_scanner.py
│   ├── file_classifier.py    # REUSE as-is: ai-project-control-tower/app/scanner/file_classifier.py
│   └── path_validator.py     # REUSE as-is: ai-project-control-tower/app/scanner/path_validator.py
├── rag/                      # Local, isolated RAG core
│   ├── contracts.py          # (re-exported from core/contracts.py)
│   ├── ingestion/            # REUSE (adapt): RAG-Engineering-Lab/src/ingestion/*
│   ├── chunking/             # REUSE as-is: RAG-Engineering-Lab/src/chunking/*
│   ├── embeddings/           # REUSE (adapt): RAG-Engineering-Lab/src/embeddings/* (local providers as-is; external providers moved behind providers/ gate)
│   ├── vectorstores/         # REUSE (adapt): RAG-Engineering-Lab/src/vectorstores/*
│   ├── retrieval/            # REUSE (adapt) + REWRITE hybrid: dense retriever from RAG-Lab, hybrid merge logic adapted from ai-project-control-tower/app/rag/hybrid_retriever.py
│   └── pipeline.py           # REUSE (adapt): RAG-Engineering-Lab/src/pipeline/rag_pipeline.py
├── knowledge_base/           # Control library, policy documents, banking domain reference material (net-new)
│   ├── controls/             # REWRITE: banking control library (net-new content)
│   └── lifecycle.py          # NEW: ingestion approval, deletion, re-indexing
├── controls/                 # Control definitions and control-to-domain mapping (NEW)
├── assessment/                # Orchestration: run scan → retrieve → evaluate controls → findings
│   ├── engine.py              # REFACTOR: ai-project-control-tower/app/audit/audit_engine.py, generalized from "agent classes" to "control evaluators"
│   └── evaluators/            # REFACTOR: ai-project-control-tower/app/agents/*.py, rules re-targeted at banking controls
├── evidence/                  # Evidence capture and evidence-to-finding linkage (NEW, seeded by FindingModel.evidence field)
├── scoring/                   # Weighting, aggregation, decision categories
│   └── engine.py               # REWRITE (merge mechanism from AI-Project-Scope-Guard/src/scope_guard/evaluator.py + dimension aggregation from ai-project-control-tower/app/audit/scoring.py) + NEW confidence/evidence-completeness handling
├── governance/                 # Read-only enforcement, sanitization, human-approval workflow, audit trail
│   ├── secret_masker.py        # REUSE as-is: ai-project-control-tower/app/scanner/secret_masker.py
│   ├── report_sanitizer.py     # REUSE as-is: ai-project-control-tower/app/reports/report_sanitizer.py
│   ├── pii_redaction.py        # REFACTOR: RAG-Engineering-Lab/src/security/pii_redaction.py (extend patterns)
│   ├── prompt_safety.py        # REFACTOR: RAG-Engineering-Lab/src/security/prompt_safety.py (advisory → configurable hard gate)
│   ├── approval_workflow.py    # NEW: human-in-the-loop review/override tracking
│   └── audit_trail.py          # NEW: append-only log of all governance-relevant events
├── reporting/                  # Report generation
│   ├── report_generator.py     # REUSE (adapt): ai-project-control-tower/app/reports/report_generator.py
│   └── templates/               # REWRITE: banking-domain report sections
├── providers/                  # Optional external AI provider adapters (NEW, see §7)
│   ├── base.py                  # NEW: shared provider interface
│   ├── openai_adapter.py        # NEW (pattern seeded by RAG-Engineering-Lab/src/embeddings/openai_provider.py)
│   ├── gemini_adapter.py        # NEW (pattern seeded by RAG-Engineering-Lab/src/embeddings/gemini_provider.py)
│   └── claude_adapter.py        # NEW
├── models/                      # Pydantic/SQLAlchemy data models
│   ├── finding.py                # REUSE (adapt): ai-project-control-tower/app/audit/models.py + app/db/models/finding.py
│   ├── control.py, evidence.py, score.py, report.py, provider_request.py, audit_event.py  # NEW (§11)
├── storage/                     # Persistence layer
│   └── db/                       # REUSE (adapt): ai-project-control-tower/app/db/* + Alembic migrations
├── config/                      # Environment/config management
├── tests/                        # REWRITE (RAG-Lab tests from scratch; adapt control-tower's real test suite; archive Scope-Guard tests as style reference)
│   ├── unit/ integration/ e2e/ isolation/ security/   # implemented in Phase 1
├── mock_banking_system/          # NEW (this revision): synthetic demo environment, scaffolded Phase 1, populated Phase 5
├── docs/
├── scripts/                      # includes seed_mock_banking_demo.py (Phase 1: documented placeholder; Phase 5: implemented)
└── deployment/                   # Docker Compose (adapted from ai-project-control-tower's multi-service compose file)
```

### 5.3 Data flow (high level)

```
Target repo/artifacts
   → scanners/ (read-only crawl, hash, classify)
   → rag/ (ingest approved artifacts → chunk → embed locally → store locally)
   → knowledge_base/controls (banking control library, also chunked/embedded/stored locally)
   → assessment/engine (retrieve relevant controls + evidence via rag/retrieval)
   → evidence/ (capture what was found, link to source)
   → scoring/engine (weight + aggregate + assign confidence + decision category)
   → governance/ (sanitize, gate, require human review)
   → reporting/ (render MD/HTML/JSON, sanitized)
   → optional providers/ adapter (only for approved, sanitized, minimized context; logged)
```

### 5.4 Security boundaries by module

- `scanners/`, `governance/path_validator` — filesystem read boundary (allowlist-enforced, no writes).
- `rag/` — local-network boundary (no external calls unless an embedding/LLM provider is explicitly configured).
- `providers/` — the only module permitted to make external network calls, and only when explicitly enabled.
- `governance/` — the mandatory choke point between any internal content and (a) the human reviewer's report and (b) the `providers/` boundary.

---

## 6. Local RAG Architecture

**Vector backend (this revision):** PostgreSQL + pgvector is the approved primary persistent
backend; Chroma is the approved secondary, portable/local backend. FAISS is not part of the
active platform. See `docs/vector_backend_decision.md` for the full rationale and operating
modes (`VECTOR_BACKEND=pgvector` default full-platform mode; `VECTOR_BACKEND=chroma` portable/
testing/demo mode). Both modes are local-first: pgvector runs against a local Docker Compose
Postgres instance, never a remote/managed database by default; Chroma's `PersistentClient`
requires no server at all. Local-first does not mean file-only.

**What remains local by default:** Document storage (`data/documents/`), vector storage (pgvector on a local Postgres instance, or Chroma on local disk), embedding generation (mock or local `sentence-transformers` model), retrieval, and all evaluation. This mirrors `RAG-Engineering-Lab`'s verified default configuration (`AppSettings.mock_mode = True`, `embedding_provider = "mock"`, both external API keys empty by default), now merged into `core.config.Settings` (`local_only_mode=True`, `external_providers_enabled=False`, no API keys by default — implemented in Phase 1).

**How isolation is enforced:**
- Config-level: external embedding/LLM providers require a non-empty API key to even construct (`openai_provider.py:34-40`, `gemini_provider.py:41-47` both raise `EmbeddingError` at construction if the key is absent) — this fail-fast pattern is reused directly and extended to the new `providers/` adapters (§7).
- Code-level: only `providers/*_adapter.py` modules are permitted to import network client libraries; this should be enforced by a lint rule / import-boundary test in `tests/isolation/`.
- Network-disable mode: a platform-wide `EXTERNAL_PROVIDERS_ENABLED=false` flag (default `false`) that short-circuits `providers/` construction entirely, independent of individual provider keys.

**How documents are processed:** Upload/select → `governance` file validation (extension allowlist + size limit + filename sanitization, from `RAG-Engineering-Lab/src/security/file_validation.py`) → optional PII redaction → chunking (`rag/chunking`, fixed or recursive) → embedding (local by default) → vector store `add()`.

**How sources are cited:** Every `Chunk` carries `doc_id`, `chunk_id`, `metadata` (including `source`/`file_name`), and post-retrieval `score`/`rank` (`RAG-Engineering-Lab/src/core/contracts.py:26-40`). This is already sufficient to populate the `source_reference` field of the target `Finding` model (§11) — reuse as-is.

**How external access is prevented by default:** No module outside `providers/` should hold a `requests`/`httpx`/vendor-SDK import. `rag/embeddings/huggingface_provider.py` downloads model weights from the internet **once**, on first use, if not already cached — this is a one-time bootstrap dependency, not a per-query network call, but it must be disclosed to operators (an offline/air-gapped deployment needs the model pre-cached).

**What existing RAG Lab components already provide vs. need improvement:**

| Capability | Status |
|---|---|
| Local document storage | Provided (`data/raw/`) |
| Local vector storage | Provided — implemented in Phase 1 as `rag/vectorstores/{chroma_store,pgvector_store}.py` (Chroma verified against a live local instance; pgvector verified for construction/graceful-failure only, no live server available) |
| Local embedding generation | Provided (mock + HuggingFace) |
| Local retrieval | Provided (dense only — hybrid is a stub, see §4) |
| Source citations | Provided (`Chunk.metadata`, `.score`, `.rank`) |
| Document classification | **Missing** — no sensitivity/classification tagging on ingested documents |
| Ingestion approval workflow | **Missing** — any file passing validation is ingested immediately, no human gate |
| Deletion / re-indexing | **Partial** — `VectorStore.clear()` wipes everything; no per-document delete or selective re-index |
| Isolation from external providers | Provided by default config; **not yet enforced by an automated test** |
| Network-disable mode | **Missing** — no single kill-switch flag exists today |
| Audit logging of retrieval | **Missing** — `METRICS.query_count_total` counts queries but does not log *what* was retrieved or by whom |

---

## 7. Optional External Agent Architecture

**Design principle:** Generalize the embedding-provider pattern already proven in `RAG-Engineering-Lab` (`src/embeddings/{openai,gemini}_provider.py`) into a provider-adapter pattern for full LLM providers.

**Shared provider interface (new, `providers/base.py`):**
```python
class ProviderAdapter(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...       # False if disabled or unconfigured
    @abstractmethod
    def send(self, request: ProviderRequest) -> ProviderResponse: ...
    @property
    @abstractmethod
    def provider_name(self) -> str: ...
```
`ProviderRequest` carries only sanitized, size-capped context (never raw findings, never raw source files) plus a `purpose` tag and an `approved_by` field populated by the governance approval gate.

**Per-provider adapters:** `openai_adapter.py`, `gemini_adapter.py`, `claude_adapter.py` — each follows the exact fail-fast, never-log-key pattern already verified in `RAG-Engineering-Lab`'s embedding providers (raise at construction if key absent; lazy client import so the SDK is only required when actually used).

**Activation rules:**
- `EXTERNAL_PROVIDERS_ENABLED=false` by default at the platform level (kill switch).
- Each individual provider additionally requires its own API key to be set.
- Both conditions must hold before `providers/registry.get_provider(name)` returns anything other than `None`.

**Approval and sanitization controls:**
- Every outbound `ProviderRequest` passes through `governance/report_sanitizer.py` and `governance/pii_redaction.py` before construction — reusing the exact sanitization functions already used for human-facing reports, so there is one sanitization implementation, not two.
- A human-approval gate (`governance/approval_workflow.py`, new) must mark a specific finding/context bundle as "approved for external sharing" before it can be included in a `ProviderRequest`. No automatic, unattended calls to external providers are permitted.

**Failure and fallback behavior:** Timeouts (configurable, short default e.g. 30s), bounded retry count (default 1–2), and a hard token/context-size cap per request. On any failure or unavailability, the platform falls back to **local-only mode** — i.e., the assessment/report simply omits the optional external-provider enrichment rather than blocking or degrading the core (local) assurance flow. This mirrors the graceful-degradation pattern already used by `ai-project-control-tower/app/rag/embedding_provider.py::get_embedding_provider()`, which falls back to a null provider when `sentence-transformers` is unavailable.

**Logging:** Every `ProviderRequest`/`ProviderResponse` pair is written to a new `provider_requests` audit table (§11) — provider name, purpose, sanitized-context hash (not the raw content), token/byte counts, latency, success/failure, and the approving human identity.

**What external providers can never see:** The complete local knowledge base, raw source code, raw scan results, or unredacted findings. Only the specific, human-approved, sanitized context bundle for a single request.

---

## 8. Read-Only Assurance Flow

1. **Select assessment target** — operator specifies a repository path (or export bundle); `scanners/path_validator.py` (reused as-is) validates it against the configured allowlist and fails closed if unconfigured.
2. **Ingest approved artifacts** — supporting documents (policies, architecture docs, prior audit reports) are uploaded through `rag/ingestion`, validated (`governance/file_validation.py`), optionally PII-redacted, and stored locally.
3. **Scan repository or exported system data** — `scanners/repo_scanner.py` performs a read-only crawl, hashing and classifying every in-scope file; verified never to write to the target.
4. **Retrieve relevant controls and knowledge** — `assessment/engine.py` queries `rag/retrieval` against both the ingested supporting documents and the `knowledge_base/controls` library.
5. **Compare evidence against requirements** — control evaluators (generalized from `ai-project-control-tower/app/agents/*`) run against scan results + retrieved context, each producing zero or more `FindingModel` instances with `evidence`, `source_reference`, and a **confidence** value (new — see §9) alongside severity.
6. **Calculate findings and scores** — `scoring/engine.py` aggregates findings per domain using weighted, severity-and-confidence-aware rules, and explicitly flags domains with **insufficient evidence** rather than defaulting them to a clean 100/100 score (fixing the single largest gap identified in this audit).
7. **Require human review** — every finding and every score defaults to `human_review_status = "pending"`; no report is marked "final" until a reviewer acts, per `governance/approval_workflow.py` (new).
8. **Generate reports** — `reporting/report_generator.py` (adapted) renders Markdown/HTML/JSON, passed through `governance/report_sanitizer.py` (reused as-is) before being written or displayed.
9. **Export recommendations** — recommendations are exported as advisory text/structured data only; no executable patches, diffs, or auto-fix instructions are ever generated (enforced by `report_sanitizer.py`'s existing auto-fix-stripping regexes, reused as-is).
10. **No automatic changes** — at no point in this flow does any component open a file in the target repository in write mode; this is the platform-wide invariant that the E2E test pattern from `ai-project-control-tower/tests/e2e/test_no_repo_modification.py` must be extended to cover every module in the flow, not just the scanner (§12).

---

## 9. Banking Domain Model

**Approved, final domain set — all 16, not a pilot subset (this revision).** Implemented in
`core/domains.py::BankingDomain` (Phase 1) as the single canonical definition; every other
module (models, scoring, reports, controls, mock data, UI) must import this enum rather than
defining its own list. Verified: exactly 16 members, unique values and labels, tested in
`tests/unit/test_domains.py`. Each domain maps to a `scoring` dimension, replacing the
existing 8 generic dimensions in `ai-project-control-tower/app/audit/scoring.py`. Content
authoring (subdomains, controls, evidence types per domain) remains incremental by phase —
see below.

- Core banking & account management
- Payments
- Credit & lending
- Investments / trading-related systems
- Customer onboarding & identity/access
- Transaction processing & financial reporting
- Fraud-related controls
- Privacy & data protection
- Application security
- Infrastructure & API security
- Database controls & segregation of duties
- Change management
- Monitoring & observability
- Business continuity / disaster recovery
- Model & AI governance
- Human approval controls / auditability

**Subdomains, controls, and evidence types:** deferred to Phase 2 content work (populating `knowledge_base/controls/`) — this planning phase defines the *shape* (§11 `Control`, `Evidence` schemas) but not the content, per the instruction not to invent regulatory claims. Control content authoring is a distinct workstream requiring domain-expert (not purely engineering) input — flagged as an open question in §16.

**Risk categories:** `critical`, `high`, `medium`, `low`, `info` — reused directly from `ai-project-control-tower/app/audit/models.py::Severity`, which is already a clean, minimal enum.

**Report sections (per assessment):** Executive summary, per-domain score table, findings by severity, findings by domain, evidence appendix, insufficient-evidence appendix (new — domains/controls that could not be evaluated), human review log, disclaimers (see §10 — no legal/regulatory compliance claims).

**Explicit separation required (per the source brief) between:**
- **Technical controls** — verifiable in code/config (e.g., "database connections use TLS").
- **Internal policies** — organization-specific documents supplied as ingested artifacts, not hardcoded.
- **Architecture standards** — the "Blueprint" concept already present in `ai-project-control-tower/app/db/models/blueprint.py`, reusable as-is.
- **Business rules** — out of scope for automated verification; surfaced only if explicitly documented in ingested artifacts.
- **Regulatory requirements** — the platform must never claim regulatory compliance from automated checks alone; every regulatory-adjacent control must carry a disclaimer field, and the UI/report templates must render it prominently. This is a hard product requirement, not a nice-to-have — reflected in the `Control` and `Report` schemas in §11.

---

## 10. Security, Privacy, and Governance

**Read-only enforcement:** `scanners/repo_scanner.py` (reused as-is) plus the extended platform-wide non-modification test suite (§12). No component other than `storage/` (the platform's own database) and `reporting/` (writing report files to the platform's own output directory) is permitted to open any file in write mode.

**Access control:** **Gap.** None of the three source repositories implement authentication or role-based access control (`ai-project-control-tower`'s own `known_limitations.md` states this explicitly, and no auth code exists in any of the three repos). This must be designed net-new before any multi-user or non-local deployment (§16).

**Secrets handling:** No hardcoded live secrets were found anywhere in the three repositories (verified via targeted regex search across all `.py` files for common API-key formats — the only match was an intentional test fixture in `ai-project-control-tower/tests/unit/test_secret_masker.py:78`). One anti-pattern was found and should be corrected: `ai-project-control-tower/app/core/config.py:89-91` ships a default `DATABASE_URL` containing a placeholder credential string (`control_tower_pass`); the new platform's config should require an explicit database credential with no embedded default, even a placeholder one, given the banking context.

**Audit trail:** `ai-project-control-tower` provides structured JSON logging (`structlog`, referenced throughout `app/core/logging.py` usage) and `created_at` timestamps on all DB rows, but there is **no append-only audit-of-audits** — no record of who reviewed/overrode a finding, no history of score changes. This is entirely new work (`governance/audit_trail.py`, `models/audit_event.py`, §11).

**Data classification:** **Gap.** No document/finding sensitivity classification exists in any of the three repositories. New `knowledge_base` and `evidence` schemas must include a classification field from the outset (§11).

**External-provider restrictions:** Enforced by the disabled-by-default `providers/` boundary design in §7; no existing code needs to be "restricted" because no existing code calls external LLM providers today (confirmed by repo-wide grep — the only real external calls in any of the three repos today are the *optional, opt-in* `openai`/`gemini` **embedding** calls in `RAG-Engineering-Lab`, which are already gated correctly).

**Human approval:** **Gap**, addressed net-new in `governance/approval_workflow.py` — no existing code has any concept of a reviewer approving or rejecting a finding.

**Logging:** `structlog` (control-tower) is the stronger of the two logging approaches found (structured JSON vs. RAG-Lab's simpler stdlib logging via `src/core/logging_config.py`, not read in full detail); adopt `structlog` platform-wide.

**Retention:** **Gap** — no retention policy or data-lifecycle management exists in any of the three repositories; must be defined net-new, particularly for locally-stored banking-sensitive ingested documents (§16 open question — retention periods are a policy decision, not an engineering one).

**Isolation requirements:** Enforced by the module-boundary rules in §5.4 and §6; needs a dedicated `tests/isolation/` suite (§12) verifying by static/import analysis that no module outside `providers/` imports a network client.

**Consolidated security findings from this audit (all file:line references verified by direct code read in this session):**

| # | Finding | Location | Severity (engineering judgment, not yet scored by the platform being designed) | Proposed remediation |
|---|---|---|---|---|
| 1 | `docs/testing_strategy.md` describes tests/smoke-test files that do not exist; `tests/{unit,integration,e2e}/` contain zero test functions | `RAG-Engineering-Lab/docs/testing_strategy.md`; `RAG-Engineering-Lab/tests/**` | High (trust/process risk, not a runtime vulnerability) | Author the missing tests before this code is trusted with banking-sensitive documents (§12, §13 Phase 2) |
| 2 | Prompt-injection scanning is advisory-only and never blocks a query | `RAG-Engineering-Lab/src/security/prompt_safety.py:37-53` | Medium | Make the gate configurable to hard-block in the new `governance/prompt_safety.py`; keep advisory mode as an option |
| 3 | PII redaction is regex-based and explicitly non-exhaustive (own docs acknowledge this) | `RAG-Engineering-Lab/src/security/pii_redaction.py`; `docs/known_limitations.md` | Medium | Extend pattern set; document residual risk clearly in the platform's own limitations doc rather than repeating the gap silently |
| 4 | Default `DATABASE_URL` embeds a placeholder credential | `ai-project-control-tower/app/core/config.py:89-91` | Low (placeholder, not a live secret, but a bad default pattern) | Require an explicit credential with no default value |
| 5 | Deterministic "agents" retrieve free-text context and pattern-match it with zero prompt-injection defenses; harmless today (no LLM call), but the same code path is the one the project's own docs anticipate wiring to a real LLM provider | `ai-project-control-tower/app/agents/security_agent.py:52-65` | Low today / Medium if left unaddressed when LLM providers are enabled | Route any future LLM-backed evaluator through `governance/prompt_safety.py` before this becomes a real attack surface |
| 6 | `CLAUDE.md`/`README.md` reference a `Doces/` directory not present in the repository | `ai-project-control-tower/CLAUDE.md:5`, `README.md:391` | Informational | Confirm with the repository owner whether this content exists elsewhere or the reference should be removed (§16) |
| 7 | `AI-System-Templates-Library/`, `Project-Blueprint-System/` are empty but referenced as pipeline stages in another repo's UI | both under `ai-project-control-tower/` | Informational | Remove references or populate; no security impact, a documentation-accuracy issue |
| 8 | No authentication/authorization anywhere across all three repositories | Whole codebase (self-reported in `ai-project-control-tower/docs/04-quality-security/known_limitations.md`) | High, if deployed beyond a single trusted local user | Design net-new (§16 open question — scope depends on deployment model) |

No path traversal, command execution, unsafe deserialization, or unrestricted-upload vulnerabilities were found in the code paths read during this audit (file validation, path resolution, and upload handling were specifically checked in both `RAG-Engineering-Lab/src/security/file_validation.py` and `ai-project-control-tower/app/scanner/path_validator.py` and found sound). This is not a claim that no such issues exist anywhere in either codebase — only the modules listed as read in §2 were reviewed at this depth; `app/api/routes/*`, `ui/pages/*`, and Alembic migration internals were inventoried but not reviewed line-by-line in this pass.

---

## 11. Data Models

**Phase mapping (this revision):** `models/enums.py` (`Severity`, `ConfidenceLevel`,
`EvidenceCompleteness`, `HumanReviewStatus`, `DecisionCategory`, `ControlType`) is
**implemented in Phase 1** — see `models/README.md`. Every other model below is **planned for
Phase 3** ("Assessment, Evidence, and Scoring"); none of them exist as importable modules yet.
`models/README.md` carries the same adapted-vs-net-new table as this section so the two do not
drift — treat this section as the field-level spec and `models/README.md` as the
implementation-status tracker.

Schemas below are proposed field lists (Pydantic/SQLAlchemy), building on the closest existing analog where one exists.

**Assessment target** (new, generalizes "project" + "scan target"):
`id, name, target_type (repo|export_bundle), path_or_uri, allowed (bool), classification, created_at`

**Control** (new — no existing analog in any of the three repos):
`id, domain, subdomain, control_id, title, description, control_type (technical|policy|architecture_standard|business_rule|regulatory_reference), source_reference, weight, applies_to_domains[]`

**Policy** (new): `id, name, content, source_document_id, version, effective_date`

**Evidence** (new, though seeded conceptually by `Finding.evidence` in `ai-project-control-tower/app/audit/models.py:23`):
`id, finding_id, evidence_type (file_excerpt|config_value|scan_result|retrieved_chunk), content, source_reference (file_path + line_number, reusing `Finding.file_path`/`line_number`), retrieved_via (chunk_id), captured_at`

**Finding** (adapted from `ai-project-control-tower/app/db/models/finding.py:7-23` and `app/audit/models.py:18-27`, extended per the source brief's required field list):
`id, assessment_id, control_id, agent_name→evaluator_name, category, severity, confidence (NEW), title, description, evidence_id, source_reference, business_impact (NEW), technical_impact (NEW), recommendation, human_review_status (NEW: pending|approved|rejected|overridden), reviewed_by, reviewed_at, created_at`

**Recommendation** (new, currently inline text on `Finding.recommendation`; promoted to its own entity to support prioritization/status independent of the finding):
`id, finding_id, text, priority, status (open|accepted|deferred|rejected)`

**Score** (adapted from `ai-project-control-tower/app/audit/models.py::AuditScores`, extended):
`id, assessment_id, domain, raw_score, weighted_score, confidence_level (NEW), evidence_completeness (NEW: complete|partial|insufficient), decision_category (acceptable|acceptable_with_observations|remediation_required|high_risk|critical_risk|insufficient_evidence|manual_review_required), calculated_at, override_of (NEW, self-referential FK for human overrides)`

**Report** (adapted from `ai-project-control-tower/app/db/models/report.py:9-19`): `id, assessment_id, format, content, sanitized (bool), generated_at, disclaimers (NEW — explicit non-compliance-claim text)`

**Provider request** (new, per §7): `id, provider_name, purpose, sanitized_context_hash, token_count, byte_count, latency_ms, status, approved_by, requested_at`

**Audit event** (new, per §10): `id, event_type (finding_reviewed|score_overridden|provider_request|ingestion_approved|...), actor, target_id, target_type, before_value, after_value, occurred_at`

---

## 12. Testing Strategy

| Test type | Approach | Reused from | Status |
|---|---|---|---|
| Unit tests | Per-module, e.g. chunkers, scoring math, secret masker patterns | `AI-Project-Scope-Guard/tests/test_evaluator.py` (style reference, verified passing 14/14) + `ai-project-control-tower/tests/test_scoring.py`, `test_report_sanitizer.py` (read, well-structured, not executed — missing deps) | Adapt; must be re-run once dependencies are installed in a real dev environment |
| Integration tests | Multi-component (chunk→embed→store→retrieve) | `ai-project-control-tower/tests/integration/test_integration.py` (exists; requires a live DB per its own README instructions) | Adapt; needs a local-DB-free equivalent for the new file-based RAG default |
| Scanner tests | Read-only guarantee | `ai-project-control-tower/tests/unit/test_scanner.py`, `test_path_validator.py` | Reuse as-is |
| RAG retrieval tests | Recall/precision/MRR/nDCG correctness | `RAG-Engineering-Lab/src/evaluation/*` (implementation exists and was read; **no tests currently exercise it** — must be authored) | Rewrite from scratch |
| Scoring tests | Weight/threshold/aggregation correctness | `ai-project-control-tower/tests/test_scoring.py` (read in full; not executed in this session due to missing `structlog` dependency) + new confidence/evidence-completeness cases | Adapt + extend |
| Provider-adapter tests | Fail-closed when unconfigured, never logs keys, respects disabled flag | New — pattern to follow is `RAG-Engineering-Lab/src/embeddings/{openai,gemini}_provider.py`'s existing fail-fast-at-construction test surface (not itself covered by any existing automated test, since `RAG-Engineering-Lab/tests/` is empty) | Author net-new |
| Isolation tests | No module outside `providers/` makes network calls | New | Author net-new (e.g., static import-graph check) |
| Security tests | Secret masking, path traversal, upload validation | `ai-project-control-tower/tests/test_security.py`, `tests/unit/test_secret_masker.py` (read; not executed — missing deps) | Adapt |
| Read-only enforcement tests | Byte-for-byte hash comparison before/after any assessment run | `ai-project-control-tower/tests/e2e/test_no_repo_modification.py` (read in full — a strong, genuinely verifiable pattern) | Reuse as-is for the scanner; **extend to cover the full assessment pipeline**, not just `RepoScanner` |
| Report-validation tests | Sanitization correctness (no leaked secrets, no auto-fix content) | `ai-project-control-tower/tests/test_report_sanitizer.py`, `test_report_generator.py` (read; not executed — missing deps) | Adapt |

**Honesty note on execution in the original audit session:** Of all tests across the three repositories, only `AI-Project-Scope-Guard/tests/test_evaluator.py` was actually executed (`14 passed in 0.02s` — pure-Python, zero extra dependencies). `RAG-Engineering-Lab/tests/` was executed and confirmed empty (`no tests ran`). `ai-project-control-tower`'s test suite could not be executed in that session because its dependencies (`structlog`, `fastapi`, `sqlalchemy`, etc.) were not installed, and per the audit's constraints, no dependencies were installed to force a run. **Corrected in this revision:** `ai-project-control-tower`'s suite was previously validated in its own original development environment at **59 tests passing**, per the project owner's own historical record (see "Plan revision notice" and `CLAUDE.md`'s Wave 5 status) — this is a distinct claim from "unknown," but it was still not independently re-verified in the audit session or in Phase 1 (see below).

**Honesty note on execution in the Phase 1 implementation session:** `pydantic-settings`, `sqlalchemy`, `alembic`, `chromadb`, `structlog`, and `psycopg2-binary` were installed in this session (all approved core platform components per "Plan revision notice" #2–#3, not incidental additions) to actually build and test Phase 1. **97 new tests were written and executed, all passing** — unit, integration (real, local Chroma add/search/delete round-trips), isolation (static import-graph checks, SDK-not-required checks), security (secret masking, report sanitization, PII redaction, prompt safety, file validation, `.env.example` hygiene), and e2e (hash-comparison proof that the three legacy repositories were not modified). Full results, file-by-file, are in `PHASE_1_COMPLETION_REPORT.md`. `ai-project-control-tower`'s own legacy 59-test suite was still **not** re-executed in this session — installing its dependencies made Phase 1's own new tests runnable, not the legacy suite, which was out of scope for Phase 1 (its underlying modules are not ported until later phases). No PostgreSQL/pgvector server was available in this environment, so `rag/vectorstores/pgvector_store.py` was verified for construction and graceful-failure behavior only, not full add/search correctness against a live database — see `docs/vector_backend_decision.md`.

---

## 13. Migration and Integration Phases

**Renumbered and re-scoped in this revision** (see "Plan revision notice"). The previous
Phase 0–7 plan is replaced by an approved Phase 1–6 plan; there is no separate "Phase 0" —
scaffolding and the RAG-backend decision are both folded into Phase 1, since the RAG-backend
decision is no longer open (§ "Plan revision notice" #2–#3). Each phase below ends with an
explicit **approval checkpoint** — this document does not authorize proceeding past Phase 1
without separate, explicit sign-off.

**Phase 1 — Unified Foundation — IMPLEMENTED, see `PHASE_1_COMPLETION_REPORT.md`**
- *Objective:* Stand up the new repository skeleton, merged configuration, both approved
  vector-store backends' foundations, shared contracts, and governance primitives — with no
  assessment/scoring logic yet.
- *Included:* Repository structure (§5.2); `core/{config,contracts,exceptions,logging,domains}.py`; `rag/vectorstores/{chroma_store,pgvector_store,registry}.py`; `rag/embeddings/mock_embedding_provider.py`; `governance/{secret_masker,report_sanitizer,pii_redaction,prompt_safety,file_validation}.py`; `scanners/path_validator.py`; `providers/{base,registry,openai_adapter,gemini_adapter,claude_adapter}.py`; `storage/db/{base,session}.py` + Alembic wiring; `models/enums.py`; `mock_banking_system/` scaffold + `scripts/seed_mock_banking_demo.py` placeholder; `deployment/docker-compose.yml` (database service only).
- *Files/modules affected:* New repo code only; the three existing repos are read from (for porting/adaptation) but never written to — verified by `tests/e2e/test_original_repos_not_modified.py`.
- *Prerequisites:* Stakeholder approval of this revised plan.
- *Expected output:* A working foundation: `pip install -r requirements.txt && pytest` runs entirely offline; `core.config.Settings()` constructs with no environment variables set and defaults to local-only/providers-disabled/pgvector-primary.
- *Tests:* 97 tests across `tests/{unit,integration,isolation,security,e2e}/`, all passing — see `PHASE_1_COMPLETION_REPORT.md` for the full breakdown.
- *Risks:* Realized and accepted, not hypothetical: `rag/vectorstores/pgvector_store.py` is untested against a live database (no PostgreSQL/pgvector server available in this environment) — see `docs/vector_backend_decision.md`.
- *Completion criteria / approval checkpoint:* Met — all Phase 1 tests pass; no original repository modified; no real credentials added; no external provider enabled; platform defaults to pgvector with Chroma selectable; all 16 domains represented; mock-system scaffolding and seed-script interface exist. **Awaiting explicit approval to begin Phase 2.**

**Phase 2 — Banking Source Ingestion and Read-Only Scanning Engine — IMPLEMENTED, see `PHASE_2_COMPLETION_REPORT.md`**

*Status correction (factual, not a plan revision):* what was actually commissioned and built
as "Phase 2" differs from this row's original description below in one respect: it did **not**
build the local-RAG document lifecycle (`rag/{ingestion,chunking,retrieval,pipeline}`, for
ingesting policy/control *documents* into the vector store) — that remains unbuilt and is
carried forward to a future phase, unchanged in scope. Instead, Phase 2 built a full read-only
*source-scanning* engine: safe local-directory/ZIP ingestion, file discovery with safety
limits, a safe content reader, deterministic file/technology classification, mapping to the 16
approved banking domains, eight deterministic content scanners, a structured finding model, a
scan orchestrator with per-file error isolation and before/after integrity verification,
PostgreSQL persistence (5 new tables, migrated and verified against a live pgvector-enabled
Postgres instance — closing Phase 1's stated pgvector gap in the process), a minimal Streamlit
workflow, and JSON/Markdown/CSV report export. See `docs/phase2_scanning_guide.md` for the full
capability inventory.

- *Objective (as built):* Prove the read-only scanning architecture end-to-end with real,
  useful findings across 8 categories, mapped to the banking domain model, persisted to
  PostgreSQL, and viewable/exportable through a minimal UI — without any assessment/control-
  library/scoring logic yet (that remains Phase 3+).
- *Included:* `scanners/{source_ingestion,file_discovery,content_reader,file_classifier,
  domain_mapper,scan_orchestrator}.py`, `scanners/rules/*` (8 scanners), `storage/db/models/
  {scan,file_inventory,domain_mapping,finding,scanner_execution}.py` +
  `alembic/versions/0001_phase2_scan_findings_tables.py`, `storage/db/repositories.py`,
  `reporting/scan_report_exporter.py`, `ui/streamlit_app.py`.
- *Files/modules affected:* New Phase 2 code only; the three legacy repositories and all
  Phase 1 code remain as they were (Phase 1's `rag/vectorstores/pgvector_store.py` gained live
  verification, not a rewrite — see below).
- *Prerequisites:* Phase 1 approval checkpoint passed.
- *Expected output:* A working local scan (`ingest → discover → classify → map domains → scan
  → persist → verify integrity → export`) producible against any local directory or ZIP
  archive, and viewable through `ui/streamlit_app.py`.
- *Tests:* 155 new tests (252 total collected, up from Phase 1's 97; 5 of the 155 require a
  live PostgreSQL server and are skipped, not failed, when one isn't available — see
  `PHASE_2_COMPLETION_REPORT.md` for the exact breakdown and how they were actually run in
  this session).
- *Risks:* Realized and resolved, not hypothetical: two ordering-dependent foreign-key bugs in
  `storage/db/repositories.py` (writing dependent rows before the parent row's ORM-side UUID
  default had been flushed) were invisible against Phase 1-style SQLite-only testing and were
  only caught by testing against the live PostgreSQL instance — see
  `PHASE_2_COMPLETION_REPORT.md` §"known limitations" for why this matters for Phase 3.
- *Completion criteria:* Met — see `PHASE_2_COMPLETION_REPORT.md`'s verdict section.
  **Awaiting explicit approval to begin Phase 3.**

**Phase 3 — Assessment, Evidence, and Scoring**
- *Objective:* Stand up persistence, evidence capture, and the new scoring engine with confidence/evidence-completeness support.
- *Included:* `models/{control,evidence,finding,recommendation,score}.py`, `storage/db/*` domain tables + first real Alembic migration, `controls/*`, `evidence/*`, `scoring/engine.py`.
- *Files/modules affected:* Adapted from `ai-project-control-tower/app/{db,audit}/*`; scoring mechanism pattern from `AI-Project-Scope-Guard/src/scope_guard/evaluator.py`; enums from Phase 1's `models/enums.py`.
- *Prerequisites:* Phase 2 approval checkpoint passed.
- *Expected output:* A scoring engine that can take a list of findings (including zero findings for an unevaluated domain) and correctly emit `DecisionCategory.INSUFFICIENT_EVIDENCE` rather than a false "clean" score — the core fix identified in the Executive Summary and §9.
- *Tests:* Scoring unit tests per §12, specifically including the "no findings because unevaluated" vs. "no findings because clean" boundary case.
- *Risks:* Medium — getting the confidence/evidence-completeness semantics right is a design risk, not just an implementation risk.
- *Completion criteria:* Scoring engine unit tests pass, including the insufficient-evidence case; Alembic migration applies cleanly to a fresh local database.

**Phase 4 — Complete Banking Domain and Governance Layer**
- *Objective:* Wire scanning + RAG + scoring together into a working end-to-end assessment covering all 16 domains (§9), and add the human-approval/audit-trail governance layer.
- *Included:* `assessment/engine.py`, `assessment/evaluators/*` (generalized from `ai-project-control-tower/app/agents/*`), `knowledge_base/controls/` structure across all 16 `BankingDomain` values, `governance/approval_workflow.py`, `governance/audit_trail.py`, `models/audit_event.py`, retention foundations, report disclaimers.
- *Files/modules affected:* Refactor of `ai-project-control-tower/app/audit/audit_engine.py`, `base_agent.py`, `orchestrator_agent.py`, and the six concrete agent files.
- *Prerequisites:* Phase 3 approval checkpoint passed.
- *Expected output:* A working, human-reviewable end-to-end assessment run producing findings with confidence and evidence across all 16 domains; findings default to `pending` review status; every review action is logged.
- *Tests:* Extend `tests/e2e/test_original_repos_not_modified.py`-style hash-comparison coverage to the full pipeline; assessment-engine integration tests; audit-trail completeness tests.
- *Risks:* Medium-High — this is the largest single integration point in the whole migration; actual control-library content authoring requires domain expertise beyond engineering scope (§16, open question #4).
- *Completion criteria:* A full assessment run completes end-to-end with zero writes to the target and produces at least one finding per represented domain; a finding can be reviewed/overridden and the change appears in the audit trail.

**Phase 5 — UI, Mock System, and Demonstration Workflow**
- *Objective:* Build the banking-domain Streamlit UI, and populate the mock banking system scaffolded in Phase 1.
- *Included:* `ui/pages/*`, `ui/components/*`, `ui/services/api_client.py`; full `mock_banking_system/` content (synthetic controls/policies/evidence across all 16 domains, a controlled mix of compliant/weak/missing/ambiguous/insufficient-evidence cases); `scripts/seed_mock_banking_demo.py` fully implemented (idempotent, deterministic, no real secrets, tested); a demo assessment run; sample technical and executive reports; a Docker-based demonstration workflow.
- *Prerequisites:* Phase 4 approval checkpoint passed (UI and demo data both depend on a working assessment pipeline).
- *Expected output:* A reviewer can complete the full §8 flow through the UI, and a stakeholder demo can run entirely against synthetic data with zero real banking information involved.
- *Tests:* Manual UI walkthrough; smoke test that the app starts without API keys; seed-script idempotency tests (running it twice produces no duplicate/inconsistent state).
- *Risks:* Low — mostly presentation and content work by this point.
- *Completion criteria:* `docker compose up` produces a working demo environment; the seed script is safely re-runnable; a reviewer can complete the full flow through the UI without touching the API directly.

**Phase 6 — Optional External Providers**
- *Objective:* Implement real `providers/*` calls per §7, disabled by default.
- *Included:* Real `send()` implementations for `providers/{openai,gemini,claude}_adapter.py` (Phase 1 scaffolded the classes and fail-closed behavior but left `send()` raising `NotImplementedError`), provider-request logging (`models/provider_request.py`), approval gates wired to `governance/approval_workflow.py` (Phase 4).
- *Prerequisites:* Phase 4 approval checkpoint passed (approval workflow must exist before any provider call can be gated by it).
- *Expected output:* External-provider enrichment available only when explicitly enabled and approved, with full logging.
- *Tests:* Provider-adapter tests extended with real (mocked-at-the-SDK-boundary) call tests; isolation tests confirming the platform still functions correctly with providers disabled (the default state, already verified in Phase 1).
- *Risks:* Low functional risk (additive, off by default) but high scrutiny warranted given the sensitivity of the data involved.
- *Completion criteria:* With `EXTERNAL_PROVIDERS_ENABLED=false` (default), zero outbound network calls occur anywhere in the platform during a full assessment run — verified by an isolation test (already true and tested as of Phase 1; must remain true).

---

## 14. Effort and Complexity Estimate

No calendar commitment is given, per instruction. Complexity is qualitative; module/integration/test counts are rough order-of-magnitude estimates. Phase 1's row is no longer an estimate — it reflects what was actually built (see `PHASE_1_COMPLETION_REPORT.md`).

| Phase | Complexity | Modules | Integration points | Tests | Major dependencies | Major unknowns |
|---|---|---|---|---|---|---|
| 1 — Unified Foundation | Low-Medium (**actual, not estimated**) | 37 new files across `core/`, `governance/`, `scanners/`, `rag/`, `providers/`, `storage/db/`, `models/`, `app/` | 8 (config↔vectorstore-registry↔provider-registry↔session↔alembic↔health-endpoint) | **97, actual, all passing** | pydantic-settings, sqlalchemy, alembic, chromadb, structlog, psycopg2-binary | None significant remaining for Phase 1's own scope |
| 2 — Scanner + local RAG core | Medium | ~20 (mirrors `RAG-Engineering-Lab/src` file count) | ~6 (ingestion↔chunking↔embedding↔store↔retrieval↔pipeline) | ~40-60 (must be authored from zero, since the source repo's suite is empty) | sentence-transformers | Live-pgvector verification of `PgVectorStore` (Phase 1's stated gap) |
| 3 — Assessment, Evidence, Scoring | Medium | ~15 (mirrors `ai-project-control-tower/app/{db,audit}` file count) | ~4 | ~25-30 | — (SQLAlchemy/Alembic already in place) | Exact confidence/evidence-completeness algorithm design |
| 4 — Complete Banking Domain and Governance Layer | High | ~15 (6+ evaluators + engine + control library scaffolding + governance workflow) | ~8 (scan↔RAG↔evaluators↔evidence↔scoring↔governance) | ~40-50 incl. extended E2E + audit-trail tests | — | Banking control content authoring is a domain-expertise task, not purely engineering (§16) |
| 5 — UI, Mock System, Demonstration Workflow | Medium | ~12 UI + mock-system content | ~2 (UI→API, seed-script→models) | Manual UI walkthroughs + seed-script idempotency tests | streamlit, jinja2 | Full page-by-page content design; volume of synthetic data needed for a convincing demo |
| 6 — Optional External Providers | Low-Medium (additive, off by default) | 3 adapters get real `send()` bodies (classes already exist from Phase 1) | ~3 | ~15-20 | openai, google-generativeai, anthropic SDKs (optional) | Per-provider rate/cost-control policy |

**What could increase effort:** banking control-library content requiring significant compliance/domain-expert time not captured in the estimates above (Phase 4); discovering during Phase 2 that `RAG-Engineering-Lab`'s untested chunking/ingestion code has latent bugs once real tests are written; discovering SQL issues in `PgVectorStore` once tested against a live database for the first time.

**What could reduce effort:** launching Phase 4 with 3-5 pilot controls per domain instead of a comprehensive set; reusing `ai-project-control-tower`'s existing Streamlit page structure more literally in Phase 5 rather than a full rewrite.

---

## 15. Removal and Cleanup Plan

**No removal/deletion has been performed in any of the three original repositories through Phase 1** — verified by `tests/e2e/test_original_repos_not_modified.py`. The table below is a forward plan; the "When" column is updated to the revised Phase 1–6 numbering (see "Plan revision notice"):

| Item | Action | When |
|---|---|---|
| `RAG-Engineering-Lab/static-site/`, `ai-project-control-tower/static-demo/`, `AI-Project-Scope-Guard/static-site/` | Remove (personal portfolio branding, not product code) | Phase 1 cleanup pass (not yet done — still present) |
| `ai-project-control-tower/AI-System-Templates-Library/`, `Project-Blueprint-System/` | Remove (empty placeholders) | Phase 1 cleanup pass (not yet done — still present) |
| `RAG-Engineering-Lab/src/retrieval/hybrid_retriever.py` | Remove (dead stub) | Phase 2, once the real hybrid implementation is ported |
| `AI-Project-Scope-Guard/src/scope_guard/evaluator.py`'s `_decide`/`_label`/`_next_steps` idea-decision logic | Remove (out-of-scope decision semantics); retain only the weighting/aggregation *pattern* as design reference | Phase 3 |
| All three repos' `notebooks/` | Move to documentation/archive (retain as historical reference, not runtime code) | Phase 1 cleanup pass (not yet done — still present) |
| `RAG-Engineering-Lab/docs/testing_strategy.md` | Rewrite to describe only tests that actually exist, once Phase 2 tests are authored | Phase 2 |
| `ai-project-control-tower/CLAUDE.md` reference to `Doces/` | Resolve with stakeholder first (§16); either restore the content or remove the reference | Phase 1 (not yet resolved — still an open question) |
| Three separate `requirements.txt` files | Merge into one reconciled dependency set | **Done in Phase 1** — see root `requirements.txt` |
| Three separate `docker-compose.yml` files | Merge into one deployment manifest (`deployment/docker-compose.yml`) | Partially done in Phase 1 (database service only — see `deployment/docker-compose.yml`); `api`/`ui` services added once those modules have real content (Phase 5/6) |
| The three original repositories themselves (`RAG-Engineering-Lab/`, `ai-project-control-tower/`, `AI-Project-Scope-Guard/` as top-level directories in this monorepo) | Retain temporarily as read-only reference during Phases 1-4 (do not delete until the corresponding functionality has been ported and tested in the new structure); archive (not delete) once superseded | After Phase 4 completion, pending explicit approval |

---

## 16. Risks and Open Questions

**Architectural risks:**
- ~~The RAG-backend decision~~ — **resolved in this revision**: pgvector primary, Chroma secondary, no FAISS (see "Plan revision notice" and `docs/vector_backend_decision.md`). The residual risk is narrower now: `rag/vectorstores/pgvector_store.py` has not been verified against a live database (Phase 1 limitation, see §12), so Phase 2 may still surface SQL issues.
- `ai-project-control-tower`'s "agents" being deterministic rule-based checks rather than LLM-backed analysis means the current control-evaluation logic is shallow (presence/absence and keyword checks); scaling this to genuinely useful banking-control evaluation may require either much more sophisticated deterministic rules or a deliberate, well-governed introduction of LLM-assisted evaluation behind the Phase 6 provider layer — a scope decision, not just an engineering one.

**Security risks:**
- Items 1-8 in the §10 findings table, most notably the untested `RAG-Engineering-Lab` codebase and the complete absence of authentication across all three source repositories (still true after Phase 1 — no auth was in scope).

**Domain-knowledge gaps:**
- No banking control library content exists in any of the three repositories today; this document defines the *schema* for controls (§11) but authoring the actual control library requires banking/compliance domain expertise beyond this audit's engineering scope.
- The source brief is explicit that the platform must never claim legal/regulatory compliance from automated checks; the exact disclaimer language and where it must appear is a legal/compliance stakeholder decision, not an engineering one.

**Dependency risks:**
- `pydantic-settings`, `sqlalchemy`, `alembic`, `chromadb`, `structlog`, and `psycopg2-binary` are now installed and pinned in the unified `requirements.txt` (done in Phase 1 — see "Plan revision notice" #2–#3: these are approved core components, not incidental additions). `faiss-cpu` is deliberately **not** included.
- No PostgreSQL/pgvector server is available in this planning/implementation environment, so `PgVectorStore` remains untested end-to-end (see §12, `docs/vector_backend_decision.md`). This must be resolved early in Phase 2.

**Performance risks:**
- `ai-project-control-tower`'s scanner skips files over 1 MB and treats binary content as opaque (self-reported limitation); large banking-system repositories (which may include large generated artifacts, data fixtures, or binaries) may see materially reduced coverage unless this limit is reconsidered per-deployment.
- Synchronous, one-audit-at-a-time execution (self-reported limitation of `ai-project-control-tower`) will not scale to multiple concurrent assessments without additional work (e.g., a task queue) — out of scope for the MVP per this plan, but worth flagging early.

**Legal or regulatory interpretation risks:**
- Explicitly out of scope for this audit to resolve; flagged for stakeholder/legal input per the source brief's own instruction not to invent compliance claims.

**Unknowns requiring stakeholder input:**
1. ~~Which RAG backend...~~ — **Resolved** (see "Plan revision notice" #2–#3).
2. What is the intended deployment model — single trusted local user (as all three source repos assume today) or multi-user/shared? This determines whether authentication/RBAC is in-scope for the MVP or a later wave. **Still open.**
3. What happened to the `Doces/` directory referenced in `ai-project-control-tower/CLAUDE.md`? Does it contain content that should inform this plan, or should the reference simply be removed? **Still open.**
4. Who owns authoring the banking control library content (§9)? This audit can define the schema but not the regulatory/domain content. **Still open — blocks Phase 4.**
5. What data retention policy applies to locally-ingested banking-sensitive documents? **Still open.**
6. Is any external LLM provider integration (Phase 6) actually required for an initial release, or is a fully local-only MVP (Phases 1-5) sufficient to ship first? **Still open.**
7. ~~Who/what provides a PostgreSQL + pgvector server...~~ — **Resolved during Phase 2:**
   Docker was available in the implementation environment; `deployment/docker-compose.yml`'s
   `db` service was started locally with a non-default, non-committed test credential, the
   Phase 2 Alembic migration was generated by autogenerate against it and applied with
   `alembic upgrade head`, and `tests/integration/test_postgres_persistence.py` (5 tests,
   including a real `rag/vectorstores/pgvector_store.py` add/search round-trip) passed against
   it. This closes the gap Phase 1 flagged. It does not resolve the separate, still-open
   question of what provisions this for a *shared* (non-local-dev) environment — that remains
   part of open question #2 (deployment model).

---

## 17. Definition of Done

**Planning phase (this document):** Done — reviewed and approved in principle, with the corrections in "Plan revision notice" applied. Open questions #2–#7 in §16 remain unresolved and do not block Phase 1 (they were not on Phase 1's critical path), but #7 blocks Phase 2's completion criteria and #4 blocks Phase 4's.

**Phase 1 ("Unified Foundation"):** Done — see `PHASE_1_COMPLETION_REPORT.md`.

**Integration phase (Phases 2-5, §13):** Complete when each phase's approval checkpoint has passed, and the platform-wide non-modification E2E test (extended from `ai-project-control-tower`'s existing pattern, already implemented for the current codebase in `tests/e2e/test_original_repos_not_modified.py`) passes against the full assessment pipeline, not just the scanner.

**Functional MVP:** A single local user can select a target repository, run a full assessment against at least one pilot banking control domain, receive findings with evidence/confidence/severity, have those findings scored with correct insufficient-evidence handling, review and approve/override them, and export a sanitized report — entirely without any external network call, verified by an isolation test (the isolation-test pattern itself is already implemented and passing as of Phase 1 — see `tests/isolation/`).

**Local-only deployment:** The platform runs via `docker compose up` (or equivalent) with zero required external API keys and `EXTERNAL_PROVIDERS_ENABLED=false` — already true and tested as of Phase 1 (`tests/unit/test_config_defaults.py`, `tests/unit/test_app_health.py`).

**Optional external-provider layer:** Complete when all of §7's controls (disabled-by-default, approval-gated, sanitized, logged, fallback-safe) are implemented and covered by isolation tests proving the platform's local-only behavior is unaffected when the layer remains disabled. The disabled-by-default/kill-switch/fail-closed-construction parts are already implemented and tested as of Phase 1; only real outbound `send()` calls (Phase 6) and provider-request logging remain.

---

## 18. Recommended Next Step

**Phase 1 is complete** — see `PHASE_1_COMPLETION_REPORT.md` for the full record. The
recommended next step is: obtain a real PostgreSQL + pgvector instance (local Docker Compose
is sufficient) for this development environment, then begin **Phase 2** exactly as scoped in
§13 — read-only repository scanning (`scanners/repo_scanner.py`, `scanners/file_classifier.py`)
and the local RAG document lifecycle (`rag/ingestion`, `rag/chunking`, `rag/retrieval`,
`rag/pipeline.py`), including the first live-database verification of
`rag/vectorstores/pgvector_store.py`. In parallel, resolve open question #2 (deployment/auth
model) with the stakeholder, since it affects how much of Phase 4's governance layer needs
authentication awareness designed in from the start rather than retrofitted. Do not begin
Phase 2 implementation work until this revised plan and the Phase 1 completion report have
been explicitly approved.

---

*This document was revised per stakeholder-approved corrections (see "Plan revision notice") and now reflects Phase 1 as implemented. No source files in `RAG-Engineering-Lab/`, `ai-project-control-tower/`, or `AI-Project-Scope-Guard/` were modified, moved, deleted, or merged in the course of producing this document or implementing Phase 1 — verified by `tests/e2e/test_original_repos_not_modified.py`.*
