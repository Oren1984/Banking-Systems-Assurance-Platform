# Operations

All commands run from the repository root. Examples use PowerShell; Docker Compose v2 is required.

## Configuration

Settings come from environment variables, read through `core/config.py`. Docker Compose loads the root `.env` file (create it with `Copy-Item .env.example .env`) and then overrides two values for the container:

| Variable | Where it is used | Notes |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | `deployment/docker-compose.yml` | Read from your shell on **every** `up`: Compose uses it for the database and to build the app's `DATABASE_URL`. It is fixed when the volume is created, so always use the same value. If it is unset, Compose falls back to the placeholder `CHANGE_ME` and the app cannot connect to an existing database. To persist it: `[Environment]::SetEnvironmentVariable("POSTGRES_PASSWORD", "...", "User")`. The value in `.env` is not used for this. |
| `POSTGRES_USER`, `POSTGRES_DB` | Compose | Default `banking_assurance` / `banking_assurance_db`. |
| `DATABASE_URL` | App | Built by Compose for the container. Only needed in `.env` when running outside Docker. |
| `DOCKER_ALLOWED_SCAN_PATHS` | Compose → `ALLOWED_SCAN_PATHS` | Container paths the scanner may read. Default: the two synthetic systems under `/scan-targets/`. |
| `ALLOWED_SCAN_PATHS` | App (outside Docker) | Comma-separated. Empty means scanning is refused. |
| `SESSION_IDLE_TIMEOUT_MINUTES` | App | Default 30. |
| `PASSWORD_MIN_LENGTH` | App | Default 12. |
| `LOCAL_ONLY_MODE`, `EXTERNAL_PROVIDERS_ENABLED`, `AGENT_*` | App | Keep the defaults; external AI providers are not implemented. |
| `DATA_RETENTION_DAYS` | App | Optional, identify-only. Nothing is ever deleted automatically. |

## Running with Docker

```powershell
$env:POSTGRES_PASSWORD = "your-password"
docker compose -f deployment/docker-compose.yml up -d --build   # start (migrations run automatically)
docker compose -f deployment/docker-compose.yml ps              # status and health
docker compose -f deployment/docker-compose.yml logs -f app     # application logs
docker compose -f deployment/docker-compose.yml down            # stop, keep data
```

The UI is at <http://localhost:8501>. PostgreSQL is reachable from the host at `localhost:5434`. Both ports are bound to `127.0.0.1` only.

`docker compose ... down -v` deletes the database volume and every assessment, review, user, and audit event in it. Use it only to start over on purpose.

### Scanning another system

Mount it read-only in `deployment/docker-compose.yml` and add its container path to the allow-list:

```yaml
    volumes:
      - C:/Projects/TargetSystem:/scan-targets/target-system:ro
```

```env
DOCKER_ALLOWED_SCAN_PATHS=/scan-targets/mock_banking_system,/scan-targets/reference_banking_system,/scan-targets/target-system
```

Then choose **Custom local directory** on **Run & History** and enter `/scan-targets/target-system`.

## First administrator

There is no default account. Create one from the host:

```powershell
# interactive password prompt
docker compose -f deployment/docker-compose.yml exec app python -m scripts.create_admin --username your.name --display-name "Your Name"

# or from a local credentials file (see admin.credentials.example)
Get-Content admin.credentials | docker compose -f deployment/docker-compose.yml exec -T app python -m scripts.create_admin --credentials-file -
```

`admin.credentials` is listed in `.gitignore` and `.dockerignore`, so it never enters the repository or the image. Running the file-based command again leaves an existing account unchanged. The same commands are the recovery path if every administrator is locked out.

Synthetic demo accounts, one per role, are created only on request: `... exec app python -m scripts.seed_demo_users --demo`. The passwords are random and printed once. Deactivate these accounts before any shared use.

## User administration

Admins manage users under **Administration → Users**:

- **Create** a user with a role and a temporary password. The user must change it at first sign-in.
- **Change role**, **deactivate/activate**, or **reset password**. Each change signs the affected user out of open sessions on their next action. A reset also clears a lockout.
- Users are never deleted. An admin cannot change their own role or status, and the last active admin cannot be removed.

Every user can change their own password under **My Account**.

## Persistence and upgrades

Data lives in the Compose volume `<project>_postgres_data`. The project name defaults to the compose file's folder, so the volume is `deployment_postgres_data`. Starting a newer version on an existing volume applies new migrations automatically. The authentication migration only adds the `users` table; existing scans, findings, scores, and audit events are untouched.

## Running without Docker

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
docker compose -f deployment/docker-compose.yml up -d db
$env:DATABASE_URL = "postgresql://banking_assurance:<password>@localhost:5434/banking_assurance_db"
$env:ALLOWED_SCAN_PATHS = "mock_banking_system,reference_banking_system"
alembic upgrade head
python -m streamlit run ui/app.py
```

Use `python -m streamlit`, not the bare `streamlit` command: it puts the repository root on the import path. The bare command fails with `No module named 'ui'` unless `PYTHONPATH` points to the repository root (the Docker image sets `PYTHONPATH=/app`).

## Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| `env file ... .env not found` | Create it: `Copy-Item .env.example .env`. |
| App unhealthy, logs show authentication failed for the database | `POSTGRES_PASSWORD` is unset in this shell or differs from the value the volume was created with. Set the original value and run `up -d` again. |
| Port 8501 or 5434 already in use, or container name conflict | Another stack is using it. The container names `banking_assurance_app` and `banking_assurance_db` are fixed, so stop the other instance first. |
| "Sign-in failed" for a known account | Wrong password, deactivated account, or a 15-minute lockout after 5 failures. The message is deliberately the same in every case. An admin can reset the password, which also unlocks the account. |
| Sent back to the sign-in page | Idle timeout, an admin change to your account, or a browser refresh (each browser session signs in separately). |
| "Assessment failed — see application logs" | Usually the path is outside the allow-list or not mounted into the container. The app log names the cause; the UI shows a generic message on purpose. |
| "DATABASE_URL is not configured" | Running outside Docker without `DATABASE_URL`. Sign-in needs the database. |
