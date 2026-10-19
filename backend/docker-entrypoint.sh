#!/bin/sh
set -e

echo "[entrypoint] waiting for MySQL at ${MYSQL_HOST}:${MYSQL_PORT} ..."
python - <<'PY'
import os, sys, time
import pymysql

host = os.getenv("MYSQL_HOST", "mysql")
port = int(os.getenv("MYSQL_PORT", "3306"))
user = os.getenv("MYSQL_USER", "aipm")
pwd = os.getenv("MYSQL_PASSWORD", "")

for attempt in range(1, 61):
    try:
        pymysql.connect(host=host, port=port, user=user, password=pwd,
                        connect_timeout=3).close()
        print(f"[entrypoint] MySQL ready after {attempt} attempt(s).")
        sys.exit(0)
    except Exception as exc:
        if attempt % 5 == 0:
            print(f"[entrypoint] still waiting ({attempt}/60): {exc}")
        time.sleep(2)

print("[entrypoint] MySQL did not become ready in time.", file=sys.stderr)
sys.exit(1)
PY

echo "[entrypoint] initialising schema / seed data (idempotent) ..."
python -m app.init_db

echo "[entrypoint] starting uvicorn ..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers "${UVICORN_WORKERS:-2}" \
  --proxy-headers \
  --forwarded-allow-ips='*'
