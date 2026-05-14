import os
import ssl
from pathlib import Path

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

# .env lives in backend/
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

REDIS_URL = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL")
if not REDIS_URL:
    raise ValueError("REDIS_URL or UPSTASH_REDIS_URL is required for Celery")

# Upstash uses managed TLS — CERT_NONE avoids self-signed cert errors
ssl_cert_reqs_env = os.getenv("REDIS_SSL_CERT_REQS", "none").lower()
ssl_cert_reqs = ssl.CERT_REQUIRED if ssl_cert_reqs_env == "required" else ssl.CERT_NONE

use_tls = REDIS_URL.startswith("rediss://")
ssl_options = {"ssl_cert_reqs": ssl_cert_reqs} if use_tls else None

celery_app = Celery(
    "aiagents",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["workers.tasks", "workers.digest_task"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    broker_use_ssl=ssl_options,
    redis_backend_use_ssl=ssl_options,
    beat_schedule={
        "daily-digest-7pm": {
            "task": "workers.digest_task.send_daily_digest",
            "schedule": crontab(hour=19, minute=0),
        }
    },
    timezone=os.getenv("CELERY_TIMEZONE", "UTC"),
)

celery = celery_app
