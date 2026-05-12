#!/bin/sh

set -eu

if [ -f /.dockerenv ]; then
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi

exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
