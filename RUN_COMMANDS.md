# Run Commands (PowerShell)

Quick reference. Configuration, users, and troubleshooting: [docs/OPERATIONS.md](docs/OPERATIONS.md).

```powershell
# first time
Copy-Item .env.example .env          # then set POSTGRES_PASSWORD in .env (keep it unchanged afterwards)
docker compose -f deployment/docker-compose.yml up -d --build

# first administrator (interactive), or see docs/OPERATIONS.md for the credentials-file option
docker compose -f deployment/docker-compose.yml exec app python -m scripts.create_admin --username your.name --display-name "Your Name"

# daily
docker compose -f deployment/docker-compose.yml up -d
docker compose -f deployment/docker-compose.yml ps
docker compose -f deployment/docker-compose.yml logs -f app

# stop, keeping data
docker compose -f deployment/docker-compose.yml down

# tests
python -m pytest -q -rs
```

App URL: <http://localhost:8085> (bound to localhost only; the container listens on 8501 internally).

`docker compose -f deployment/docker-compose.yml down -v` deletes the database volume and all stored data.
