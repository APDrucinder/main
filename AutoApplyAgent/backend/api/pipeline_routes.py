from fastapi import APIRouter, UploadFile, File, HTTPException
from workers.pipeline_task import run_pipeline_task
from celery.result import AsyncResult
import shutil
import os

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

@router.post("/start")
async def start_pipeline(
    user_id: str,
    locations: list[str],
    file: UploadFile = File(...)
):
    # Save uploaded resume temporarily
    resume_path = f"uploads/{user_id}_{file.filename}"
    os.makedirs("uploads", exist_ok=True)
    
    with open(resume_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Start Celery task
    task = run_pipeline_task.delay(user_id, resume_path, locations)

    return {"task_id": task.id}


@router.get("/status/{task_id}")
async def get_pipeline_status(task_id: str):
    result = AsyncResult(task_id)

    return {
        "task_id": task_id,
        "status": result.status,        # PENDING, STARTED, SUCCESS, FAILURE
        "step": result.info.get("step") if isinstance(result.info, dict) else None,
        "result": result.result if result.successful() else None
    }