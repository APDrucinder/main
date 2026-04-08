# backend/storage/supabase_client.py

from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
# Use service key here NOT anon key
# service key bypasses Row Level Security
# anon key is for frontend only

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

RESUME_BUCKET = "resumes"

async def upload_resume(file_bytes: bytes, filename: str, user_id: str) -> str:
    """
    Uploads resume to Supabase storage.
    Returns the file path (stored in DB, not full URL).
    """
    file_path = f"{user_id}/{filename}"

    supabase.storage.from_(RESUME_BUCKET).upload(
        path=file_path,
        file=file_bytes,
        file_options={"content-type": "application/pdf"}
    )

    return file_path

async def get_resume_url(file_path: str) -> str:
    """
    Generates a signed URL valid for 1 hour.
    Never expose permanent public URLs for resumes.
    """
    response = supabase.storage.from_(RESUME_BUCKET).create_signed_url(
        path=file_path,
        expires_in=3600  # 1 hour
    )
    return response["signedURL"]

async def delete_resume(file_path: str):
    """
    Call this when a user deletes their account
    or uploads a new resume replacing the old one.
    """
    supabase.storage.from_(RESUME_BUCKET).remove([file_path])