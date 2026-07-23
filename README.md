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

## Demo Guidance

Run the platform locally, select "Full Assessment (recommended)", and use the mock banking fixture for a complete deterministic demonstration path.

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
