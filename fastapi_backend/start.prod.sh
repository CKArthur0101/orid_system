#!/bin/sh

set -eu

# Compose 的 ${VAR} 不會從 env_file 讀；若未設 DATABASE_URL，由 POSTGRES_* 組出（與 db 容器 env_file 一致）。
if [ -f /.dockerenv ] && [ -z "${DATABASE_URL-}" ]; then
    if [ -n "${POSTGRES_USER-}" ] && [ -n "${POSTGRES_PASSWORD-}" ] && [ -n "${POSTGRES_DB-}" ]; then
        export DATABASE_URL="$(
            python -c "
import os
from urllib.parse import quote

e = os.environ
u, p, d = e['POSTGRES_USER'], e['POSTGRES_PASSWORD'], e['POSTGRES_DB']
host = (e.get('POSTGRES_HOST') or '').strip() or 'db'
port = (e.get('POSTGRES_PORT') or '').strip() or '5432'
print(
    'postgresql+asyncpg://'
    + quote(u, safe='')
    + ':'
    + quote(p, safe='')
    + f'@{host}:{port}/'
    + quote(d, safe='')
)
"
        )"
    fi
fi

if [ -f /.dockerenv ]; then
    python -c "
import os, socket, sys, time
from urllib.parse import urlparse
raw = (os.environ.get('DATABASE_URL') or '').strip()
if not raw:
    print('DATABASE_URL is not set.', file=sys.stderr)
    sys.exit(1)
p = urlparse(raw)
h, pt = p.hostname, p.port or 5432
if not h:
    print('DATABASE_URL has no hostname; set POSTGRES_HOST or fix URL.', file=sys.stderr)
    sys.exit(1)
last_err = None
for i in range(25):
    try:
        socket.getaddrinfo(h, str(pt), type=socket.SOCK_STREAM)
        last_err = None
        break
    except socket.gaierror as e:
        last_err = e
        time.sleep(1)
if last_err is not None:
    print(
        'Cannot resolve DATABASE_URL host %r port %s after retries (%s). '
        'Check: (1) backend and db share the same compose network; (2) host port bind did not fail '
        '(e.g. PROD_BACKEND_PORT free); (3) try: docker compose down && docker compose up -d --force-recreate.'
        % (h, pt, last_err),
        file=sys.stderr,
    )
    sys.exit(1)
"
    attempt=1
    max_retries=20
    retry_delay=2
    while [ "$attempt" -le "$max_retries" ]; do
        echo "Running Alembic migrations (attempt ${attempt}/${max_retries})..."
        if alembic upgrade head; then
            break
        fi
        echo "Migration attempt ${attempt} failed, retrying in ${retry_delay}s..."
        if [ "$attempt" -eq "$max_retries" ]; then
            echo "Failed to apply migrations after ${max_retries} attempts."
            exit 1
        fi
        sleep "$retry_delay"
        attempt=$((attempt + 1))
    done
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi

exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
