from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.concurrency import run_in_threadpool
from database.storage import upload_resume
from database.connection import get_db
from database.models import Resume
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

router = APIRouter(prefix="/resume", tags=["resume"])

ALLOWED_TYPES = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
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
    
    suffix = ".pdf" if "pdf" in file.content_type else ".docx"
    filename = f"{uuid.uuid4()}{suffix}"
    
    # Run the synchronous Supabase upload in a threadpool to prevent blocking FastAPI
    file_url = await run_in_threadpool(
        upload_resume,
        file_bytes=file_bytes,
        filename=filename,
        user_id=user_id
    )
    
    # Save record to database
    resume_record = Resume(
        user_id=user_id,
        file_url=file_url,
        raw_text=None,    
        parsed_data=None  
    )
    
    db.add(resume_record)
    await db.commit() # CRITICAL FIX: Actually save to the database!
    await db.refresh(resume_record) # Refresh to safely get the generated ID
    
    return {
        "resume_id": str(resume_record.id),
        "file_url": file_url,
        "status": "uploaded",
        "message": "Resume uploaded. Parsing will begin shortly."
    }

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
        "file_url": resume.file_url,
        "parsed_data": resume.parsed_data,
        "uploaded_at": resume.uploaded_at
    }