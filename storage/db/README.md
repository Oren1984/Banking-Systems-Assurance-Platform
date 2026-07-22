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
  `Finding`, `ScannerExecutionRecord` (Phase 2 — see below).
- `repositories.py` — `ScanRepository`, the persistence layer for a Phase 2 scan result
  (Phase 2).

## Migration boundary (status corrected — see the plan's Phase 2 status correction note)

Phase 1 defined no domain tables. **Phase 2 moved the `Finding` table (and its supporting
`Scan`/`FileInventoryRecord`/`DomainMappingRecord`/`ScannerExecutionRecord` tables) earlier
than the original plan's §11 table, which had placed all of them in Phase 3.** This was
required by Phase 2's own brief (a working structured finding model + persistence was
in-scope for Phase 2, not deferred). `ai-project-control-tower`'s remaining existing tables
(`app/db/models/{audit_run,blueprint,report,project,rag_document}.py`) and the new `Control`,
`Evidence`, `Score`, and `AuditEvent` tables are still Phase 3+, unchanged.

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
