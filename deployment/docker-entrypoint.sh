#!/bin/sh
set -eu

# Connection settings come from the root .env (env_file in
# deployment/docker-compose.yml) -- the same values the db service uses.
# core/config.py builds the in-network DATABASE_URL from POSTGRES_* and the
# scan allow-list from DOCKER_ALLOWED_SCAN_PATHS (see the compose file).
if [ -z "${POSTGRES_PASSWORD:-}" ]; then
    echo "POSTGRES_PASSWORD is not set in .env -- see docs/OPERATIONS.md." >&2
    exit 1
fi
if [ "${POSTGRES_PASSWORD}" = "CHANGE_ME" ]; then
    echo "WARNING: POSTGRES_PASSWORD is still the CHANGE_ME placeholder; set a real value in .env." >&2
fi

echo "Waiting for PostgreSQL availability..."
python - <<'PY'
import os
import sys
import time

import psycopg2

from core.config import get_settings

db_url = get_settings().database_url
if not db_url:
    print("No database connection configured (DATABASE_URL / POSTGRES_*); cannot run migrations.", file=sys.stderr)
    sys.exit(1)

max_attempts = 30
for attempt in range(1, max_attempts + 1):
    try:
        conn = psycopg2.connect(db_url)
        conn.close()
        print(f"PostgreSQL connection succeeded on attempt {attempt}.")
        break
    except Exception as exc:  # pragma: no cover
        reason = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        # A wrong password will not fix itself — stop with a clear message
        # instead of retrying. (psycopg2's message never contains the password.)
        if "password authentication failed" in reason:
            print(
                f"PostgreSQL rejected the credentials: {reason}\n"
                "POSTGRES_PASSWORD in .env must match the password the database volume was "
                "created with. See docs/OPERATIONS.md (Troubleshooting).",
                file=sys.stderr,
            )
            sys.exit(1)
        if attempt >= max_attempts:
            print(f"PostgreSQL did not become available: {reason}", file=sys.stderr)
            sys.exit(1)
        print(f"Attempt {attempt}/{max_attempts} failed ({reason}); retrying in 2s...")
        time.sleep(2)
PY

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting Streamlit..."
# 0.0.0.0 is the address *inside* the container (required for Docker port
# publishing). Host exposure is limited to localhost by the 127.0.0.1 port
# binding in deployment/docker-compose.yml.
exec streamlit run ui/app.py --server.address=0.0.0.0 --server.port=8501
