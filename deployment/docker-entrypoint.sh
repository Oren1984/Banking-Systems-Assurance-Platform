#!/bin/sh
set -eu

echo "Waiting for PostgreSQL availability..."
python - <<'PY'
import os
import sys
import time

import psycopg2

db_url = os.environ.get("DATABASE_URL", "")
if not db_url:
    print("DATABASE_URL is not set; cannot run migrations.", file=sys.stderr)
    sys.exit(1)

max_attempts = 30
for attempt in range(1, max_attempts + 1):
    try:
        conn = psycopg2.connect(db_url)
        conn.close()
        print(f"PostgreSQL connection succeeded on attempt {attempt}.")
        break
    except Exception as exc:  # pragma: no cover
        if attempt >= max_attempts:
            print(f"PostgreSQL did not become available: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"Attempt {attempt}/{max_attempts} failed; retrying in 2s...")
        time.sleep(2)
PY

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting Streamlit..."
exec streamlit run ui/streamlit_app.py --server.address=0.0.0.0 --server.port=8501
