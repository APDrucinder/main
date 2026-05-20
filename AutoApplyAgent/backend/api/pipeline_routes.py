from __future__ import annotations

import os
import re
import uuid as _uuid
from uuid import UUID

import shutil
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from api.auth import get_current_user_id

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

_SAFE_FILENAME_RE = re.compile(r"[^\w\-. ]")


def _safe_filename(name: str) -> str:
    """Strip path separators and dangerous characters from a filename."""
    # Take only the basename, then remove anything that isn't alphanumeric / dash / dot / space
    base = os.path.basename(name)
    safe = _SAFE_FILENAME_RE.sub("_", base)
    return safe or "resume"


@router.post("/start")
async def start_pipeline(
    locations: list[str],
    file: UploadFile = File(...),
    current_user_id: UUID = Depends(get_current_user_id),
):
    """Trigger a full pipeline run via Celery for the authenticated user."""
    user_id = str(current_user_id)
    safe_name = _safe_filename(file.filename or "resume.pdf")
    resume_path = f"uploads/{user_id}_{_uuid.uuid4().hex}_{safe_name}"
    os.makedirs("uploads", exist_ok=True)

    with open(resume_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        from workers.pipeline_task import run_pipeline_task
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Pipeline worker unavailable: {exc}") from exc

    task = run_pipeline_task.delay(user_id, resume_path, locations)
    return {"task_id": task.id}


@router.get("/status/{task_id}")
async def get_pipeline_status(
    task_id: str,
    _: UUID = Depends(get_current_user_id),
):
    result = AsyncResult(task_id)

    return {
        "task_id": task_id,
        "status": result.status,
        "step": result.info.get("step") if isinstance(result.info, dict) else None,
        "result": result.result if result.successful() else None,
    }