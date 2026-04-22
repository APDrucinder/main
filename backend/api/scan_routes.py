# backend/api/scan_routes.py

from fastapi import APIRouter, HTTPException
from workers.tasks import scan_jobs_task
from celery.result import AsyncResult

router = APIRouter(prefix="/scan", tags=["scan"])

@router.post("/trigger")
async def trigger_scan(user_id: str):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    task = scan_jobs_task.delay(user_id)

    return {
        "task_id": task.id,
        "status": "queued",
        "message": "Scan started. Poll /scan/status/{task_id} for updates."
    }


@router.get("/status/{task_id}")
async def get_scan_status(task_id: str):
    task_result = AsyncResult(task_id)

    if task_result.state == "PENDING":
        return {"task_id": task_id, "status": "pending"}
    elif task_result.state == "STARTED":
        return {"task_id": task_id, "status": "running"}
    elif task_result.state == "PROGRESS":
        return {"task_id": task_id, "status": "running", "detail": task_result.info}
    elif task_result.state == "SUCCESS":
        return {"task_id": task_id, "status": "completed", "result": task_result.result}
    elif task_result.state == "FAILURE":
        return {"task_id": task_id, "status": "failed", "error": str(task_result.info)}

    return {"task_id": task_id, "status": task_result.state.lower()}