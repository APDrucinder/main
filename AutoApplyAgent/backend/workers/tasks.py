from __future__ import annotations

import asyncio

from shared.logger import logger
from workers.celery_app import celery_app
from workers.pipeline_task import execute_pipeline_task


@celery_app.task(bind=True, name="workers.tasks.scan_jobs_task")
def scan_jobs_task(self, user_id: str, locations: list[str] | None = None):
    """Queue entry point used by `/scan/trigger` to run the full pipeline."""
    self.update_state(state="PROGRESS", meta={"step": "queued", "user_id": user_id})

    try:
        return asyncio.run(
            execute_pipeline_task(
                task=self,
                user_id=user_id,
                resume_path="",
                locations=locations,
            )
        )
    except Exception as exc:
        logger.error("scan_jobs_task failed", user_id=user_id, error=str(exc))
        self.update_state(state="FAILURE", meta={"status": "failed", "error": str(exc)})
        raise
