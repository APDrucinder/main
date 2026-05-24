# Backend Service

FastAPI + Celery backend for resume parsing, job scan, matching, and auto-apply workflows.

## Local Run

1. Create env file:

```bash
cp .env.example .env
```

2. Install dependencies:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

3. Start API:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

4. Start Celery worker:

```bash
celery -A celery_app.celery_app worker --loglevel=info
```

5. (Optional) Start Celery beat for daily digest:

```bash
celery -A celery_app.celery_app beat --loglevel=info
```

## Tests

```bash
pytest -q
```

## Production Notes

- Set `DATABASE_URL` and Redis (`REDIS_URL` or `UPSTASH_REDIS_URL`) before deployment.
- Keep `DB_SSL_VERIFY=true` and `REDIS_SSL_CERT_REQS=required` in production.
- Use `AUTO_APPLY_DRY_RUN=true` for safe smoke runs before enabling live submission.
- Live LinkedIn auto-apply requires a valid user-specific LinkedIn session captured on the deployment machine. Capture with `python cookie_manager.py --user-id <user_uuid> linkedin`. If cookies are missing, expired, or open LinkedIn signed out, the worker stops auto-apply and marks the result as needing credentials.
- Platform cookies are isolated per user under `cookies/users/<user_uuid>/`. The backend refuses to load legacy global cookies unless `ALLOW_GLOBAL_PLATFORM_COOKIES=true` is explicitly set for a local-only legacy run.
- Do not claim automation can never be flagged by a platform. Production auto-apply uses conservative defaults: `AUTO_APPLY_MIN_THRESHOLD=75`, `AUTO_APPLY_MAX_PER_RUN=3`, and `AUTO_APPLY_MAX_CONSECUTIVE_FAILURES=2`.
- Session auth endpoints are available at `/auth/login`, `/auth/logout`, and `/auth/me`.
- Browser clients should call APIs with credentials enabled to include the HttpOnly session cookie.
- `/scan/trigger` accepts either JSON body `{ "user_id": "...", "locations": [...] }` or a `user_id` query parameter.
- Integration E2E test runs only when `RUN_E2E_TESTS=true`.
