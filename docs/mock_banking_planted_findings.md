# Mock Bank — Planted Findings Inventory

This is the authoritative, **actually-executed** record of what scanning `mock_banking_system/`
produces. Every number below was captured by running `scanners.scan_orchestrator.run_scan`
and `assessment.engine.run_assessment` against this exact fixture tree in this session, not
predicted by hand — see `docs/demo_guide.md` for the reproduction command
(`scripts/seed_mock_banking_demo.py`) and `tests/unit/test_mock_banking_fixture.py` /
`tests/integration/test_postgres_phase5_demo.py` for the tests that pin these numbers so a
future change to a scanner or to this fixture is caught as a regression, not silently absorbed.

**No real credentials, personal information, production data, or external dependencies appear
anywhere in this directory.** Every "secret," "password," "API key," email, and identity-shaped
value below is a synthetic placeholder deliberately shaped to match a detection pattern.

## Top-level result (as of this session)

- Files found: 33 · scanned: 30 · skipped: 3 (2 empty `.gitkeep`-style placeholders that no
  longer exist after population, plus `config/legacy_vault_password.secrets`, an intentionally
  unsupported extension)
- Total findings: **42**
- By severity: `critical=4, high=18, medium=10, low=10`
- Domains evaluated: **15 of 16** (every domain except `model_ai_governance`, which is
  deliberately not represented — see "Intentional gap" below)
- Full assessment run produces all **7** `DecisionCategory` values across the 16 domains —
  see "Domain scores" below.
- The same fixture scanned twice in the same session produces byte-identical findings and
  scores (excluding generated ids/timestamps) — verified by
  `tests/unit/test_mock_banking_fixture.py::test_scanning_the_mock_system_twice_is_deterministic`.

## Planted findings by file

| File | Rule(s) | Severity | Intent |
|---|---|---|---|
| `app/accounts/account_service.py` | `SECRET-001` | high | Hardcoded DB password |
| | `SQL-001` | high | String-concatenated SQL |
| | `AUDIT-002` | medium | `withdraw()` has no nearby audit call |
| | `AUDIT-003`* | low | Incidental — see note below |
| `app/accounts/account_lookup_clean.py` | — | — | **Negative example**: parameterized query, audit call present |
| `app/payments/payment_processor.py` | `SECRET-001` | high | Hardcoded gateway API key |
| | `LOG-001` | critical | `cvv`/`card_number` passed into a log call |
| `app/payments/payment_processor_clean.py` | — | — | **Negative example**: masked logging, parameterized query |
| `app/credit/loan_approval.py` | — | — | **Negative example**: audit call present on `approve_loan` |
| `app/credit/underwriter_access.py` | `PERM-003` | high | `role = "admin"` assignment |
| `app/investments/portfolio_service.py` | `AUDIT-002` | medium | `override_trade_limit()` has no nearby audit call |
| | `AUDIT-003`* | low | Incidental |
| `app/investments/portfolio_service_clean.py` | — | — | **Negative example**: parameterized query |
| `app/identity/onboarding.py` | `PII-EMAIL` | low | Synthetic customer email |
| | `PII-DATE_OF_BIRTH` | medium | Synthetic DOB field |
| | `PII-NATIONAL_ID_SHAPED` | high | SSN-shaped synthetic value |
| | `PII-ACCOUNT_NUMBER_FIELD` | high | Synthetic account-number field |
| | `PII-PHONE` ×3* | low | Incidental — the phone-shaped-digit heuristic also matches digit runs inside the DOB/national-ID/account values above; a real demonstration of regex-based scanning's known overlap, not a bug (see `docs/security_boundaries.md`) |
| `app/auth/login_handler.py` | — | — | **Negative example**: delegates to a password hasher, no hardcoded credential |
| `app/fraud/aml_screening.py` | `AUDIT-002` | medium | `flag_suspicious_transfer()` has no nearby audit call |
| | `SQL-003` | medium | `%`-style SQL formatting |
| `app/privacy/data_retention_policy.py` | `CFG-004` | high | `encrypt_enabled = false` |
| `app/security/access_control.py` | `PERM-001` | critical | Wildcard IAM `Action: "*"` |
| | `PERM-002` | high | Wildcard IAM `Resource: "*"` |
| `app/audit/audit_trail_service.py` | `AUDIT-003` | low | Audit note missing standard fields |
| `app/audit/audit_trail_service_clean.py` | — | — | **Negative example**: actor/action/timestamp/correlation_id all present |
| `app/reconciliation/ledger_reconciliation.py` | `SQL-001` | high | String-concatenated SQL |
| `app/business_continuity/disaster_recovery_plan.py` | — | — | **Negative example**: clean backup/failover check, still a real (evaluated) domain — see below |
| `database/migrations/0001_create_accounts_schema.sql` | — | — | **Negative example**: plain `CREATE TABLE`, no destructive statement |
| `database/migrations/0002_drop_legacy_ledger.sql` | `SQL-004` | high | `DROP TABLE` statement |
| `config/security_baseline.ini` | `CFG-001` | medium | `DEBUG = true` |
| | `CFG-002` | high | `verify_ssl = false` |
| | `CFG-003` | critical | `auth_enabled = false` |
| | `CFG-005` | medium | Permissive CORS (`Access-Control-Allow-Origin: *`) |
| | `CFG-006` | medium | Binds `host = 0.0.0.0` |
| | `CFG-007` | high | Default/weak credential (`admin = admin`) |
| | `CFG-008` | low | `display_errors = true` |
| `config/db_schema_credentials.env` | `SQL-005` | high | Plaintext `DB_PASSWORD` |
| `config/legacy_vault_password.secrets` | `SKIP-001` | medium | Unsupported extension, sensitive-looking name — never read |
| `api/routes/openapi_routes.yaml` | `PERM-004` | high | `public: true` |
| `infra/terraform/iam_policy.tf` | `PERM-001` | critical | Wildcard IAM `Action = "*"` |
| | `PERM-002` | high | Wildcard IAM `Resource = "*"` |
| `deployment/docker-compose.yml` | `CFG-006` | medium | Binds `HOST: 0.0.0.0` |
| `infra/k8s/configmap.yaml` | `PERM-005` | high | `allow_anonymous: true` |
| `observability/monitoring_config.yaml` | — | — | **Negative example**: no insecure settings |
| `logging/app_logger.py` | `LOG-001` | high | `password` passed into a log call |
| `README.md`, `architecture/overview.md` | `AUDIT-003`* | low | Incidental — prose that mentions "audit" without nearby actor/action/timestamp fields; the scanner does not distinguish source code from documentation, which is itself a real, worth-knowing limitation (see `docs/security_boundaries.md`) |

