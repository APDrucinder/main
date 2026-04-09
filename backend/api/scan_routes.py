# backend/api/scan_routes.py

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.connection import get_db
from database.models import Application, Job
from workers.tasks import scan_jobs_task
from celery.result import AsyncResult

router = APIRouter(prefix="/scan", tags=["scan"])

@router.post("/trigger")
async def trigger_scan(user_id: str):
    """
    Starts a background job scan for the user.
    Returns immediately with a task_id to poll.
    """
    task = scan_jobs_task.delay(user_id)

    return {
        "task_id": task.id,
        "status": "queued",
        "message": "Scan started. Poll /scan/status for updates."
    }

@router.get("/status")
async def get_scan_status(task_id: str):
    """
    Poll this endpoint to check if the scan is done.
    Frontend calls this every 3 seconds.
    """
    task_result = AsyncResult(task_id)

    if task_result.state == "PENDING":
        return {"task_id": task_id, "status": "queued"}

    elif task_result.state == "PROGRESS":
        return {
            "task_id": task_id,
            "status": "running",
            "detail": task_result.info
        }

    elif task_result.state == "SUCCESS":
        return {
            "task_id": task_id,
            "status": "completed",
            "result": task_result.result
        }

    elif task_result.state == "FAILURE":
        return {
            "task_id": task_id,
            "status": "failed",
            "error": str(task_result.info)
        }

    return {"task_id": task_id, "status": task_result.state}


@router.get("/applications")
async def get_applications(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all applications for a user with job details.
    """
    result = await db.execute(
        select(Application, Job)
        .join(Job, Application.job_id == Job.id)
        .where(Application.user_id == user_id)
        .order_by(Application.applied_at.desc())
    )
    rows = result.all()

    if not rows:
        return {"applications": [], "total": 0}

    applications = []
    for application, job in rows:
        applications.append({
            "application_id": str(application.id),
            "job": {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "apply_url": job.apply_url,
                "source": job.source
            },
            "match_score": application.match_score,
            "matched_skills": application.matched_skills,
            "missing_skills": application.missing_skills,
            "reasoning": application.reasoning,
            "status": application.status,
            "applied_at": str(application.applied_at),
            "feedback": application.user_feedback
        })

    return {"applications": applications, "total": len(applications)}