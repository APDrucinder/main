from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.pipeline_routes import router as pipeline_router
from api.resume_routes import router as resume_router

app.include_router(pipeline_router)
app.include_router(resume_router)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",           # local Next.js dev
        "https://yourapp.vercel.app",      # production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    import sentry_sdk
except ImportError:  # pragma: no cover
    sentry_sdk = None

from api.application_routes import router as application_router
from api.preferences_routes import router as preferences_router
from api.resume_routes import router as resume_router
from api.scan_routes import router as scan_router

load_dotenv()


def _parse_origins(value: str | None) -> List[str]:
    if not value:
        return ["http://localhost:3000"]
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def _init_sentry() -> None:
    if sentry_sdk is None:
        return

    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return

    traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.2"))
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=traces_sample_rate,
        environment=os.getenv("ENVIRONMENT", "development"),
        release=os.getenv("APP_VERSION"),
    )


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

app.include_router(resume_router)
app.include_router(preferences_router)
app.include_router(scan_router)
app.include_router(application_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "running", "environment": os.getenv("ENVIRONMENT", "development")}
