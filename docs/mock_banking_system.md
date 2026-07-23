# Mock Banking System — Status

See `mock_banking_system/README.md` for the full purpose statement, hard rules (no real
banking/customer data, ever), and directory layout, and
`docs/mock_banking_planted_findings.md` for the complete, actually-executed finding/score
inventory this fixture produces.

## Status: populated (Phase 5)

- `mock_banking_system/{app,api,config,database,deployment,infra,observability,logging,
  architecture,policies}/` — 27 synthetic source files spanning 15 of the 16 approved banking
  domains, with a controlled mix of planted positive findings, negative (clean) examples, and
  multiple severity levels.
- `scripts/seed_mock_banking_demo.py` — fully implemented. Running it
  (`python -m scripts.seed_mock_banking_demo`, requires `DATABASE_URL`) runs one real, full
  `assessment.engine.run_assessment()` call against `mock_banking_system/` and writes
  `<report_output_dir>/mock_banking_demo/latest_assessment.{json,md}` (default
  `data/reports/mock_banking_demo/`) — deliberately **outside** `mock_banking_system/` itself,
  so a generated report is never re-scanned as if it were part of the fixture (see
  `mock_banking_system/README.md`'s "Hard rules").
- `mock_banking_system/evidence/` remains intentionally empty — superseded by the platform's
  own generated `Evidence` rows (Phase 3); a static synthetic-evidence directory would
  duplicate what the platform now produces itself.

## What was deferred, and why

`model_ai_governance` has no represented content — deliberately, not an oversight. It exists
specifically so a full assessment run demonstrates `DecisionCategory.INSUFFICIENT_EVIDENCE`
against real, observable output, not a synthetic dataclass in a unit test. See
`docs/mock_banking_planted_findings.md`'s "Intentional gap" section.

Real banking regulatory/compliance control *content* (as opposed to the illustrative technical
controls this fixture exercises) remains out of scope — `BANKING_PLATFORM_INTEGRATION_PLAN.md`
§16 open question #4, unchanged.
