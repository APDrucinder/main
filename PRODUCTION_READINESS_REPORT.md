# Production Readiness Report

Date: 2026-05-20

## Executive Summary

The highest-risk code and local production-env blockers found during this review have been fixed. The app now builds, backend tests collect cleanly, protected endpoints reject unauthenticated access in the production env, and live auto-apply defaults to dry-run.

The remaining publish blockers are deployment-configuration tasks outside the repository: set the deployed HTTPS URLs, run smoke checks against those URLs, and capture/verify the LinkedIn server-side session on the deployment machine before disabling dry-run.

## Findings And Status

1. Production auth must be enforced.
   - Risk: `AUTH_REQUIRED=false` allows protected endpoints to be accessed without a Clerk/session identity.
   - Required state: `AUTH_REQUIRED=true` in production.
   - Status: fixed locally and guarded in code. Unsafe production auth now fails startup.

2. Session cookies must be HTTPS-only in production.
   - Risk: `SESSION_COOKIE_SECURE=false` sends auth cookies over non-HTTPS origins.
   - Required state: `SESSION_COOKIE_SECURE=true` in production.
   - Status: fixed locally and guarded in code.

3. Live auto-apply must start in dry-run until LinkedIn is connected on the deployment machine.
   - Risk: auto-apply can attempt browser submissions before server-side platform sessions are valid.
   - Required state for first launch: `AUTO_APPLY_ENABLED=true`, `AUTO_APPLY_DRY_RUN=true`; switch dry-run off only after server-side LinkedIn session capture passes.
   - Status: fixed in local env and code defaults. Worker/direct scan now default to dry-run.

4. Production public URLs must not point to localhost.
   - Risk: deployed users are redirected to local developer ports.
   - Required state: configure `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_LANDING_URL`, and `NEXT_PUBLIC_AGENT_ONE_URL` to deployed HTTPS URLs.
   - Status: code fallbacks are production-safe; deployment env values still need to be set to real HTTPS domains.

5. Backend test collection must be clean.
   - Risk: `test_query.py` executes a real DB query at import time and breaks full-suite pytest collection.
   - Required state: move it behind a main guard or out of pytest collection.
   - Status: fixed. Full backend pytest now collects and runs.

6. LinkedIn live auto-apply requires a valid server-side session capture.
   - Current state: no saved platform cookies were detected locally.
   - Required state: recapture LinkedIn cookies on the deployment machine or ship a proper Connect LinkedIn flow.
   - Status: not complete. This must be done on the deployment machine before turning dry-run off.

7. Deployment env files must not override real platform env vars.
   - Risk: local `.env` files can shadow production variables if loaded with override semantics.
   - Status: fixed for backend DB/env loading. Runtime deployment env vars now win over local env files.

## Verification Log

Final local checks:
- Backend compile: passed.
- Frontend lint: passed with warnings only.
- Frontend production build: passed after allowing Google Fonts fetch.
- Landing production build: passed with warnings only.
- Backend pytest: `2 passed, 1 skipped`.
- Production auth smoke:
  - `/health`: 200
  - `/platform-sessions` without auth: 401
  - `/dashboard` without auth: 401
- Production guard smoke:
  - Unsafe `AUTH_REQUIRED=false` with `ENVIRONMENT=production`: startup fails as expected.
  - Safe production auth/session env: startup passes.

Live deployed environment checks:
- Not run from this workspace because no deployed frontend/backend URL or Railway/Vercel/Render CLI is configured here.
- Current public frontend env still points to a local API URL. Replace it in the hosting provider before publishing.

## Launch Checklist

- Set production env:
  - `ENVIRONMENT=production`
  - `AUTH_REQUIRED=true`
  - `SESSION_COOKIE_SECURE=true`
  - `SESSION_SECRET=<strong non-default secret>`
  - `SESSION_SALT=<strong non-default salt>`
  - `AUTH_DEMO_LOGIN_ENABLED=false`
  - `AUTO_APPLY_ENABLED=true`
  - `AUTO_APPLY_DRY_RUN=true` for first deploy smoke test
  - `CORS_ALLOW_ORIGINS=<deployed frontend URL>,<deployed landing URL>`
  - `NEXT_PUBLIC_API_BASE_URL=<deployed backend URL>`
  - `NEXT_PUBLIC_LANDING_URL=<deployed landing URL>`
  - `NEXT_PUBLIC_AGENT_ONE_URL=<deployed frontend dashboard URL>`
- Run backend health check against deployed backend.
- Run frontend smoke test against deployed frontend.
- Confirm `/platform-sessions` requires auth in production.
- Capture LinkedIn cookies on deployment machine before disabling dry-run.

## Publish Recommendation

Safe to deploy a dry-run production smoke release after setting the deployed HTTPS URLs in the hosting provider.

Do not disable `AUTO_APPLY_DRY_RUN` until `/platform-sessions` shows a valid LinkedIn session on the deployment machine and a signed-in manual smoke check confirms LinkedIn does not open signed out.
