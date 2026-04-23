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
- API endpoints require `X-User-Id` header and enforce user scope checks when `AUTH_REQUIRED=true`.
- `/scan/trigger` accepts either JSON body `{ "user_id": "...", "locations": [...] }` or a `user_id` query parameter.
- Integration E2E test runs only when `RUN_E2E_TESTS=true`.
