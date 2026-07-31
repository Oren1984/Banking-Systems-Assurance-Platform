# Banking Systems Assurance Platform - Run Commands (PowerShell)


## Optional Local Developer Mode (Linux / macOS)

end from virtual environment:

```bash
deactivate
```

## First-Time Docker Setup (Recommended)

```powershell
Copy-Item .env.example .env
docker compose -f deployment/docker-compose.yml up --build
```

Application access:

```text
http://localhost:8501
```

## Normal Daily Startup

```powershell
docker compose -f deployment/docker-compose.yml up -d
```

View status:

```powershell
docker compose -f deployment/docker-compose.yml ps
```

View application logs:

```powershell
docker compose -f deployment/docker-compose.yml logs -f app
```

View database logs:

```powershell
docker compose -f deployment/docker-compose.yml logs -f db
```

## Shutdown (Preserves Database Data)

```powershell
docker compose -f deployment/docker-compose.yml down
```

## Full Reset Warning

```powershell
docker compose -f deployment/docker-compose.yml down -v
```

`down -v` deletes the PostgreSQL volume and stored database data.

## Scan Target Mounts (Read-Only)

Default read-only scan target mount (already in Compose):

```yaml
volumes:
	- ../mock_banking_system:/scan-targets/mock_banking_system:ro
```

Inside Docker, scan paths must use container paths:

```env
DOCKER_ALLOWED_SCAN_PATHS=/scan-targets/mock_banking_system
```

Add another Windows scan target safely (read-only):

```yaml
volumes:
	- C:/Projects/TargetBankingSystem:/scan-targets/target-system:ro
```

Then set:

```env
DOCKER_ALLOWED_SCAN_PATHS=/scan-targets/mock_banking_system,/scan-targets/target-system
```

## Optional Local Developer Mode

Use this only when you intentionally want Python + Streamlit + Alembic outside Docker.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Start only the database container:

```powershell
docker compose -f deployment/docker-compose.yml up -d db
```

Set local mode variables (PowerShell session):

```powershell
$env:DATABASE_URL = "postgresql://<your_user>:<your_password>@localhost:5434/<your_db>"
$env:ALLOWED_SCAN_PATHS = "mock_banking_system"
```

Run migrations and Streamlit locally:

```powershell
alembic upgrade head
streamlit run ui/streamlit_app.py
```

Run tests:

```powershell
pytest
```
