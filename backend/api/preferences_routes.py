from fastapi import APIRouter, HTTPException, Depends
from database.connection import get_db
from database.models import JobPreference
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List

router = APIRouter(
    prefix="/preferences", 
    tags=["preferences"]
)

class PreferencesInput(BaseModel):
    target_roles: List[str]
    locations: List[str]
    experience_years: int
    salary_min: int = 0
    remote_ok: bool = False
    auto_apply_threshold: int = 75

@router.post("/{user_id}")
async def save_preferences(
    user_id: str,
    preferences: PreferencesInput,
    db: AsyncSession = Depends(get_db)
):
    # Check if preferences already exist
    result = await db.execute(
        select(JobPreference)
        .where(JobPreference.user_id == user_id)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update existing
        existing.target_roles = preferences.target_roles
        existing.locations = preferences.locations
        existing.experience_years = preferences.experience_years
        existing.salary_min = preferences.salary_min
        existing.remote_ok = preferences.remote_ok
        existing.auto_apply_threshold = preferences.auto_apply_threshold
    else:
        # Create new
        new_pref = JobPreference(
            user_id=user_id,
            **preferences.model_dump()
        )
        db.add(new_pref)
    
    await db.commit() # CRITICAL FIX: Commit the transaction!
    
    return {"status": "saved", "preferences": preferences}

@router.get("/{user_id}")
async def get_preferences(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(JobPreference)
        .where(JobPreference.user_id == user_id)
    )
    prefs = result.scalar_one_or_none()
    
    if not prefs:
        raise HTTPException(
            status_code=404,
            detail="No preferences set yet"
        )
    
    return {
        "target_roles": prefs.target_roles,
        "locations": prefs.locations,
        "experience_years": prefs.experience_years,
        "salary_min": prefs.salary_min,
        "remote_ok": prefs.remote_ok,
        "auto_apply_threshold": prefs.auto_apply_threshold
    }