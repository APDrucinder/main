from celery import Celery
celery=Celery(
    "job_agent",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["workers.pipeline_task"]
)

celery.conf.update(
    task_track_status=True,
    result_expires=3600,
)