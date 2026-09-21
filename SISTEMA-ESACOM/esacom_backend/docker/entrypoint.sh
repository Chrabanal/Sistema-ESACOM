#!/bin/sh
set -e

python - <<'PY'
import os, time
import psycopg2
from urllib.parse import urlparse

url = os.environ.get("DATABASE_URL", "")
if url.startswith("postgres"):
    parsed = urlparse(url)
    for attempt in range(60):
        try:
            conn = psycopg2.connect(
                dbname=parsed.path.lstrip('/'),
                user=parsed.username,
                password=parsed.password,
                host=parsed.hostname,
                port=parsed.port or 5432,
            )
            conn.close()
            print("PostgreSQL disponible")
            break
        except Exception as exc:
            if attempt == 59:
                raise
            print(f"Esperando PostgreSQL... {exc}")
            time.sleep(2)
PY

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
fi

exec "$@"
