# backend/api/resume_routes.py

from fastapi import APIRouter, UploadFile, File, HTTPException
from database.storage import upload_resume
from database.connection import get_db
from database.models import Resume
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Depends
import uuid
import tempfile
import os

router = APIRouter(prefix="/resume", tags=["resume"])

ALLOWED_TYPES = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-"
    "officedocument.wordprocessingml.document"
]

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

@router.post("/upload")
async def upload_resume_endpoint(
    user_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    # Validate file type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and Word files accepted"
        )
    
    # Read file
    file_bytes = await file.read()
    
    # Validate file size
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum 5MB."
        )
    
    # Save temporarily for parsing
    suffix = ".pdf" if "pdf" in file.content_type else ".docx"
    
    with tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False
    ) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    
    try:
        # Upload to Supabase storage
        file_url = await upload_resume(
            file_bytes=file_bytes,
            filename=f"{uuid.uuid4()}{suffix}",
            user_id=user_id
        )
        
        # Save record to database
        resume_record = Resume(
            user_id=user_id,
            storage_path=file_url,
            raw_text=None,    # Will be filled after parsing
            parsed_data=None  # Will be filled after parsing
        )
        db.add(resume_record)
        await db.flush()
        
        resume_id = str(resume_record.id)
        
        return {
            "resume_id": resume_id,
            "file_url": file_url,
            "status": "uploaded",
            "message": "Resume uploaded. "
                       "Parsing will begin shortly."
        }
        
    finally:
        # Clean up temp file
        os.unlink(tmp_path)


@router.get("/{user_id}")
async def get_resume(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == user_id)
        .order_by(Resume.uploaded_at.desc())
        .limit(1)
    )
    resume = result.scalar_one_or_none()
    
    if not resume:
        raise HTTPException(
            status_code=404,
            detail="No resume found for this user"
        )
    
    return {
        "resume_id": str(resume.id),
        "storage_path": resume.storage_path,
        "parsed_data": resume.parsed_data,
        "uploaded_at": resume.uploaded_at
    }