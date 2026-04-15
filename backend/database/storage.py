from supabase import create_client
import os
from dotenv import load_dotenv
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from shared.logger import logger

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

# Changed to standard 'def' because the supabase client is synchronous
def upload_resume(
    file_bytes: bytes,
    filename: str,
    user_id: str
) -> str:
    
    file_path = f"resumes/{user_id}/{filename}"
    
    # Upload to Supabase storage
    supabase.storage.from_("resumes").upload(
        file_path, 
        file_bytes,
        {"content-type": "application/pdf"}
    )
    
    # Get public URL
    url = supabase.storage.from_("resumes").get_public_url(file_path)
    
    return url

def save_to_manual_queue(user_id: str, job_id: str):
    """
    Inserts a record into the applications table with a manual_queue status.
    Uses the Supabase client directly.
    """
    try:
       
        response = supabase.table("applications").insert({
            "user_id": user_id,
            "job_id": job_id,
            "status": "manual_queue",
            "reasoning": "No ATS handler matched for URL"
        }).execute()
        
        return response
        
    except Exception as e:
        logger.error("Failed to save to manual queue", user_id=user_id, job_id=job_id, error=str(e))
        return None