# storage/db/

## Phase 1 (implemented)

- `base.py` — SQLAlchemy 2.x `DeclarativeBase`, adapted as-is from
  `ai-project-control-tower/app/db/base.py`. No domain models are registered against it yet.
- `session.py` — lazy engine/session factory (see module docstring for why this deviates from
  the source repo's eager pattern: `database_url` has no default here, so eager creation would
  break import-time safety).
- `alembic.ini` / `alembic/env.py` (repo root) — Alembic wired to `storage/db/base.py`'s
  metadata. `alembic/versions/` was intentionally empty in Phase 1 (no domain tables yet); it
  now contains `0001_phase2_scan_findings_tables.py` (Phase 2).
- `models/` (this subpackage) — `Scan`, `FileInventoryRecord`, `DomainMappingRecord`,
  `Finding`, `ScannerExecutionRecord` (Phase 2); `Control`, `Evidence`, `Score`,
  `Recommendation` (Phase 3); `AuditEvent`, `ControlEvaluation` (Phase 4) — see below.
- `repositories.py` — `ScanRepository` (Phase 2); `ScoringRepository` (Phase 3);
  `ControlEvaluationRepository`, `AuditRepository`, `GovernanceRepository` (Phase 4) — see
  below.

## Phase 3 (implemented)

- `models/{control,evidence,score,recommendation}.py` + 3 new columns on `findings`
  (`human_review_status`, `reviewed_by`, `reviewed_at`) — `alembic/versions/
  0002_phase3_controls_evidence_scoring.py`.
- `repositories.py::ScoringRepository` — scores every scan against all 16 domains, captures
  evidence, generates recommendations, and supports minimal recommendation review.

## Phase 4 (implemented)

- `models/{audit_event,control_evaluation}.py` — `alembic/versions/
  ..._phase4_audit_trail_control_evaluations.py`.
- `repositories.py::ControlEvaluationRepository` — persists per-(domain, control) evaluation
  results from `assessment/evaluators/control_evaluator.py`.
- `repositories.py::AuditRepository` — the only writer of `audit_events`; append-only, one
  `record()` method, no update/delete method exists.
- `repositories.py::GovernanceRepository` — applies validated `governance/approval_workflow.py`
  decisions (finding review, score override) and the finalization policy check, recording an
  audit event for every action.
- A module-level `_domain_coverage()` helper, factored out of `ScoringRepository` in this
  phase, is now shared by `ScoringRepository` and `ControlEvaluationRepository` so the two can
  never compute "which domains were actually evaluated" differently.

## Migration boundary (status corrected — see the plan's Phase 2 status correction note)

Phase 1 defined no domain tables. **Phase 2 moved the `Finding` table (and its supporting
`Scan`/`FileInventoryRecord`/`DomainMappingRecord`/`ScannerExecutionRecord` tables) earlier
than the original plan's §11 table, which had placed all of them in Phase 3.** This was
required by Phase 2's own brief (a working structured finding model + persistence was
in-scope for Phase 2, not deferred). `Control`, `Evidence`, `Score`, and `Recommendation` were
implemented in Phase 3 as planned; `AuditEvent` and `ControlEvaluation` were implemented in
Phase 4, also as planned. `ai-project-control-tower`'s remaining existing tables
(`app/db/models/{audit_run,blueprint,report,project,rag_document}.py`) were never ported —
this platform's own schema superseded them starting in Phase 2.

## Verified vs. not verified

- **Phase 1:** `storage/db/base.py` and `storage/db/session.py` import cleanly with no
  DATABASE_URL set; `get_db()`/`get_engine()` raise a clear `ConfigurationError` (not a crash)
  when called without one. `alembic upgrade head` was not run — no server was available.
- **Phase 2 (closes the Phase 1 gap):** a live PostgreSQL/pgvector instance was provisioned
  locally via Docker Compose; `alembic revision --autogenerate` produced
  `0001_phase2_scan_findings_tables.py` against the models above, `alembic upgrade head`
  applied it cleanly, and `tests/integration/test_postgres_persistence.py` verified a full
  scan result round-trips through `ScanRepository` correctly — including finding, in that
  process, two real foreign-key-ordering bugs that SQLite-only testing had missed (see
  `PHASE_2_COMPLETION_REPORT.md`).
- **Phase 3:** `0002_phase3_controls_evidence_scoring.py` applied and verified against the same
  live instance; `tests/integration/test_postgres_phase3_scoring.py` verified a full
  `score_and_generate()` round-trip. See `PHASE_3_COMPLETION_REPORT.md`.
- **Phase 4:** `..._phase4_audit_trail_control_evaluations.py` applied and verified against the
  same live instance; `tests/integration/test_postgres_phase4_assessment.py` verified a full
  `run_assessment()` round-trip including traceability and a governance review action. See
  `PHASE_4_COMPLETION_REPORT.md`.
