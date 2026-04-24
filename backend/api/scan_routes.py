from __future__ import annotations

from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import assert_user_scope, get_current_user_id

router = APIRouter(prefix="/scan", tags=["scan"])


class ScanTriggerRequest(BaseModel):
    user_id: UUID
    locations: list[str] | None = Field(default=None)


@router.post("/trigger")
async def trigger_scan(
    payload: ScanTriggerRequest | None = None,
    user_id: UUID | None = None,
    current_user_id: UUID = Depends(get_current_user_id),
):
    resolved_user_id = payload.user_id if payload else user_id
    resolved_locations = payload.locations if payload else None
    if not resolved_user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    assert_user_scope(current_user_id, resolved_user_id)

    try:
        from workers.tasks import scan_jobs_task
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Scan worker unavailable: {exc}") from exc

    task = scan_jobs_task.delay(str(resolved_user_id), resolved_locations)
    return {
        "task_id": task.id,
        "status": "queued",
        "message": "Scan started. Poll /scan/status/{task_id} for updates.",
    }


@router.get("/status/{task_id}")
async def get_scan_status(task_id: str):
    task_result = AsyncResult(task_id)

    if task_result.state == "PENDING":
        return {"task_id": task_id, "status": "pending"}
    if task_result.state in {"STARTED", "PROGRESS"}:
        return {
            "task_id": task_id,
            "status": "running",
            "detail": task_result.info,
        }
    if task_result.state == "SUCCESS":
        return {
            "task_id": task_id,
            "status": "completed",
            "result": task_result.result,
        }
    if task_result.state == "FAILURE":
        return {"task_id": task_id, "status": "failed", "error": str(task_result.info)}

    raise HTTPException(status_code=500, detail=f"Unknown task state: {task_result.state}")
