from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func
from database.models import User, Application
from fastapi import HTTPException

TIER_LIMITS={
    "Free": 10,
    "Pro": 100,
    "Max": float('inf')
}

async def get_today_application_count(
    user_id:str,
    db: AsyncSession
) -> int:

    today_start=datetime.combine(
        date.today(),
        datetime.min.time()
    )

    result=await db.execute(
        select(func.count(Application.id))
        .where(Application.user_id==user_id)
        .where(Application.applied_at >= today_start)
        .where(Application.status=="applied")
    )

    return result.scalar() or 0

async def check_tier_limit(
    user_id: str,
    db: AsyncSession
) -> dict:

    result= await db.execute(
        select(User).where(User.id==user_id)
    )
    user=result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User Not Found"
        )
    
    tier=user.subscription_tier or "free"
    limit=TIER_LIMITS.get(tier,10)
    today_count= await get_today_application_count(user_id,db)

    can_apply=(
        limit==float("inf") or
        today_count<limit

    )
    
    remaining=(
        "unlimited" if limit == float("inf")
        else max(0, limit - today_count)
    )

    return {
        "can_apply": can_apply,
        "tier": tier,
        "limit": "unlimited" if limit == float("inf") 
                 else limit,
        "used_today": today_count,
        "remaining": remaining
    }

async def increment_application_count(
    user_id: str,
    db: AsyncSession
):
    pass