# Banking Systems Assurance Platform

## Summary

The Banking Systems Assurance Platform is a read-only assurance system for banking and high-sensitivity financial environments. It scans approved local targets, maps findings to banking domains and controls, and produces auditable assessment artifacts without modifying scanned systems.

## Problem It Solves

Financial engineering and assurance teams often need a repeatable way to evaluate system implementation against internal controls and architecture expectations while preserving source integrity.

Business problem:
- Difficult to consistently assess implementation risk across multiple domains.
- Evidence is fragmented and hard to trace through decision workflows.
- Governance reviews can become manual and inconsistent.

Technical problem:
- Teams need deterministic, read-only scanning and evidence capture.
- Findings, control evaluations, and score decisions must remain auditable.
- Operators need a local workflow that does not require external provider dependency.

## What the Platform Does

- Ingests local directories or ZIP archives for read-only scanning.
- Maps findings to banking domains and control expectations.
- Generates findings, recommendations, domain scores, and traceability links.
- Supports governance review and score overrides with audit trail records.
- Exports assessment artifacts in JSON, Markdown, and CSV.

## Why This Platform Exists

The platform exists to provide a structured, auditable, and practical assurance workflow that reduces manual review friction while preserving strict non-remediation boundaries.

## How It Works (High Level)

1. Source ingestion validates allowed paths.
2. Deterministic scanners produce findings and masked evidence.
3. Assessment logic evaluates controls and computes domain scores.
4. Governance workflows support human review and overrides.
5. Reporting and export functions produce decision-ready artifacts.

## Core Capabilities

- Read-only assessment workflow.
- Domain-based scoring and decision categorization.
- Control evaluation and traceability.
- Governance review with append-only audit events.
- Optional AI assistant tab for advisory responses.

## Safety Boundaries

- Read-only scanning only.
- No automatic remediation of scanned systems.
- No claim of legal or regulatory compliance from automated checks alone.
- **No authentication, authorization, or role separation of any kind.** Anyone who can reach
  the running app can perform every action, including governance review and score overrides.
  The reviewer/actor identity recorded in the audit trail is a self-typed, unverified value —
  not a login-backed identity. This is a deliberate POC/MVP boundary, not an oversight; see
  "Current Implementation vs. Production Requirements" below and `docs/security_boundaries.md`.

## Current Implementation vs. Production Requirements

This is a local, single-operator portfolio POC/MVP. The table below distinguishes what exists
today from what is intentionally out of scope and what a real Production deployment would
additionally require. See the in-app **Help / System Information** panel (sidebar) for the
same summary while running the app.

| Area | Implemented in this POC/MVP | Would be mandatory before Production |
|---|---|---|
| Read-only scanning, source-integrity verification | Yes | — |
| Secret masking / PII redaction in findings and reports | Yes (regex-based, documented non-exhaustive) | Broader, maintained detection coverage |
| Governance review, score overrides, append-only audit trail | Yes | Audit events bound to a verified identity, not free text |
| Reviewer/actor identity | Self-typed, unverified text field | Authenticated, session-bound identity |
| Authentication / login / logout | **Not implemented** | Real authentication with verified credentials |
| Roles / RBAC / access control | **Not implemented** | Role separation for governance actions (e.g. viewer vs. reviewer) |
| Session management | **Not implemented** | Server-side, tamper-resistant session/identity binding |
| MFA / SSO | **Not implemented** | As applicable to the deployment environment |
| Monitoring / observability | Basic in-app status indicators only (mode, DB connectivity) | Production-grade monitoring, alerting, log aggregation |
| Secrets management | `.env`-based, local-only | Managed secrets store, rotation |
| Deployment hardening | Local Docker Compose, non-root container, read-only mounts | Network isolation, TLS termination, hardened deployment pipeline |

None of the "Not implemented" items above are described anywhere in this repository as present
— if any other document appears to claim otherwise, this table and `docs/security_boundaries.md`
are authoritative.

## Architecture (High Level)

The platform is organized into modular boundaries for scanning, assessment, governance, reporting, and UI orchestration. Streamlit provides the operator interface while core logic remains in service/domain modules.

## Recommended Runtime (Docker Compose)

The primary and recommended run mode is full Docker Compose deployment:

```powershell
docker compose -f deployment/docker-compose.yml up --build
```

This launches the complete platform through containers:
- Streamlit application (`app`)
- PostgreSQL with pgvector (`db`)
- Automatic Alembic migrations during app startup
- Python dependencies in the app image

Application URL:

```text
http://localhost:8501
```

## First-Time Setup

```powershell
Copy-Item .env.example .env
docker compose -f deployment/docker-compose.yml up --build
```

## Daily Operations

Start in background:

