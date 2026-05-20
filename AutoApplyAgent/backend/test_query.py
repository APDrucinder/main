import asyncio
from sqlalchemy import select, func, case, cast, Integer
from datetime import datetime, timedelta

from database.connection import AsyncSessionLocal
from database.models import Application

async def query_application_stats():
    now = datetime.utcnow()
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = start_of_today - timedelta(days=now.weekday())

    async with AsyncSessionLocal() as db:
        stmt = select(
            func.count(Application.id),
            func.sum(cast(Application.applied_at >= start_of_today, Integer)),
            func.sum(cast(Application.applied_at >= start_of_week, Integer)),
            func.sum(cast(Application.user_feedback == "got_interview", Integer))
        )
        result = await db.execute(stmt)
        print(result.one())

if __name__ == "__main__":
    asyncio.run(query_application_stats())
