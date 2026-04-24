import os
from typing import Optional

from dotenv import load_dotenv
from typing import Any

from shared.logger import logger

load_dotenv()

_supabase_client: Optional[Any] = None


def _get_supabase_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_service_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured")

    from supabase import create_client

    _supabase_client = create_client(supabase_url, supabase_service_key)
    return _supabase_client


def upload_resume(
    file_bytes: bytes,
    filename: str,
    user_id: str,
    content_type: str,
) -> str:
    client = _get_supabase_client()
    file_path = f"resumes/{user_id}/{filename}"

    client.storage.from_("resumes").upload(
        file_path,
        file_bytes,
        {"content-type": content_type},
    )

    return client.storage.from_("resumes").get_public_url(file_path)


def save_to_manual_queue(user_id: str, job_id: str):
    """
    Inserts a record into the applications table with a manual_queue status.
    Uses the Supabase client directly.
    """
    client = _get_supabase_client()

    try:
        response = (
            client.table("applications")
            .insert(
                {
                    "user_id": user_id,
                    "job_id": job_id,
                    "status": "manual_queue",
                    "reasoning": "No ATS handler matched for URL",
                }
            )
            .execute()
        )
        return response

    except Exception as e:
        logger.error(
            "Failed to save to manual queue",
            user_id=user_id,
            job_id=job_id,
            error=str(e),
        )
        return None
