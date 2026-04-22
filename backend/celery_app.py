from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv
import ssl

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL")

celery_app = Celery(
    "aiagents",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["workers.tasks", "workers.digest_task"]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    broker_use_ssl={
        "ssl_cert_reqs": ssl.CERT_NONE
    },
    redis_backend_use_ssl={
        "ssl_cert_reqs": ssl.CERT_NONE
    },
    # ── Celery Beat Schedule ──
    beat_schedule={
        "daily-digest-7pm": {
            "task": "workers.digest_task.send_daily_digest",
            "schedule": crontab(hour=19, minute=0),  # 7:00 PM UTC every day
        }
    },
    timezone="UTC",
)

# Export both names so existing code still works
celery = celery_app