```powershell
docker compose -f deployment/docker-compose.yml up -d
```

Status:

```powershell
docker compose -f deployment/docker-compose.yml ps
```

App logs:

```powershell
docker compose -f deployment/docker-compose.yml logs -f app
```

DB logs:

```powershell
docker compose -f deployment/docker-compose.yml logs -f db
```

Shutdown (preserves DB volume):

```powershell
docker compose -f deployment/docker-compose.yml down
```

Full reset (deletes DB data):

```powershell
docker compose -f deployment/docker-compose.yml down -v
```

Warning: `down -v` deletes the PostgreSQL named volume and stored database data.

## Read-Only Scan Mounts

Default approved scan target mount:

```yaml
volumes:
	- ../mock_banking_system:/scan-targets/mock_banking_system:ro
```

Inside Docker, the app uses container-internal scan paths:

```env
DOCKER_ALLOWED_SCAN_PATHS=/scan-targets/mock_banking_system
```

Add another Windows target safely as read-only:

```yaml
volumes:
	- C:/Projects/TargetBankingSystem:/scan-targets/target-system:ro
```

Then set:

```env
DOCKER_ALLOWED_SCAN_PATHS=/scan-targets/mock_banking_system,/scan-targets/target-system
```

## Security Boundaries

- Scan targets are mounted read-only.
- The platform does not modify scanned systems.
- No Docker socket mounting is used.
- No privileged container mode is used.
- PostgreSQL exposure remains local development mapping (`5434:5432`).
- Credentials are provided via `.env`, never hardcoded in Dockerfile or Compose.
- Recommendations are advisory only; no automatic remediation.

## Testing Summary

- Primary test execution uses `pytest` from repository root.
- Most tests run without external providers.
- PostgreSQL integration tests require a configured `DATABASE_URL` and running local database.
- **Known, non-blocking failures as of the last runtime validation:** 10 unit/security tests
  pin the mock banking fixture's finding count at 42; this environment currently produces 41
  (a pre-existing scanner/fixture drift, not caused by or related to any change in this
  document's "Current Implementation vs. Production Requirements" table). 3 e2e tests fail
  because the untouched legacy reference repositories (`AI-Project-Scope-Guard/`, etc.) are
  incomplete in some checkouts. Neither set blocks the POC/MVP demonstration — the application
  starts, runs a full assessment, and produces correct, internally consistent results end to
  end; only the specific pinned count differs from the tests' expectation. Do not "fix" these
  by changing `mock_banking_system/`, scanner logic, or the test expectations themselves
  without a separate, explicit decision — see `docs/mock_banking_planted_findings.md`.

## Demo Guidance

Run the platform locally (`docker compose -f deployment/docker-compose.yml up --build`, per
"Recommended Runtime" above), select "Full Assessment (recommended)", and use the mock banking
fixture for a complete, deterministic demonstration path — this was manually verified end to
end (initial load, database connectivity indicator, Quick Scan, Full Assessment, all six tabs,
governance review/override, audit trail, Help / System Information panel, and both success and
sanitized-failure UI messages) against a live Docker Compose stack. See
`docs/security_boundaries.md` for the exact scope of that verification.

A second, small "Reference Banking System (well-governed demo)" source option is also
selectable from the same "1. Select Source and Run Assessment" screen — it demonstrates the
same pipeline reaching the opposite outcome (mostly `acceptable`, immediate finalization
eligibility) on genuinely well-governed source, as a direct contrast to the mock system above.
See `docs/reference_banking_system_findings.md` and `docs/demo_guide.md` step 15. It is a
separate, additive fixture; it does not modify or replace the mock banking system.

## Optional Local Developer Mode

Local Python execution remains available as a secondary path for development.

- Use Docker only for `db`.
- Run Alembic and Streamlit from a local virtual environment.
- Use local DB URL `localhost:5434`.

See [RUN_COMMANDS.md](RUN_COMMANDS.md) for the exact local developer mode steps.

## Runbook

- [RUN_COMMANDS.md](RUN_COMMANDS.md)
- [docs/PROJECT_RUNBOOK.md](docs/PROJECT_RUNBOOK.md)

## Documentation

- [`docs/PROJECT_RUNBOOK.md`](docs/PROJECT_RUNBOOK.md) — detailed operations and troubleshooting
- [`docs/demo_guide.md`](docs/demo_guide.md) — end-to-end demo walkthrough
- [`docs/security_boundaries.md`](docs/security_boundaries.md) — safety boundaries and safeguards
- [`docs/architecture.md`](docs/architecture.md) — architecture and module structure
- [`docs/agent_guide.md`](docs/agent_guide.md) — optional AI assistant boundaries

## Project Ownership

Concept, architecture, implementation, governance design, testing, and validation by Oren Salami.
