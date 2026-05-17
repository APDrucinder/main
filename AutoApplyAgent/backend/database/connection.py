import os
import ssl
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
BACKEND_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"

# Load backend/.env last with override so repo-root placeholders cannot shadow
# the real backend runtime configuration.
load_dotenv(dotenv_path=ROOT_ENV_PATH, override=False)
load_dotenv(dotenv_path=BACKEND_ENV_PATH, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing from .env")

ssl_verify = os.getenv("DB_SSL_VERIFY", "true").lower() == "true"
ssl_context = ssl.create_default_context()
if not ssl_verify:
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
connect_timeout = float(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "4"))

connect_args: dict[str, object]
if DATABASE_URL.startswith("postgresql+"):
    connect_args = {"ssl": ssl_context, "timeout": connect_timeout}
elif DATABASE_URL.startswith("sqlite+"):
    # sqlite drivers (for local/dev) do not accept ssl arguments.
    connect_args = {"timeout": connect_timeout}
else:
    connect_args = {"timeout": connect_timeout}

engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    pool_pre_ping=True,
    connect_args=connect_args,
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
