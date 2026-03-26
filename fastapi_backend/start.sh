#!/bin/bash

set -e

run_migrations() {
    local max_retries=20
    local retry_delay=2
    local attempt=1

    while [ $attempt -le $max_retries ]; do
        echo "Running Alembic migrations (attempt ${attempt}/${max_retries})..."
        if [ -f /.dockerenv ]; then
            alembic upgrade head && return 0
        else
            uv run alembic upgrade head && return 0
        fi

        echo "Migration attempt ${attempt} failed, retrying in ${retry_delay}s..."
        sleep $retry_delay
        attempt=$((attempt + 1))
    done

    echo "Failed to apply migrations after ${max_retries} attempts."
    return 1
}

run_migrations

if [ -f /.dockerenv ]; then
    echo "Running in Docker"
    fastapi dev app/main.py --host 0.0.0.0 --port 8000 --reload &
    python watcher.py
else
    echo "Running locally with uv"
    uv run fastapi dev app/main.py --host 0.0.0.0 --port 8000 --reload &
    uv run python watcher.py
fi

wait
