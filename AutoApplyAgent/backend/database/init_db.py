from __future__ import annotations

import asyncio

from database.connection import Base, engine
from database import models  # noqa: F401  # Ensure model metadata is registered.
from shared.logger import logger


async def init() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")


if __name__ == "__main__":
    asyncio.run(init())
