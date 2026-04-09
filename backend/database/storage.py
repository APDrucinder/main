from supabase import create_client
import os
from dotenv import load_dotenv

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