from __future__ import annotations

from datetime import date, datetime
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Application, User

TIER_LIMITS = {
    "free": 10,
    "pro": 100,
    "power": float("inf"),
}


def _parse_user_uuid(user_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(user_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid user_id format") from exc


async def get_today_application_count(user_id: str, db: AsyncSession) -> int:
    user_uuid = _parse_user_uuid(user_id)
    today_start = datetime.combine(date.today(), datetime.min.time())

    result = await db.execute(
        select(func.count(Application.id)).where(
            Application.user_id == user_uuid,
            Application.applied_at >= today_start,
            Application.status == "applied",
        )
    )
    return result.scalar() or 0


async def check_tier_limit(user_id: str, db: AsyncSession) -> dict:
    user_uuid = _parse_user_uuid(user_id)

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tier = (user.subscription_tier or "free").lower()
    limit = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    today_count = await get_today_application_count(user_id, db)

    can_apply = limit == float("inf") or today_count < limit
    remaining = "unlimited" if limit == float("inf") else max(0, int(limit - today_count))

    return {
        "can_apply": can_apply,
        "tier": tier,
        "limit": "unlimited" if limit == float("inf") else int(limit),
        "used_today": today_count,
        "remaining": remaining,
    }


async def increment_application_count(user_id: str, db: AsyncSession):
    """No-op placeholder retained for backward compatibility."""
    _parse_user_uuid(user_id)
    return None
