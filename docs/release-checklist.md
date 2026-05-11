## ORID Production Release Checklist

### Before Deploy
- [ ] Production `DATABASE_URL` points to managed Postgres and keeps SSL query params intact.
- [ ] `CORS_ORIGINS` only contains the real frontend domain.
- [ ] `ACCESS_SECRET_KEY`, `RESET_PASSWORD_SECRET_KEY`, and `VERIFICATION_SECRET_KEY` are strong random secrets.
- [ ] `OPENAI_API_KEY` is set in production if AI features should be enabled.
- [ ] Demo / seed / local-only variables are reviewed and removed if unnecessary.

### Database
- [ ] Create a backup or snapshot before migration.
- [ ] Run `uv run alembic upgrade head`.
- [ ] Confirm the newest revision applied successfully.
- [ ] Check that the new analytics indexes exist.

### Backend
- [ ] Backend container starts successfully with production env vars.
- [ ] Login succeeds and tokens expire on the intended schedule.
- [ ] Student free-text and feedback chat still work.
- [ ] Unsafe or prompt-injection-like student input is blocked with a user-readable error.
- [ ] Rate limiting still works after container restart.

### Frontend
- [ ] Frontend container can reach `API_BASE_URL`.
- [ ] Student week page loads without re-fetching the full message history after every feedback click.
- [ ] Teacher dashboard loads class overview successfully.
- [ ] Teacher personal tracking can open chat records.
- [ ] Internal backend crashes are not shown verbatim in browser responses.

### Demo Accounts and Data
- [ ] Test teacher account can see the expected class.
- [ ] Test student account can complete the week flow.
- [ ] `force_new` behavior only works for explicitly allowed accounts.
- [ ] Production data is separated from demo / seeded data.

### Operations
- [ ] Container restart does not break ORID progression or rate limiting behavior.
- [ ] Slow queries are checked in managed Postgres dashboards.
- [ ] Logs contain enough context for debugging but no secrets or tokens.
- [ ] Rollback steps are documented and the team knows who executes them.
