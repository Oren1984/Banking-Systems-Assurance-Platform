# Run Commands (PowerShell)

Quick reference. Configuration, users, and troubleshooting: [docs/OPERATIONS.md](docs/OPERATIONS.md).

```powershell
# first time
Copy-Item .env.example .env
$env:POSTGRES_PASSWORD = "choose-a-long-random-value"
docker compose -f deployment/docker-compose.yml up -d --build

# first administrator (interactive), or see docs/OPERATIONS.md for the credentials-file option
docker compose -f deployment/docker-compose.yml exec app python -m scripts.create_admin --username your.name --display-name "Your Name"

# daily (POSTGRES_PASSWORD must be set in the shell, same value as the first time)
docker compose -f deployment/docker-compose.yml up -d
docker compose -f deployment/docker-compose.yml ps
docker compose -f deployment/docker-compose.yml logs -f app

# stop, keeping data
docker compose -f deployment/docker-compose.yml down

# tests
python -m pytest -q -rs
```

App URL: <http://localhost:8501> (bound to localhost only).

`docker compose -f deployment/docker-compose.yml down -v` deletes the database volume and all stored data.