*Findings marked with an asterisk were not hand-planned but are genuine, reproducible scanner
output — documented rather than suppressed, consistent with this project's practice of never
hand-waving an inconvenient result.

## Domain scores (full `run_assessment()` result, this session)

| Domain | Decision category | Weighted score | Findings | Files evaluated |
|---|---|---|---|---|
| `application_security` | `critical_risk` | 0.0 | 11 | 3 |
| `infrastructure_api_security` | `critical_risk` | 19.5 | 4 | 3 |
| `payments` | `critical_risk` | 66.5 | 2 | 2 |
| `core_banking` | `high_risk` | 5.7 | 7 | 5 |
| `onboarding_identity_access` | `remediation_required` | 49.7 | 8 | 3 |
| `fraud_controls` | `remediation_required` | 51.8 | 4 | 4 |
| `database_controls_sod` | `acceptable_with_observations` | 65.0 | 2 | 3 |
| `transaction_processing_reporting` | `acceptable_with_observations` | 65.0 | 2 | 2 |
| `investments_trading` | `manual_review_required` | 93.2 | 2 | 2 |
| `monitoring_observability` | `manual_review_required` | 90.0 | 1 | 2 |
| `business_continuity_dr` | `acceptable` | 100.0 | 0 | 1 |
| `change_management` | `acceptable` | 91.6 | 1 | 1 |
| `credit_lending` | `acceptable` | 82.5 | 1 | 2 |
| `human_approval_auditability` | `acceptable` | 98.0 | 1 | 2 |
| `privacy_data_protection` | `acceptable` | 82.5 | 1 | 1 |
| `model_ai_governance` | `insufficient_evidence` | — | 0 | 0 |

**All 7 `DecisionCategory` values are represented** in a single run of this fixture —
`acceptable`, `acceptable_with_observations`, `remediation_required`, `high_risk`,
`critical_risk`, `manual_review_required`, and `insufficient_evidence`. This is what makes
this specific fixture useful for a demo: every governance/finalization scenario the platform
supports has a real, reproducible domain to point at.

`business_continuity_dr` is worth calling out specifically: it is **evaluated** (a real file
was scanned and mapped to that domain) **and** has zero findings, so it correctly resolves to
`acceptable` with a weighted score of exactly 100.0 — not `insufficient_evidence`. This is the
Phase 3 boundary case
(`tests/unit/test_scoring_engine.py::test_evaluated_domain_with_zero_findings_is_acceptable_not_insufficient`)
demonstrated with real, end-to-end data instead of a synthetic dataclass. Contrast this with
`model_ai_governance` below (never evaluated at all) and with `privacy_data_protection` (also
evaluated, but with one real finding, `acceptable` at 82.5 rather than a perfect 100.0) — three
domains, three different reasons to land in a similar-sounding "fine" band, each one real and
distinguishable in the platform's own data.

## Intentional gap: `model_ai_governance`

No file under `mock_banking_system/` maps to `model_ai_governance` — deliberately. This is not
an oversight: it exists specifically to demonstrate the platform's core correctness guarantee
(`BANKING_PLATFORM_INTEGRATION_PLAN.md` Executive Summary / §9) with real, observable output —
a domain nobody has evaluated yet resolves to `DecisionCategory.INSUFFICIENT_EVIDENCE`
(`raw_score`/`weighted_score` both `None`), never a false "clean" 100/100 score. See
`docs/demo_guide.md` step 5 for how to show this live.

## Control evaluations (this session)

A full `run_assessment()` call produces **68** `ControlEvaluation` rows (16 domains × the
`controls/catalog.py` controls applicable to each — see
`knowledge_base/controls/domain_coverage.json`): **56 `satisfied`**, **8 `gap`**, and
**4 `insufficient_evidence`** (all four belonging to `model_ai_governance`, one per applicable
cross-cutting control).
