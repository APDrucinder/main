from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import assert_user_scope, get_current_user_id
from database.connection import get_db
from database.models import JobPreference

router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferencesInput(BaseModel):
    target_roles: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    experience_years: int = Field(ge=0)
    salary_min: int = Field(default=0, ge=0)
    remote_ok: bool = False
    auto_apply_threshold: int = Field(default=75, ge=75, le=100)


@router.post("/{user_id}")
async def save_preferences(
    user_id: UUID,
    preferences: PreferencesInput,
    db: AsyncSession = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    assert_user_scope(current_user_id, user_id)

    result = await db.execute(select(JobPreference).where(JobPreference.user_id == user_id))
    existing = result.scalar_one_or_none()

    if existing:
        existing.target_roles = preferences.target_roles
        existing.locations = preferences.locations
        existing.experience_years = preferences.experience_years
        existing.salary_min = preferences.salary_min
        existing.remote_ok = preferences.remote_ok
        existing.auto_apply_threshold = preferences.auto_apply_threshold
    else:
        new_pref = JobPreference(user_id=user_id, **preferences.model_dump())
        db.add(new_pref)

    await db.commit()

    return {"status": "saved", "preferences": preferences.model_dump()}


@router.get("/{user_id}")
async def get_preferences(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
):
    assert_user_scope(current_user_id, user_id)

    result = await db.execute(select(JobPreference).where(JobPreference.user_id == user_id))
    prefs = result.scalar_one_or_none()

    if not prefs:
        raise HTTPException(status_code=404, detail="No preferences set yet")

    return {
        "target_roles": prefs.target_roles,
        "locations": prefs.locations,
        "experience_years": prefs.experience_years,
        "salary_min": prefs.salary_min,
        "remote_ok": prefs.remote_ok,
        "auto_apply_threshold": prefs.auto_apply_threshold,
    }
