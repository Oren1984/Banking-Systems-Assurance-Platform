# Mock Bank — Synthetic Architecture Overview

**SYNTHETIC DEMONSTRATION CONTENT — not a real bank, not real architecture.**

"Mock Bank" is a fictional, self-contained banking system built solely to give the Banking
Systems Assurance Platform something realistic-but-safe to scan for Phase 5's demonstration
workflow. It has no real users, no real money movement, and no real infrastructure — every
file under `mock_banking_system/` is source text only, never executed by the platform or by
this document.

## Fictional components

- **Accounts** (`app/accounts/`) — core banking account lookup/withdrawal.
- **Payments** (`app/payments/`) — card payment processing.
- **Credit & Lending** (`app/credit/`) — loan approval and underwriter access.
- **Investments** (`app/investments/`) — portfolio/trade services.
- **Identity & Auth** (`app/identity/`, `app/auth/`) — customer onboarding, login.
- **Fraud/AML** (`app/fraud/`) — suspicious-transfer screening.
- **Privacy** (`app/privacy/`) — data retention/encryption configuration.
- **Application Security** (`app/security/`) — access-control policy.
- **Audit** (`app/audit/`) — audit trail recording.
- **Reconciliation** (`app/reconciliation/`) — ledger reconciliation batch job.
- **Business Continuity** (`app/business_continuity/`) — backup/failover checks.
- **Database** (`database/migrations/`) — schema migrations.
- **API** (`api/routes/`) — route exposure configuration.
- **Infrastructure** (`infra/terraform/`, `infra/k8s/`) — IaC examples.
- **Change Management** (`deployment/`) — deployment configuration.
- **Monitoring** (`observability/`, `logging/`) — observability configuration.

Deliberately **not included**: any Model & AI Governance component — see
`docs/mock_banking_planted_findings.md` for why that omission is itself part of the
demonstration (it shows `DecisionCategory.INSUFFICIENT_EVIDENCE`, not a false "clean" score).
