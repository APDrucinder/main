from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import assert_user_scope, get_current_user_id
from database.connection import get_db
from database.models import Resume
from database.storage import upload_resume

router = APIRouter(prefix="/resume", tags=["resume"])

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/upload")
async def upload_resume_endpoint(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    user_id = current_user_id

    suffix = ALLOWED_TYPES.get(file.content_type)
    if not suffix:
        raise HTTPException(status_code=400, detail="Only PDF and Word files accepted")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum 5MB.")

    filename = f"{uuid4()}{suffix}"

    try:
        file_url = await run_in_threadpool(
            upload_resume,
            file_bytes=file_bytes,
            filename=filename,
            user_id=str(user_id),
            content_type=file.content_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to upload resume file") from exc

    resume_record = Resume(
        user_id=user_id,
        file_url=file_url,
        raw_text=None,
        parsed_data=None,
    )

    db.add(resume_record)
    await db.commit()
    await db.refresh(resume_record)

    return {
        "data": {
            "resume_id": str(resume_record.id),
            "file_url": file_url,
            "status": "uploaded",
            "message": "Resume uploaded. Parsing will begin shortly.",
        }
    }


@router.get("/{user_id}")
async def get_resume(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    assert_user_scope(current_user_id, user_id)

    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == user_id)
        .order_by(Resume.uploaded_at.desc())
        .limit(1)
    )
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(status_code=404, detail="No resume found for this user")

    return {
        "data": {
            "resume_id": str(resume.id),
            "file_url": resume.file_url,
            "parsed_data": resume.parsed_data,
            "uploaded_at": resume.uploaded_at.isoformat() if resume.uploaded_at else None,
        }
    }
