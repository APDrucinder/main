# backend/workers/celery_app.py

from celery import Celery
import os
from dotenv import load_dotenv
import ssl

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

celery_app = Celery(
    "aiagents",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["workers.tasks"]
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
)