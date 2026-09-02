# Security Boundaries — Phase 1–6 Snapshot

Full security/privacy/governance analysis and the consolidated findings table live in
`BANKING_PLATFORM_INTEGRATION_PLAN.md` §10. This document tracks only what has actually been
implemented and its known limitations — it does not re-derive the audit.

## Read-only enforcement

`scanners/path_validator.py` fails closed (rejects everything) when `ALLOWED_SCAN_PATHS` is
unset — verified by `tests/unit/test_path_validator.py`. **Phase 2 closes the gap Phase 1
noted here:** `scanners/scan_orchestrator.py` now performs a full read-only scan and proves it
never wrote to the source, by hashing the entire source tree before and after every scan
(`scanners/file_discovery.py::compute_source_integrity_hash`) and refusing to report a scan as
successful if the hashes differ — verified by
`tests/security/test_scan_no_source_modification.py` and exercised on every scan via
`ScanSummary.integrity_verified`. No scanner ever opens a scanned file in write mode; only
`open(path, "rb")` (hashing) and text-mode reads are used (`scanners/content_reader.py`).

The three legacy repositories were verified byte-for-byte unmodified across both the Phase 1
and Phase 2 implementation sessions using a hash-comparison test
(`tests/e2e/test_original_repos_not_modified.py`), the same pattern as
`ai-project-control-tower/tests/e2e/test_no_repo_modification.py`.

## No code execution during scanning (Phase 2)

