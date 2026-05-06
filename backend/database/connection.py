import os
import ssl
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase

ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
BACKEND_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"

# Load root .env first (preferred), then backend/.env for backward compatibility.
load_dotenv(dotenv_path=ROOT_ENV_PATH, override=False)
load_dotenv(dotenv_path=BACKEND_ENV_PATH, override=False)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing from .env")

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    connect_args={"ssl": ssl_context}
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
