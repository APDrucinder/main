# backend/database/init_db.py

import asyncio
from connection import engine, Base
import models  # triggers model registration

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("All tables created in Neon.")

asyncio.run(init())