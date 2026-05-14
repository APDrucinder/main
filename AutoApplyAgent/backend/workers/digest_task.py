from workers.celery_app import celery_app

from agents.daily_digest import run_daily_digest
from shared.logger import logger


@celery_app.task(name="workers.digest_task.send_daily_digest")
def send_daily_digest():
    """Celery Beat task that runs the daily digest job."""
    logger.info("Celery Beat triggered daily digest")
    try:
        run_daily_digest()
        logger.info("Daily digest task complete")
    except Exception as exc:
        logger.error("Daily digest task failed", error=str(exc))
        raise
