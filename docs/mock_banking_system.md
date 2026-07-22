# Mock Banking System — Phase 1 Status

See `mock_banking_system/README.md` for the full purpose statement, hard rules (no real
banking/customer data, ever), and planned directory layout. This document only records what
exists as of Phase 1.

## Status: scaffolding only

- `mock_banking_system/{architecture,app,api,config,database,policies,evidence,sample_exports}/`
  — empty directories, present so the Phase 5 layout is already agreed and stable.
- `scripts/seed_mock_banking_demo.py` — a documented interface placeholder. Running it
  (`python scripts/seed_mock_banking_demo.py`) validates configuration and prints the list of
  actions it will perform once implemented; it writes no data. See the module docstring for
  the full list of Phase 5 requirements (idempotent, deterministic, no real secrets, tested).

## Explicitly not done in Phase 1

- No synthetic controls, documents, findings, or assessment targets exist yet.
- No compliant/weak/missing/ambiguous/insufficient-evidence example data exists yet.
- No sample technical or executive report exists yet.

All of the above are scheduled for **Phase 5** ("UI, Mock System, and Demonstration
Workflow") per `BANKING_PLATFORM_INTEGRATION_PLAN.md` Part B. Populating this system before
`assessment/`, `scoring/`, and `models/finding.py` exist (Phases 3–4) would require either
fabricating data unconnected to any real pipeline or inventing schema ahead of the models
that define it — both were judged worse than waiting.
