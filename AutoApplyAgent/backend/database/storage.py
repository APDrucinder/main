import os
from typing import Optional, Any
from dotenv import load_dotenv
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
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured"
        )

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

    # Use signed URL instead of public URL
    # Works even with private bucket
    result = client.storage.from_("resumes").create_signed_url(
        file_path,
        expires_in=604800  # 7 days
    )
    
    signed_url = result.get("signedURL") or result.get("signedUrl")
    
    if not signed_url:
        logger.warning(
            "Could not get signed URL, falling back to public URL",
            file_path=file_path
        )
        return client.storage.from_("resumes").get_public_url(file_path)
    
    logger.info("Resume uploaded", file_path=file_path)
    return signed_url


def save_to_manual_queue(user_id: str, job_id: str):
    client = _get_supabase_client()
    try:
        response = (
            client.table("applications")
            .insert({
                "user_id": user_id,
                "job_id": job_id,
                "status": "manual_queue",
                "reasoning": "No ATS handler matched for URL",
            })
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