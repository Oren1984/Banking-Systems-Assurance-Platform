# controls/

## Phase 3 (implemented — see `PHASE_3_COMPLETION_REPORT.md`)

- `catalog.py` — `CONTROL_CATALOG` (8 illustrative, engineering-derived technical controls,
  each mapped 1:1 to a Phase 2 scanner category via `rule_prefix`), `upsert_catalog()`
  (idempotent seed/update against `storage/db/models/control.py::Control`),
  `control_for_rule_id()` (pure rule_id → control lookup), and (Phase 4)
  `applies_to_domain()`/`controls_for_domain()` — the precedence rule for whether a control
  applies to a given `core.domains.BankingDomain` (explicit `applies_to_domains` list, else a
  single `domain`, else universal/cross-cutting).

**Not a banking regulatory or compliance control library.** Every entry's `control_type` is
`ControlType.TECHNICAL` — see the module's own docstring and
`BANKING_PLATFORM_INTEGRATION_PLAN.md` §16 open question #4, which remains open (authoring a
real regulatory library requires domain expertise outside this project's engineering scope).

See `knowledge_base/controls/README.md` for the generated per-domain coverage manifest this
catalog drives.
