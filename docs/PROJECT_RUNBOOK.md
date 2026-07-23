# Project Runbook - Banking Systems Assurance Platform

This runbook is the detailed operational manual for local setup, startup, migrations, runtime operations, troubleshooting, and recovery.

For short copy-ready commands, use `RUN_COMMANDS.md`.

## 1. Prerequisites

- Python 3.12+
- pip
- Docker Engine
- Docker Compose (`docker compose`)
- Repository cloned locally
- Free local ports: `5434` (PostgreSQL host port), `8501` (Streamlit)

## 2. First-Time Setup

Run from repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## 3. `.env` Configuration

Set these required values in `.env`:

```env
POSTGRES_USER=<your_user>
POSTGRES_PASSWORD=<your_password>
POSTGRES_DB=<your_db>
DATABASE_URL=postgresql://<your_user>:<your_password>@localhost:5434/<your_db>
ALLOWED_SCAN_PATHS=mock_banking_system,C:\path\to\other\allowed\target
```

Notes:
- `.env` is created from `.env.example`.
- `ALLOWED_SCAN_PATHS` is a comma-separated list of relative or absolute paths.
- Keep `.env` local and uncommitted.

## 4. Startup

```powershell
.\.venv\Scripts\Activate.ps1
docker compose -f deployment/docker-compose.yml up -d
docker compose -f deployment/docker-compose.yml ps db
alembic upgrade head
streamlit run ui/streamlit_app.py
```

## 5. PostgreSQL Health and Readiness

Compose file and service:
- Compose file: `deployment/docker-compose.yml`
- Service name: `db`
- Port mapping: host `5434` -> container `5432`

Health checks:

```powershell
docker compose -f deployment/docker-compose.yml ps db
docker compose -f deployment/docker-compose.yml logs db
```

Ready state:
- `db` shows as `Up` and healthy in `docker compose ... ps db`.

## 6. Alembic Migrations

Run Alembic from repository root in the activated virtual environment.

```powershell
alembic current
alembic history
alembic upgrade head
```

If migrations fail:
- Confirm `DATABASE_URL` is valid and points to `localhost:5434`.
- Confirm PostgreSQL container is running: `docker compose -f deployment/docker-compose.yml ps db`.
- Inspect DB logs: `docker compose -f deployment/docker-compose.yml logs db`.

## 7. Streamlit Execution

```powershell
streamlit run ui/streamlit_app.py
```

Application URL:
- `http://localhost:8501`

Stop Streamlit:
- `Ctrl+C` in the Streamlit terminal.

## 8. Shutdown

```powershell
docker compose -f deployment/docker-compose.yml stop
docker compose -f deployment/docker-compose.yml down
```

Behavior:
- `docker compose -f deployment/docker-compose.yml stop` stops containers and keeps them.
- `docker compose -f deployment/docker-compose.yml down` removes containers but preserves the database volume.

## 9. Restart

Normal restart after shutdown:

```powershell
.\.venv\Scripts\Activate.ps1
docker compose -f deployment/docker-compose.yml up -d
alembic upgrade head
streamlit run ui/streamlit_app.py
```

## 10. Destructive Reset

Warning: this permanently deletes the PostgreSQL volume and stored database data.

```powershell
docker compose -f deployment/docker-compose.yml down -v
```

After reset, rebuild state:

```powershell
docker compose -f deployment/docker-compose.yml up -d
alembic upgrade head
```

## 11. Logs

```powershell
docker compose -f deployment/docker-compose.yml logs db
docker compose -f deployment/docker-compose.yml ps db
```

Optional app reachability check:

```powershell
Invoke-WebRequest http://localhost:8501 -UseBasicParsing | Select-Object -ExpandProperty StatusCode
```

## 12. Testing

All tests:

```powershell
.\.venv\Scripts\Activate.ps1
pytest
```

Integration tests (with running DB and valid `DATABASE_URL`):

```powershell
pytest tests/integration/ -v
```

## 13. Common Troubleshooting

### A. `docker compose ... up -d` fails with missing variables

Symptom:
- Error says `POSTGRES_USER`, `POSTGRES_PASSWORD`, or `POSTGRES_DB` is not set.

Fix:
- Add required values in `.env` and retry startup.

### B. Alembic URL parse errors

Symptom:
- `alembic current` or `alembic upgrade head` fails with SQLAlchemy URL parse/connection errors.

Fix:
- Correct `DATABASE_URL` in `.env`.
- Ensure host port uses `5434`.

### C. Streamlit cannot start because port is in use

Symptom:
- Streamlit reports port `8501` is already in use.

Fix:
- Stop the conflicting process, then rerun:

```powershell
streamlit run ui/streamlit_app.py
```

### D. PostgreSQL is not healthy

Symptom:
- `db` does not reach healthy/up state.

Fix:
- Review logs: `docker compose -f deployment/docker-compose.yml logs db`.
- If needed, follow the destructive reset procedure in section 10.

### E. Path validation blocks scans

Symptom:
- Scan target is rejected as not allowed.

Fix:
- Confirm target path is included in `ALLOWED_SCAN_PATHS`.
- Ensure comma-separated format and valid paths.

## 14. Recovery Steps

Use this sequence for operational recovery after failed startup/migration:

1. Stop and remove containers:

```powershell
docker compose -f deployment/docker-compose.yml down
```

2. Start fresh containers:

```powershell
docker compose -f deployment/docker-compose.yml up -d
docker compose -f deployment/docker-compose.yml ps db
```

3. Re-apply migrations:

```powershell
alembic upgrade head
```

4. Run the app:

```powershell
streamlit run ui/streamlit_app.py
```

If the issue persists, perform the destructive reset from section 10 and then repeat this recovery sequence.
