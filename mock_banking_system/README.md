# mock_banking_system/

## Purpose

A controlled, entirely synthetic demonstration banking environment used for development,
integration tests, read-only-enforcement verification, demonstrations, UI screenshots,
sample reports, scoring validation, and RAG validation — without ever touching real banking,
customer, employee, account, transaction, credit, investment, identity, or payment data.

## Status

**Scaffolding only, as of Phase 1.** This directory currently contains an empty directory
skeleton and this README. No synthetic data, no application code, and no seed data exist yet.
Full population is scheduled for **Phase 5** ("UI, Mock System, and Demonstration Workflow") —
see `BANKING_PLATFORM_INTEGRATION_PLAN.md` Part B.

## Planned coverage

Once populated (Phase 5), this environment will contain realistic-but-synthetic examples
spanning all 16 domains defined in `core.domains.BankingDomain`, deliberately including a
controlled mixture of:

- compliant controls
- weak controls
- missing controls
- ambiguous controls
- insufficient-evidence cases
- low, medium, high, and critical findings

## Hard rules (apply for the lifetime of this directory, not just Phase 1)

- **No real customer, bank, employee, account, transaction, credit, investment, identity, or
  payment information may be used, ever.**
- No real secrets, credentials, or API keys — synthetic placeholders only.
- Everything here must be clearly identifiable as a demonstration artifact, never mistaken
  for a real banking system or real audit evidence.

## Directory layout

| Directory | Purpose | Status |
|---|---|---|
| `architecture/` | Synthetic architecture docs/diagrams for the mock system | Empty — Phase 5 |
| `app/` | Synthetic application code to be scanned by the platform | Empty — Phase 5 |
| `api/` | Synthetic API surface/specs | Empty — Phase 5 |
| `config/` | Synthetic configuration examples (including intentionally weak ones) | Empty — Phase 5 |
| `database/` | Synthetic schema/data examples | Empty — Phase 5 |
| `policies/` | Synthetic internal policy documents for RAG ingestion | Empty — Phase 5 |
| `evidence/` | Synthetic evidence artifacts | Empty — Phase 5 |
| `sample_exports/` | Synthetic exported-system data bundles | Empty — Phase 5 |

## Seed script

See `scripts/seed_mock_banking_demo.py` — a documented Phase 1 interface placeholder. It does
not seed anything yet; running it validates configuration and prints/returns the actions it
will perform once implemented in Phase 5.
