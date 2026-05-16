from __future__ import annotations

import logging
import os
from typing import List
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, TimeoutError as SQLAlchemyTimeoutError

from api.application_routes import router as application_router
from api.pipeline_routes import router as pipeline_router
from api.preferences_routes import router as preferences_router
from api.resume_routes import router as resume_router
from api.scan_routes import router as scan_router
from api.scan_direct_routes import router as scan_direct_router
from api.web_routes import router as web_router
from api.clerk_webhook import router as webhook_router

try:
    import sentry_sdk
except ImportError:  # pragma: no cover
    sentry_sdk = None

load_dotenv()

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
]

LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _is_loopback_origin(origin: str) -> bool:
    try:
        return urlsplit(origin).hostname in LOOPBACK_HOSTS
    except ValueError:
        return False


def _expand_loopback_origins(origins: list[str]) -> list[str]:
    expanded = list(origins)
    for origin in origins:
        try:
            parts = urlsplit(origin)
            port = parts.port
        except ValueError:
            continue

        if parts.scheme not in {"http", "https"} or parts.hostname not in LOOPBACK_HOSTS:
            continue

        for host in LOOPBACK_HOSTS:
            host_label = f"[{host}]" if ":" in host else host
            netloc = f"{host_label}:{port}" if port else host_label
            expanded.append(urlunsplit((parts.scheme, netloc, "", "", "")))

    return _dedupe(expanded)


def _parse_origins(value: str | None) -> List[str]:
    origins = (
        [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        if value
        else []
    )
    if not origins:
        origins = list(DEFAULT_CORS_ORIGINS)
    elif any(_is_loopback_origin(origin) for origin in origins):
        origins = [*DEFAULT_CORS_ORIGINS, *origins]
    return _expand_loopback_origins(origins)


def _init_sentry() -> None:
    if sentry_sdk is None:
        return
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return

    try:
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.2")),
            environment=os.getenv("ENVIRONMENT", "development"),
            release=os.getenv("APP_VERSION"),
        )
    except Exception:
        # Do not block API startup if DSN is invalid in local/dev setup.
        return


_init_sentry()

app = FastAPI(
    title="AIAgents API",
    version=os.getenv("APP_VERSION", "dev"),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_origins(os.getenv("CORS_ALLOW_ORIGINS")),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
            }
        },
    )


@app.exception_handler(SQLAlchemyTimeoutError)
async def database_timeout_handler(_: Request, __: SQLAlchemyTimeoutError):
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "DATABASE_UNAVAILABLE",
                "message": "Database is unavailable. Check DATABASE_URL or network access.",
            }
        },
    )


@app.exception_handler(TimeoutError)
async def database_connection_timeout_handler(_: Request, __: TimeoutError):
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "DATABASE_UNAVAILABLE",
                "message": "Database is unavailable. Check DATABASE_URL or network access.",
            }
        },
    )


logger = logging.getLogger("aiagents")


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(_: Request, exc: SQLAlchemyError):
    logger.exception("SQLAlchemy error: %s", exc)
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "DATABASE_ERROR",
                "message": "Database request failed.",
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Unexpected server error",
            }
        },
    )


app.include_router(web_router)
app.include_router(resume_router)
app.include_router(preferences_router)
app.include_router(scan_router)
app.include_router(scan_direct_router)
app.include_router(application_router)
app.include_router(pipeline_router)
app.include_router(webhook_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "running", "environment": os.getenv("ENVIRONMENT", "development")}
