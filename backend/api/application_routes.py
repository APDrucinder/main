# backend/api/application_routes.py

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.connection import get_db
from database.models import Application, Job
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/applications", tags=["applications"])


# ─── GET /applications/{user_id} ───────────────────────────────────────────

@router.get("/{user_id}")
async def get_applications(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
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
                "id": str(job.id),
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "salary_range": job.salary_range,
                "apply_url": job.apply_url,
                "source": job.source,
                "posted_date": str(job.posted_date) if job.posted_date else None
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


# ─── GET /applications/{user_id}/stats ─────────────────────────────────────

@router.get("/{user_id}/stats")
async def get_application_stats(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = start_of_today - timedelta(days=now.weekday())

    today_result = await db.execute(
        select(func.count(Application.id))
        .where(
            Application.user_id == user_id,
            Application.applied_at >= start_of_today
        )
    )
    applied_today = today_result.scalar() or 0

    week_result = await db.execute(
        select(func.count(Application.id))
        .where(
            Application.user_id == user_id,
            Application.applied_at >= start_of_week
        )
    )
    applied_this_week = week_result.scalar() or 0

    total_result = await db.execute(
        select(func.count(Application.id))
        .where(Application.user_id == user_id)
    )
    total_applied = total_result.scalar() or 0

    interview_result = await db.execute(
        select(func.count(Application.id))
        .where(
            Application.user_id == user_id,
            Application.user_feedback == "got_interview"
        )
    )
    interviews = interview_result.scalar() or 0

    rejection_result = await db.execute(
        select(func.count(Application.id))
        .where(
            Application.user_id == user_id,
            Application.user_feedback == "rejected"
        )
    )
    rejections = rejection_result.scalar() or 0

    responded = interviews + rejections
    response_rate = round((responded / total_applied * 100), 1) if total_applied > 0 else 0

    return {
        "applied_today": applied_today,
        "applied_this_week": applied_this_week,
        "total_applied": total_applied,
        "interviews": interviews,
        "rejections": rejections,
        "response_rate_percent": response_rate
    }


# ─── POST /applications/{application_id}/feedback ──────────────────────────

VALID_FEEDBACK = {"got_interview", "rejected", "no_response"}

class FeedbackInput(BaseModel):
    feedback: str

@router.post("/{application_id}/feedback")
async def submit_feedback(
    application_id: str,
    body: FeedbackInput,
    db: AsyncSession = Depends(get_db)
):
    if body.feedback not in VALID_FEEDBACK:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feedback. Must be one of: {VALID_FEEDBACK}"
        )

    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    application.user_feedback = body.feedback

    if body.feedback == "got_interview":
        application.status = "interview"
    elif body.feedback == "rejected":
        application.status = "rejected"

    await db.commit()

    return {
        "application_id": application_id,
        "feedback": body.feedback,
        "status": application.status,
        "message": "Feedback recorded."
    }