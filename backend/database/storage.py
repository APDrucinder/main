# backend/database/storage.py

from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

RESUME_BUCKET = "resumes"

async def upload_resume(
    file_bytes: bytes,
    filename: str,
    user_id: str
) -> str:
    file_path = f"{user_id}/{filename}"

    supabase.storage.from_(RESUME_BUCKET).upload(
        path=file_path,
        file=file_bytes,
        file_options={"content-type": "application/pdf"}
    )

    return file_path

async def get_resume_url(file_path: str) -> str:
    response = supabase.storage.from_(RESUME_BUCKET).create_signed_url(
        path=file_path,
        expires_in=3600
    )
    return response["signedURL"]

async def delete_resume(file_path: str):
    supabase.storage.from_(RESUME_BUCKET).remove([file_path])