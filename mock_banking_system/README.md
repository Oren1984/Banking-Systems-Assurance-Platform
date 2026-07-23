# mock_banking_system/

## Purpose

A controlled, entirely synthetic demonstration banking environment used for development,
integration tests, read-only-enforcement verification, demonstrations, UI screenshots,
sample reports, scoring validation, and RAG validation — without ever touching real banking,
customer, employee, account, transaction, credit, investment, identity, or payment data.

## Status: populated (Phase 5)

This directory now contains **27 synthetic source files** spanning 15 of the platform's 16
approved banking domains (`model_ai_governance` is deliberately not represented — see below),
with a controlled mix of deliberate positive findings (planted, real scanner matches),
deliberate negative findings (files that should produce zero findings), and multiple severity
levels. See `docs/mock_banking_planted_findings.md` for the complete, actually-executed
inventory of every finding this fixture produces — every number there was captured by running
the real scanner/assessment pipeline against this exact tree, not predicted by hand.

Run `python -m scripts.seed_mock_banking_demo` (requires `DATABASE_URL`) to execute a full,
real assessment against this fixture and write sample exports under
`<report_output_dir>/mock_banking_demo/` (default `data/reports/mock_banking_demo/` —
deliberately **not** inside this directory; see "Hard rules" below). See `docs/demo_guide.md`
for the full walkthrough.

## Hard rules (apply for the lifetime of this directory, not just Phase 1)

- **No real customer, bank, employee, account, transaction, credit, investment, identity, or
  payment information may be used, ever.**
- No real secrets, credentials, or API keys — synthetic placeholders only, deliberately shaped
  to match a detection pattern.
- Everything here must be clearly identifiable as a demonstration artifact, never mistaken
  for a real banking system or genuine compliance evidence.
- Meta-documentation *about* the fixture (e.g. `docs/mock_banking_planted_findings.md`) and
  every generated assessment export live **outside** this directory — anything placed inside
  `mock_banking_system/` is itself scanned on the next run, and a document or report listing
  rule IDs, recommendation text, and masked evidence would corrupt its own numbers (and break
  the determinism guarantee below) if scanned alongside the fixture that produced it. This was
  found and fixed during this phase's own implementation — see `PHASE_5_COMPLETION_REPORT.md`.

## Directory layout

| Directory | Purpose | Banking domain(s) touched |
|---|---|---|
| `app/accounts/` | Core banking account lookup/withdrawal | `core_banking` |
| `app/payments/` | Card payment processing | `payments` |
| `app/credit/` | Loan approval, underwriter access | `credit_lending` |
| `app/investments/` | Portfolio/trade services | `investments_trading` |
| `app/identity/` | Customer onboarding | `onboarding_identity_access` |
| `app/auth/` | Login handling | `onboarding_identity_access` |
| `app/fraud/` | AML/suspicious-transfer screening | `fraud_controls` |
| `app/privacy/` | Data retention/encryption configuration | `privacy_data_protection` |
| `app/security/` | Access-control policy | `application_security` |
| `app/audit/` | Audit trail recording | `human_approval_auditability` |
| `app/reconciliation/` | Ledger reconciliation | `transaction_processing_reporting`, `core_banking` |
| `app/business_continuity/` | Backup/failover checks | `business_continuity_dr` |
| `database/migrations/` | Schema migrations | `database_controls_sod` |
| `api/routes/` | API route exposure config | `infrastructure_api_security` |
| `infra/terraform/`, `infra/k8s/` | IaC examples | `infrastructure_api_security` |
| `deployment/` | Deployment configuration | `change_management` |
| `observability/`, `logging/` | Monitoring/logging configuration | `monitoring_observability` |
| `architecture/` | Synthetic architecture overview (documentation) | — |
| `policies/` | Synthetic policy document (documentation) | — |
| `evidence/` | Reserved — superseded by the platform's own generated `Evidence` rows (Phase 3); kept empty | — |

## Seed script

See `scripts/seed_mock_banking_demo.py`. Idempotent (safe to run repeatedly — each run creates
a new, real historical assessment; never mutates or deletes a prior one), deterministic (the
*content* of findings/scores is identical run to run), and contains no real secrets.
