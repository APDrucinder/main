from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AUTH_REQUIRED, DEV_USER_ID, attach_session_cookie, clear_session_cookie, get_current_user_id
from database.connection import get_db
from database.models import Application, Job, JobPreference, User

router = APIRouter(tags=["web"])

DEMO_LOGIN_ENABLED = os.getenv("AUTH_DEMO_LOGIN_ENABLED", "false").lower() == "true"
LOGIN_PASSWORD = os.getenv("AUTH_DEMO_PASSWORD")


def data_response(data: object) -> dict[str, object]:
    return {"data": data}


def error_response(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class SettingsPayload(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    experience_years: int = Field(default=0, ge=0)
    salary_min: int = Field(default=0, ge=0)
    remote_ok: bool = False
    auto_apply_threshold: int = Field(default=75, ge=0, le=100)


class OnboardingPayload(BaseModel):
    full_name: str = Field(min_length=1)
    target_roles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    experience_years: int = Field(default=0, ge=0)
    salary_min: int = Field(default=0, ge=0)
    remote_ok: bool = False
    auto_apply_threshold: int = Field(default=75, ge=0, le=100)


async def _fetch_or_create_user(db: AsyncSession, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        return user

    new_user = User(
        id=uuid.uuid4(),
        clerk_id=f"local-{uuid.uuid4()}",
        email=email,
        subscription_tier="free",
    )
    db.add(new_user)
    await db.flush()
    return new_user


def _user_payload(user: User) -> dict[str, str]:
    return {
        "id": str(user.id),
        "email": user.email,
        "subscription_tier": user.subscription_tier,
    }


def _dev_user_payload(email: str) -> dict[str, str]:
    return {
        "id": DEV_USER_ID or "00000000-0000-0000-0000-000000000000",
        "email": email,
        "subscription_tier": "free",
    }


@router.post("/auth/login")
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    if not DEMO_LOGIN_ENABLED or not LOGIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response("NOT_FOUND", "Password login is disabled"),
        )

    if payload.password != LOGIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response("INVALID_CREDENTIALS", "Invalid email or password"),
        )

    email = payload.email.lower()
    try:
        user = await _fetch_or_create_user(db, email)
        await db.commit()
        await db.refresh(user)
    except (TimeoutError, SQLAlchemyError):
        if AUTH_REQUIRED or not DEV_USER_ID:
            raise
        attach_session_cookie(response, UUID(DEV_USER_ID))
        return data_response({"user": _dev_user_payload(email)})

    attach_session_cookie(response, user.id)
    return data_response({"user": _user_payload(user)})


@router.post("/auth/logout")
async def logout(response: Response):
    clear_session_cookie(response)
    return data_response({"logged_out": True})


@router.get("/auth/me")
async def me(
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await db.get(User, current_user_id)
    except (TimeoutError, SQLAlchemyError):
        if AUTH_REQUIRED:
            raise
        return data_response({"user": _dev_user_payload("local@example.com")})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response("UNAUTHORIZED", "Session is invalid"),
        )
    return data_response({"user": _user_payload(user)})


@router.get("/dashboard")
async def dashboard(
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = start_of_today - timedelta(days=now.weekday())

    try:
        total_result = await db.execute(
            select(func.count(Application.id)).where(Application.user_id == current_user_id)
        )
        applied_today_result = await db.execute(
            select(func.count(Application.id)).where(
                Application.user_id == current_user_id,
                Application.applied_at >= start_of_today,
            )
        )
        applied_week_result = await db.execute(
            select(func.count(Application.id)).where(
                Application.user_id == current_user_id,
                Application.applied_at >= start_of_week,
            )
        )
        interview_result = await db.execute(
            select(func.count(Application.id)).where(
                Application.user_id == current_user_id,
                Application.user_feedback == "got_interview",
            )
        )

        recent_result = await db.execute(
            select(Application, Job)
            .join(Job, Application.job_id == Job.id)
            .where(Application.user_id == current_user_id)
            .order_by(Application.applied_at.desc())
            .limit(10)
        )
    except (TimeoutError, SQLAlchemyError):
        if AUTH_REQUIRED:
            raise
        return data_response(
            {
                "stats": {
                    "total_applied": 0,
                    "applied_today": 0,
                    "applied_this_week": 0,
                    "interviews": 0,
                },
                "recent_applications": [],
            }
        )
    recent_rows = recent_result.all()
    recent = [
        {
            "application_id": str(application.id),
            "status": application.status,
            "match_score": application.match_score,
            "applied_at": application.applied_at.isoformat() if application.applied_at else None,
            "job": {
                "id": str(job.id),
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "apply_url": job.apply_url,
            },
        }
        for application, job in recent_rows
    ]

    return data_response(
        {
            "stats": {
                "total_applied": total_result.scalar() or 0,
                "applied_today": applied_today_result.scalar() or 0,
                "applied_this_week": applied_week_result.scalar() or 0,
                "interviews": interview_result.scalar() or 0,
            },
            "recent_applications": recent,
        }
    )


@router.get("/applications")
async def applications(
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(Application, Job)
            .join(Job, Application.job_id == Job.id)
            .where(Application.user_id == current_user_id)
            .order_by(Application.applied_at.desc())
        )
    except (TimeoutError, SQLAlchemyError):
        if AUTH_REQUIRED:
            raise
        return data_response({"applications": [], "total": 0})
    rows = result.all()

    payload = [
        {
            "application_id": str(application.id),
            "status": application.status,
            "match_score": application.match_score,
            "matched_skills": application.matched_skills,
            "missing_skills": application.missing_skills,
            "reasoning": application.reasoning,
            "manual_apply_url": application.manual_apply_url,
            "applied_at": application.applied_at.isoformat() if application.applied_at else None,
            "job": {
                "id": str(job.id),
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "salary_range": job.salary_range,
                "apply_url": job.apply_url,
                "source": job.source,
            },
        }
        for application, job in rows
    ]

    return data_response({"applications": payload, "total": len(payload)})


@router.patch("/settings")
async def update_settings(
    payload: SettingsPayload,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(select(JobPreference).where(JobPreference.user_id == current_user_id))
        preference = result.scalar_one_or_none()

        if preference is None:
            preference = JobPreference(user_id=current_user_id)
            db.add(preference)

        preference.target_roles = payload.target_roles
        preference.locations = payload.locations
        preference.experience_years = payload.experience_years
        preference.salary_min = payload.salary_min
        preference.remote_ok = payload.remote_ok
        preference.auto_apply_threshold = payload.auto_apply_threshold
        preference.is_active = True

        await db.commit()
    except (TimeoutError, SQLAlchemyError):
        if AUTH_REQUIRED:
            raise

    return data_response({"settings": payload.model_dump()})


@router.post("/onboarding")
async def onboarding(
    payload: OnboardingPayload,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await db.get(User, current_user_id)
    except (TimeoutError, SQLAlchemyError):
        user = None
        if AUTH_REQUIRED:
            raise
    if not user:
        if not AUTH_REQUIRED:
            return data_response(
                {
                    "user": _dev_user_payload("local@example.com"),
                    "onboarding_completed": True,
                    "settings": {
                        "target_roles": payload.target_roles,
                        "locations": payload.locations,
                        "experience_years": payload.experience_years,
                        "salary_min": payload.salary_min,
                        "remote_ok": payload.remote_ok,
                        "auto_apply_threshold": payload.auto_apply_threshold,
                    },
                }
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response("UNAUTHORIZED", "Session is invalid"),
        )

    result = await db.execute(select(JobPreference).where(JobPreference.user_id == current_user_id))
    preference = result.scalar_one_or_none()
    if preference is None:
        preference = JobPreference(user_id=current_user_id)
        db.add(preference)

    preference.target_roles = payload.target_roles
    preference.locations = payload.locations
    preference.experience_years = payload.experience_years
    preference.salary_min = payload.salary_min
    preference.remote_ok = payload.remote_ok
    preference.auto_apply_threshold = payload.auto_apply_threshold
    preference.is_active = True

    await db.commit()

    return data_response(
        {
            "user": _user_payload(user),
            "onboarding_completed": True,
            "settings": {
                "target_roles": payload.target_roles,
                "locations": payload.locations,
                "experience_years": payload.experience_years,
                "salary_min": payload.salary_min,
                "remote_ok": payload.remote_ok,
                "auto_apply_threshold": payload.auto_apply_threshold,
            },
        }
    )