Every Phase 2 scanner (`scanners/rules/*.py`) is regex-based pattern matching against
already-decoded text — none of them import a code execution facility
(`eval`/`exec`/`pickle.load`/unsafe `yaml.load`) or a database driver, verified statically by
`tests/security/test_no_unsafe_deserialization.py` (AST-walks every `.py` file in the
platform's own code, not just a sample). `scanners/rules/sql_scanner.py` in particular detects
SQL injection/destructive-statement *patterns* — it never executes SQL; the same static test
verifies no `sqlite3`/`psycopg2`/`pymysql`/`pyodbc` import or `.execute()` call exists anywhere
under `scanners/rules/`. `tests/security/test_no_network_during_scan.py` monkeypatches
`socket.socket` to raise during a full scan run, proving no network call occurs.

## Archive ingestion safety (Phase 2)

`scanners/source_ingestion.py::ingest_zip_archive()` rejects, before extracting a single byte:
Zip Slip / path-traversal entries, absolute-path entries (both POSIX and Windows drive-letter
forms), symlink entries (via the Unix mode bits in a ZIP's `external_attr`), archives exceeding
`max_archive_entry_count` or `max_archive_uncompressed_bytes`, and any single entry whose
compression ratio exceeds `max_archive_compression_ratio` (a zip-bomb heuristic). Extraction
itself re-validates every resolved path stays inside the extraction root as defense in depth.
All extraction happens in an isolated temp directory (`Settings.scan_temp_dir`) that
`SourceHandle.cleanup()` removes after the scan — verified by
`tests/unit/test_source_ingestion.py` (11 tests) and
`tests/security/test_scan_no_source_modification.py::test_scanning_a_zip_archive_never_modifies_the_original_zip`.

## Secret handling

- `governance/secret_masker.py` — regex-based pattern coverage (AWS/GitHub/OpenAI/
  Anthropic/Google keys, JWTs, env-style `KEY=value` secrets, Bearer tokens). **Line-start
  anchored** for the env-style pattern — `PASSWORD=value` is caught,
  `SOME_PREFIX_PASSWORD=value` on the same line start is not (verified in
  `tests/security/test_secret_masker.py`). Banking-specific patterns (PANs, IBANs, routing
  numbers) are **not yet included** — this is a known gap, not a completeness claim.
- `governance/report_sanitizer.py` — re-masks secrets and strips auto-fix/patch-plan content
  from any report. This is the code-level enforcement of "recommend, never auto-fix."
- `core/config.py` rejects the specific insecure placeholder credential fragment found during
  the audit in `ai-project-control-tower/app/core/config.py:89`
  (`control_tower_pass`) — enforced by a `field_validator`, verified by
  `tests/unit/test_config_defaults.py::test_rejects_legacy_insecure_placeholder_credential`.
  No field in `core/config.py` carries any default credential, placeholder or otherwise.
- `.env.example` contains only empty placeholders; verified by
  `tests/security/test_env_example_no_real_secrets.py` to contain no real-looking secret
  patterns and to keep `EXTERNAL_PROVIDERS_ENABLED=false` / `LOCAL_ONLY_MODE=true`.
- **Phase 2 extensions to `governance/secret_masker.py`:** added an unanchored quoted-
  assignment pattern (catches `db_password = "..."` in code, not just `.env`-style lines) and a
  connection-string-credential pattern (`postgres://user:PASS@host` etc.), plus a new
  `find_secret_spans()` function that `scanners/rules/secret_scanner.py` reuses so detection
  and masking share one pattern set rather than two. `storage/db/models/finding.py` deliberately
  has **no raw-`evidence` column** — only `masked_evidence` is ever persisted; this is a
  structural (schema-level) guarantee, not just an application-level one, verified by
  `tests/unit/test_scan_repository.py::test_finding_row_has_no_raw_evidence_column`.
  `tests/security/test_no_secret_leakage_in_logs.py` verifies a full scan run never emits a
  raw secret value to the logging system.

## PII redaction — explicitly not complete

`governance/pii_redaction.py` is regex-based (email, phone-like sequences, long digit runs).
It does **not** detect names, addresses, or free-text account references. Do not present its
output as guaranteed PII-free in any context — see the module docstring and
`tests/security/test_pii_redaction.py::test_documented_as_non_exhaustive`.

## Prompt-injection defense — advisory by default, hard gate for the agent boundary (Phase 6)

`governance/prompt_safety.py::check_prompt_safety()` defaults to advisory (`enforce=False`):
it flags suspicious patterns but does not block a query. An `enforce=True` hard-gate mode has
existed as a documented extension point since Phase 1; it went unused until Phase 6, where
`agents/sanitizer.py::build_question_context()` — the only free-text-question entry point in
the platform — calls it with `enforce=True`. A matched pattern (e.g. "ignore previous
instructions") raises `GovernanceError` and the question is rejected outright, never merely
warned about — verified by `tests/unit/test_agent_sanitizer.py::test_build_question_context_rejects_a_prompt_injection_attempt`
and, through the UI, by `tests/unit/test_streamlit_app_smoke.py::test_asking_an_unsafe_question_shows_an_error_not_a_crash`.

## External provider isolation

- `core.config.Settings.external_providers_enabled` defaults to `False`; per-provider flags
  (`openai_enabled`, `gemini_enabled`, `claude_enabled`) also default to `False`.
- `providers/registry.py::get_provider()` requires all three conditions (kill switch,
  per-provider flag, non-empty API key) before returning anything other than `None` — verified
  by `tests/unit/test_provider_registry.py`.
- `providers/{openai,gemini,claude}_adapter.py` fail fast at construction if given an empty
  key, never log the key (`__repr__` redacts it), and never import a network-client library or
  vendor SDK, lazily or otherwise — `send()` always raises `NotImplementedError`, a deliberate
  Phase 6 scope boundary (see `providers/README.md`), not a missed implementation. No provider
  SDK (`openai`, `anthropic`, `google-generativeai`) is installed or required for local
  startup — verified by `tests/isolation/test_no_sdk_required_for_local_startup.py`.
- `tests/isolation/test_no_network_imports_outside_providers.py` statically verifies that no
  module outside `providers/` — including `agents/`, the Phase 6 boundary that orchestrates
  `providers/` — imports a network-client library (`requests`, `httpx`, `openai`, `anthropic`,
  `google.generativeai`, etc.) anywhere in the new platform's own code.

## Optional agent boundary (Phase 6)

See `docs/agent_guide.md` for the full picture (setup, configuration, cost, limitations). In
summary:

- `AGENT_ENABLED=false` by default; even when enabled, `AGENT_PROVIDER=local` is the default —
  four separate, explicit conditions must all hold before `agents/registry.py::get_agent_provider()`
  ever returns an external adapter (see that module's own docstring).
- Every agent context passes through `agents/sanitizer.py` before anything else happens:
  `governance/report_sanitizer.py::sanitize_report()` (secret masking + auto-fix stripping),
  then `governance/pii_redaction.py::redact_pii()`, then a hard character limit
  (`AGENT_MAX_CONTEXT_CHARS`, default 4000) and item-count limit (`AGENT_MAX_EVIDENCE_ITEMS`,
  default 5) — never an entire repository, never a raw source file.
- A provider failure (including the `NotImplementedError` every adapter's `send()` currently
  raises) always falls back to the local, deterministic agent mode —
  `agents/agent_service.py::_run()` never lets an exception from this boundary propagate into
  the deterministic assessment pipeline.
- Agent actions are audited exactly like every other governance action (one `AuditEvent` per
  action, metadata only — see `storage/db/models/audit_event.py`) but never write to a
  `Finding`, `Score`, `ControlEvaluation`, or `Recommendation` row — verified by
  `tests/unit/test_agent_ui_service.py::test_agent_actions_do_not_change_deterministic_findings_or_scores`
  and `::test_agent_actions_do_not_change_finalization_status`.
- End-to-end secret-leakage proof: `tests/security/test_agent_no_secret_leakage.py` runs a full
  assessment against a fixture containing a real-looking (synthetic) secret, triggers every
  agent action including against a "configured" external provider, and asserts the raw secret
  never appears in application logs, the persisted audit trail, or the response returned to
  the UI.

## Read-only enforcement extended to the assessment layer (Phase 4)

`assessment/engine.py::run_assessment()` orchestrates `ScanRepository`, `ScoringRepository`,
`ControlEvaluationRepository`, and `AuditRepository` — none of which have any filesystem access
to the scanned target; the only filesystem interaction in the entire pipeline remains
`scanners/source_ingestion.py`, unchanged from Phase 2. Verified by
`tests/security/test_assessment_no_source_modification.py`, which extends Phase 2's
hash-comparison proof to a full `run_assessment()` call, not just the raw scanner.

## Human-in-the-loop governance (Phase 4)

- `governance/approval_workflow.py` validates every review/override decision before it can be
  applied — `storage/db/repositories.py::GovernanceRepository` never persists an unvalidated
  transition. A finding's `human_review_status` can only move to `approved`, `rejected`, or
  `overridden` via an explicit reviewer action (never back to `pending`); an `overridden`
  outcome and every score override require a non-empty, recorded reason.
- `check_finalization_policy()` blocks an assessment from being treated as final while any
  domain scored `high_risk`/`critical_risk` still has a finding pending human review — verified
  by `tests/unit/test_approval_workflow.py` and `tests/unit/test_governance_repository.py`.
- Score overrides never mutate history: `GovernanceRepository.override_score()` always inserts a
  **new** `Score` row linked via `override_of`, leaving the original deterministic-engine result
  intact and queryable.
- `storage/db/models/audit_event.py`'s `audit_events` table is append-only by construction — no
  update or delete method exists anywhere in this codebase for it. Every governance-relevant
  action (scan persisted, scoring completed, control evaluation completed, assessment
  completed, finding reviewed, score overridden) is recorded via
  `governance/audit_trail.py::build_audit_event()`, which sanitizes every free-text
  summary/payload value through the same `governance/report_sanitizer.py` used for human-facing
  reports before the row is ever constructed — verified by `tests/unit/test_audit_trail.py`
  (raw-secret-in-summary and nested-payload sanitization cases) and
  `tests/unit/test_assessment_engine.py::test_run_assessment_never_leaks_the_raw_secret_anywhere`.
- `governance/retention.py` is identify-only: it can name which of the platform's own persisted
  scans are older than a configured `data_retention_days` (default `None` — disabled), but no
  code path anywhere in this codebase deletes anything as a result. See the module's own
  docstring for what remains a deliberately open decision for a later phase.

## Mock banking system: no real data, and self-contamination avoided (Phase 5)

`mock_banking_system/` contains only synthetic, deliberately-shaped placeholder values —
verified by `tests/unit/test_mock_banking_fixture.py::test_no_real_secret_shaped_values_are_present_in_the_fixture`
and by every export/report test asserting the specific fake values never appear in generated
output. A real bug was found and fixed during this phase: generated assessment reports were
initially written to `mock_banking_system/sample_exports/`, which is itself inside the scanned
tree — the report's own content (rule ids, recommendation text, masked evidence) then became
new scan input on the next run, silently inflating and destabilizing the fixture's finding
count. Fixed by writing all sample exports under `Settings.report_output_dir`
(`data/reports/mock_banking_demo/` by default) instead — never inside a scanned target. See
`mock_banking_system/README.md`'s "Hard rules" and `scripts/seed_mock_banking_demo.py`'s own
module docstring.

## Config bug found and fixed during Phase 5: `ALLOWED_SCAN_PATHS` via a real environment variable

`core/config.py::Settings.allowed_scan_paths` has always had a `mode="before"` validator
(`_parse_scan_paths`) written to accept a comma-separated string. That validator never actually
ran when the value came from a real OS environment variable: pydantic-settings' env source
attempts to JSON-decode any non-scalar-typed field before model validators run, and a plain
string like `mock_banking_system` is not valid JSON — the result was a hard `SettingsError`
crash at `Settings()` construction, not a graceful fallback. Every existing test constructed
`Settings(allowed_scan_paths=[...])` directly (bypassing the env source entirely), so this path
had never been exercised until Phase 5's own demo UI was run against a real environment
variable. Fixed by annotating the field `Annotated[list[str], NoDecode]` (pydantic-settings'
documented escape hatch for exactly this case). Verified by
`tests/unit/test_config_defaults.py`'s existing coverage plus a new regression assertion; see
`PHASE_5_COMPLETION_REPORT.md` for the full account.

## Access control — unresolved gap, unchanged from the audit

No authentication or authorization exists anywhere, consistent with all three audited
repositories and unchanged by Phase 2 (out of scope per the Phase 2 brief's explicit "Explicitly
Out of Scope" list). This remains an open question requiring a stakeholder decision on the
deployment model (see `BANKING_PLATFORM_INTEGRATION_PLAN.md` §16, open question #2).

**Confirmed and deliberately unchanged by the post-Phase-6 hardening recap** (see
`README.md`'s "Current Implementation vs. Production Requirements" table): no login, session,
role, or RBAC system was added. The owner's explicit decision for that recap was to document
this gap clearly — in this file, in `README.md`, and in the running app's own **Help / System
Information** panel — rather than add authentication, since a real auth/RBAC system is judged
out of proportion for a local, single-operator POC/MVP and was declined pending a separate,
explicit decision on the deployment model. What the recap *did* change, to reduce the false
sense of accountability this gap creates: the reviewer/actor text inputs in
`ui/streamlit_app.py` are now explicitly labeled "unverified demo entry — not authenticated,"
and the Governance tab's audit-trail view carries the same caveat next to the events it lists.
The underlying `governance/audit_trail.py::build_audit_event()` behavior (actor is any
non-empty string, sanitized before storage) is unchanged — this was a labeling/documentation
fix, not a behavior change, per the owner's explicit "no changes to the governance workflow
solely to support authentication" instruction.

Production would require: real authentication with verified credentials, session-bound
identity, role separation (RBAC) for governance actions, audit events bound to a verified
identity rather than free text, and MFA/SSO as applicable — see README.md's table for the full
list. None of this exists in the current codebase.

## Database status visibility (post-Phase-6 hardening recap)

The Streamlit status banner's "Database" indicator now reflects an actual, timed connectivity
probe (`storage/db/session.py::check_database_connectivity()` — a short-lived, disposable
`SELECT 1` connection, 2-second `connect_timeout` on PostgreSQL URLs, cached for 15 seconds via
`st.cache_data` to avoid a live round-trip on every Streamlit rerun) rather than merely checking
whether `DATABASE_URL` is set. A connectivity failure is logged (exception *type* only, not the
raw driver error, to avoid leaking connection details in this unauthenticated UI) and surfaces
as `UNREACHABLE` in the banner rather than a misleading `YES`. This is a UI status indicator
only — it does not gate or alter any assessment/governance operation, and no monitoring service
(Prometheus, Grafana, or otherwise) was added; `observability/` remains unimplemented by
deliberate scope decision.

## Error handling in the UI (post-Phase-6 hardening recap)

`ui/streamlit_app.py` previously displayed raw `str(exception)` text directly to any viewer on
five failure paths (run assessment, review a finding, override a score, ask the AI assistant a
question, run a Quick Scan). Since this UI has no authentication, that raw text (which can
incidentally include internal paths, DB errors, or library internals) was potentially visible
to anyone who could reach the app. All five now show a generic, action-specific message (e.g.
"Assessment could not be completed — see application logs for details.") while the full
exception (type + a `governance/report_sanitizer.py`-sanitized message, so any incidental
secret-shaped or auto-fix-shaped text is still masked) is logged via `core/logging.py`'s
structured logger for operator diagnosis. No scanned source content, uploaded file content, or
provider response is included in these log lines — only the exception raised by the platform's
own orchestration code.

## Runtime validation (post-Phase-6 hardening recap)

The above (database connectivity indicator, sanitized error handling, unverified-identity
labeling, and the Help / System Information panel) was manually verified against a live
`docker compose -f deployment/docker-compose.yml up --build` stack, not only against the
automated test suite: application startup, the database status banner (`CONNECTED` against a
real PostgreSQL container), Quick Scan, a full Full Assessment run, all six Full Assessment
tabs, a governance finding review (audit trail count incremented correctly, actor recorded
as typed), a deliberately-submitted prompt-injection question (rejected, generic UI message
shown, full sanitized detail logged server-side — see `docs/PROJECT_RUNBOOK.md` §13.F for one
startup-blocking Windows/CRLF issue found and fixed during this pass), and the Help / System
Information panel's content. No malformed or truncated UI text was found beyond Streamlit's
own responsive `st.metric` ellipsis behavior at narrow viewport widths (a pre-existing,
cosmetic, non-blocking display characteristic, not corrupted data — the full values are present
in the page's own text/DOM).

## What this platform does not claim

This is not a claim of banking-grade security. It is a foundation with specific, tested
guarantees (listed above) and specific, documented gaps (PII completeness, prompt-injection
hard-gating, authentication, banking-specific secret patterns, non-exhaustive scanner pattern
coverage — see `docs/phase2_scanning_guide.md`). Do not represent any component here as
production-ready or regulation-compliant. Phase 2's PII/sensitive-data scanner in particular
is pattern-based detection only and is never a regulatory compliance determination — see each
finding's own `description` field, which states this explicitly.
