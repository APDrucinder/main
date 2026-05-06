"""
Direct scan endpoint — runs the pipeline in-process (no Celery/Redis required).
Used for local development and single-server deployments.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user_id
from shared.logger import logger

router = APIRouter(prefix="/scan", tags=["scan-direct"])

# ── In-memory scan store ──────────────────────────────────────
_scans: dict[str, dict] = {}


class DirectScanRequest(BaseModel):
    locations: list[str] | None = Field(default=None)
    resume_path: str | None = Field(default=None)


@router.post("/run")
async def run_scan_direct(
    payload: DirectScanRequest | None = None,
    current_user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Start a pipeline scan directly (no Celery)."""
    scan_id = str(uuid.uuid4())
    locations = payload.locations if payload else None
    resume_path = payload.resume_path if payload else None

    _scans[scan_id] = {
        "status": "running",
        "step": "starting",
        "user_id": str(current_user_id),
        "result": None,
        "error": None,
    }

    asyncio.create_task(
        _execute_scan(scan_id, str(current_user_id), locations, resume_path)
    )

    return {
        "scan_id": scan_id,
        "status": "running",
        "message": "Scan started. Poll /scan/run/{scan_id}/status for updates.",
    }


@router.get("/run/{scan_id}/status")
async def get_scan_run_status(scan_id: str):
    """Poll the status of a direct scan."""
    scan = _scans.get(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    return {
        "scan_id": scan_id,
        "status": scan["status"],
        "step": scan["step"],
        "result": scan["result"],
        "error": scan["error"],
    }


async def _execute_scan(
    scan_id: str,
    user_id: str,
    locations: list[str] | None,
    resume_path: str | None,
):
    """Run the pipeline and update scan state as it progresses."""
    from pipeline import JobApplicationPipeline, UserPreferences
    from database.connection import AsyncSessionLocal
    from database.models import JobPreference, Resume
    from sqlalchemy import select

    scan = _scans[scan_id]

    try:
        # Load user preferences and resume from DB
        async with AsyncSessionLocal() as db:
            pref_result = await db.execute(
                select(JobPreference).where(
                    JobPreference.user_id == uuid.UUID(user_id)
                )
            )
            pref = pref_result.scalar_one_or_none()

            resume_result = await db.execute(
                select(Resume)
                .where(Resume.user_id == uuid.UUID(user_id))
                .order_by(Resume.uploaded_at.desc())
                .limit(1)
            )
            resume_record = resume_result.scalar_one_or_none()

        # Build preferences — use DB values or sensible defaults
        if pref:
            preferences = UserPreferences(
                target_roles=pref.target_roles or ["software engineer"],
                locations=locations or pref.locations or ["Bangalore"],
                experience_years=pref.experience_years or 0,
                salary_min=pref.salary_min or 0,
                remote_ok=pref.remote_ok if pref.remote_ok is not None else False,
                auto_apply_threshold=pref.auto_apply_threshold or 75,
            )
        else:
            preferences = UserPreferences(
                target_roles=["software engineer", "python developer"],
                locations=locations or ["Bangalore"],
                experience_years=0,
                salary_min=0,
                remote_ok=False,
                auto_apply_threshold=75,
            )

        # Resolve resume path
        actual_resume_path = resume_path
        if not actual_resume_path and resume_record and resume_record.file_url:
            actual_resume_path = resume_record.file_url
        if not actual_resume_path:
            actual_resume_path = "Dhruv_Resume.pdf"  # fallback for dev

        pipeline = JobApplicationPipeline(
            apply_threshold=preferences.auto_apply_threshold,
            max_applications=50,
            user_id=user_id,
            dry_run=False,
        )

        # Hook into pipeline steps via scan state
        scan["step"] = "parsing"
        result = await pipeline.run(
            resume_path=actual_resume_path,
            preferences=preferences,
        )

        scan["status"] = "completed"
        scan["step"] = "done"
        scan["result"] = result

        logger.info("Direct scan completed", scan_id=scan_id, user_id=user_id)

    except Exception as exc:
        scan["status"] = "failed"
        scan["step"] = "error"
        scan["error"] = str(exc)
        logger.error("Direct scan failed", scan_id=scan_id, error=str(exc))
