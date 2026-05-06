from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.models import User

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() == "true"
DEV_USER_ID = os.getenv("DEV_USER_ID")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "apd_session")
SESSION_MAX_AGE_SECONDS = int(os.getenv("SESSION_MAX_AGE_SECONDS", "604800"))
SESSION_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret")
SESSION_SALT = os.getenv("SESSION_SALT", "apd-session")


def _parse_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid {field_name} format",
        ) from exc


def _session_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(SESSION_SECRET, salt=SESSION_SALT)


def create_session_token(user_id: UUID) -> str:
    return _session_serializer().dumps({"user_id": str(user_id)})


def read_session_token(token: str) -> UUID | None:
    try:
        payload = _session_serializer().loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None

    user_id = payload.get("user_id") if isinstance(payload, dict) else None
    if not user_id:
        return None
    try:
        return UUID(str(user_id))
    except ValueError:
        return None


def attach_session_cookie(response: Response, user_id: UUID) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(user_id),
        httponly=True,
        samesite="lax",
        secure=SESSION_SECURE,
        path="/",
        max_age=SESSION_MAX_AGE_SECONDS,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=SESSION_SECURE,
    )


async def _get_cookie_user_id(request: Request, db: AsyncSession) -> UUID | None:
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie_token:
        return None

    session_user_id = read_session_token(cookie_token)
    if not session_user_id:
        return None

    user = await db.get(User, session_user_id)
    if not user:
        return None

    return session_user_id


async def get_current_user_id(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> UUID:
    """
    Auth guard priority:
    1. Session cookie
    2. X-User-Id header (legacy/support)
    3. DEV_USER_ID fallback when AUTH_REQUIRED=false
    """
    cookie_user_id = await _get_cookie_user_id(request, db)
    if cookie_user_id:
        return cookie_user_id

    if x_user_id:
        return _parse_uuid(x_user_id, "X-User-Id")

    if not AUTH_REQUIRED and DEV_USER_ID:
        return _parse_uuid(DEV_USER_ID, "DEV_USER_ID")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing X-User-Id header",
    )


def assert_user_scope(current_user_id: UUID, target_user_id: UUID) -> None:
    if not AUTH_REQUIRED:
        return
    if current_user_id != target_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden for requested user scope",
        )
