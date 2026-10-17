# Architecture

A single Python application: a Streamlit UI on top of plain-Python service modules, backed by PostgreSQL. There is no separate API server, queue, or cache.

## Components

| Layer | Location | Responsibility |
| --- | --- | --- |
| UI | `ui/app.py`, `ui/shell.py`, `ui/views/`, `ui/components/` | Sign-in gate, role-filtered navigation, pages, shared widgets and charts. `ui/streamlit_app.py` is an alias that runs the same app. |
| Access control | `auth/` | Password hashing, sign-in, sessions, role permissions, user administration, and the secured service wrappers every page calls. |
| UI services | `ui/services/` | Streamlit-free functions the secured wrappers delegate to: assessments, AI Assistant, scan comparison. |
| Assessment pipeline | `assessment/engine.py` | Runs ingest → scan → persist → score → control evaluation → audit for one source. |
| Scanning | `scanners/` | Allow-list path validation, ZIP extraction with traversal and size limits, file discovery, domain mapping, and the rule scanners in `scanners/rules/`. |
| Scoring and controls | `scoring/`, `controls/catalog.py`, `assessment/evaluators/` | Per-domain weighted scores, decision categories, recommendations, and control evaluation against an 8-control catalog. |
| Governance | `governance/` | Review/override validation and the finalization policy, audit-event construction, secret masking, PII redaction, report sanitization, prompt-safety checks. |
| Reporting | `reporting/` | JSON, Markdown, and CSV exports of a scan or a full assessment. |
| Persistence | `storage/db/`, `alembic/` | SQLAlchemy models and repositories; Alembic migrations (head: `0004_auth_users`). |
| AI Assistant | `agents/`, `providers/` | Advisory explanations of stored results (see below). |

Not on the runtime path: `rag/` (Chroma and pgvector vector-store adapters, covered by tests but not used by the assessment workflow) and `app/main.py` (a FastAPI `/health` endpoint that is tested but not started by Docker).

## Data flow

1. A page calls a method on `auth/secured_services.py`. The `Authorizer` re-validates the session against the database (idle timeout, account active, session version) and checks the role's permission. A denial is audited and raised.
2. For a Full Assessment, `assessment.engine.run_assessment()` validates the path against `ALLOWED_SCAN_PATHS`, hashes the source, runs every scanner, hashes the source again, and stores the scan with its findings. Only masked evidence is stored; raw matches never reach the database.
3. Scores, recommendations, evidence records, and control evaluations are computed and stored. The pipeline records its steps as `system` audit events, and the secured wrapper adds an `assessment_requested` event naming the user.
4. Governance actions (Manager only) go through `GovernanceRepository`. A score override inserts a new score row that points to the one it replaces; nothing is updated in place except a finding's review status.
5. Reads (dashboard, findings, compare, exports) are SELECT-only.

Quick Scan runs the scanners in memory only; just its audit event is stored.

## Storage

PostgreSQL 16 using the `pgvector/pgvector:pg16` image, in the Docker volume `postgres_data`. Tables: `scans`, `file_inventory`, `domain_mappings`, `findings`, `scanner_executions`, `controls`, `evidence`, `recommendations`, `scores`, `control_evaluations`, `audit_events`, `users`.

- `audit_events` is append-only: the code has no update or delete path for it.
- `users` rows are never deleted, only deactivated, so audit history stays attributable.
- Migrations run automatically when the app container starts (`deployment/docker-entrypoint.sh`).

## Scan comparison

`ui/services/comparison_service.py` compares two completed scans of the same source path. A finding counts as unchanged when rule, file path, and whitespace-normalized masked evidence match; line numbers are ignored and duplicates are matched one-to-one. Domain changes use each domain's effective score (latest, overrides applied). Scans of different sources are rejected with an explanation.

## AI Assistant

Four actions: explain a finding, summarize a domain, answer a question about the evidence, and write an executive summary. Every action requires a click, is permission-checked, and writes an `agent_action` audit event under the signed-in user.

In the current code the assistant always runs in **local mode**: deterministic, sanitized restatements of stored data, with no network calls. The OpenAI, Gemini, and Claude adapters in `providers/` are placeholders whose `send()` raises `NotImplementedError`, so even a configured external provider falls back to local mode. Questions pass a prompt-safety check, and context is capped by `AGENT_MAX_CONTEXT_CHARS` and `AGENT_MAX_EVIDENCE_ITEMS`. The assistant cannot change findings, scores, or reviews.
