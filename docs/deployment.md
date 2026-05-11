## Overview
This project is now intended to run as:

- `nextjs-frontend` in a long-running container on a VPS
- `fastapi_backend` in a long-running container on the same VPS (or another VM/container host)
- managed Postgres such as Supabase for the production database

`docker-compose.yml` is for local development only. Do not treat it as the production deployment spec.

## Target Architecture
The app server and API server should stay alive as normal containers. The database should be external and managed.

```text
Browser
  -> Next.js frontend container
  -> FastAPI backend container
  -> Supabase / managed Postgres
```

This matters because:

- the backend can use a normal connection pool
- cross-request state must not live only in Python memory
- the database DSN must be kept intact, including `sslmode=require` and provider-specific query params

## Production Environment Variables
Backend minimum:

```env
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:6543/postgres?sslmode=require
ACCESS_SECRET_KEY=replace_me
RESET_PASSWORD_SECRET_KEY=replace_me
VERIFICATION_SECRET_KEY=replace_me
ACCESS_TOKEN_EXPIRE_SECONDS=43200
CORS_ORIGINS=["https://your-frontend.example.com"]
FRONTEND_URL=https://your-frontend.example.com
DB_DISABLE_POOLING=false
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT_SEC=30
DB_POOL_RECYCLE_SEC=1800
OPENAI_API_KEY=replace_me
```

Frontend minimum:

```env
API_BASE_URL=http://backend:8000
ACCESS_TOKEN_COOKIE_MAX_AGE_SEC=43200
```

Notes:

- keep `DATABASE_URL` exactly as given by Supabase or your provider
- never replace production `CORS_ORIGINS` with `["*"]`
- keep demo / seed variables out of the production environment unless you explicitly need them

## Container Startup Flow
Recommended backend startup flow:

1. Build the backend image.
2. Inject production environment variables.
3. Run Alembic migrations once for the new release.
4. Start the FastAPI app.
5. Verify `/docs` or a health endpoint only from trusted networks if you expose them.

Recommended frontend startup flow:

1. Build the Next.js image.
2. Inject `API_BASE_URL`.
3. Start the Node server.

## Migration Strategy
For each release:

1. Take a database backup or snapshot first.
2. Deploy the new backend image.
3. Run `uv run alembic upgrade head`.
4. Start or restart the backend containers.
5. Smoke test login, student chat, teacher dashboard, and export.

Rollback principle:

- if migrations are backward compatible, roll back the application image first
- if a migration is not backward compatible, restore from backup instead of improvising on live data

## Supabase Notes
When using Supabase:

- use the pooled or direct connection string that matches your traffic profile
- keep SSL-related query params intact
- size `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` conservatively so you do not exhaust the database connection cap
- if you use the Supabase transaction pooler, keep per-container pool sizes small

## Security Defaults
Before go-live, confirm:

- access tokens are short-lived and cookies are `httpOnly`
- backend logs do not print JWTs or raw internal exceptions to end users
- only the production frontend origin is in `CORS_ORIGINS`
- demo-only routes and seed workflows are not exposed to normal student users
- secrets are stored in VPS environment management, not committed to the repo

## Development vs Production
Local development:

- use `docker-compose.yml`
- local Postgres containers are acceptable
- permissive CORS is acceptable only for local testing

Production:

- use dedicated container runtime or process manager on the VPS
- connect to Supabase / managed Postgres
- run migrations explicitly during deploy
- keep app containers stateless
