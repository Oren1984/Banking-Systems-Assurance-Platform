# assessment/

Implemented in Phase 4 ("Complete Banking Domain and Governance Layer").

- `engine.py::run_assessment()` — thin, read-only orchestration of the already-existing
  Phase 2/3/4 repositories (`ScanRepository`, `ScoringRepository`,
  `ControlEvaluationRepository`, `AuditRepository`): ingest → scan → persist → score/evidence/
  recommendations → control evaluation → audit trail. Adds no new business logic of its own —
  deterministic scanning/scoring/control-evaluation logic remains the sole authority.
- `evaluators/control_evaluator.py` — pure function generalized from
  `ai-project-control-tower/app/agents/*` (see `BANKING_PLATFORM_INTEGRATION_PLAN.md` §3):
  for every one of the 16 approved domains, determines whether each applicable catalog control
  (`controls/catalog.py`) is `satisfied`, has a `gap` (matching findings present), or is
  `insufficient_evidence` (the domain was never evaluated) — the same core "insufficient
  evidence is not a false clean" fix `scoring/engine.py` applies at the domain-score level,
  applied here at the individual-control level.
- `traceability.py` — read-only query service: given one `finding_id`, returns the full chain
  from source file → scanner rule → banking domain(s) → matched control(s) → evidence →
  current domain score → recommendation(s).

See `PHASE_4_COMPLETION_REPORT.md` for what was built, tested, and verified.
