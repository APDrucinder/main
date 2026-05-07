from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import jwt
from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from jwt import InvalidTokenError, PyJWKClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
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
CLERK_ISSUER = os.getenv("CLERK_ISSUER", "").rstrip("/")

_jwks_clients: dict[str, PyJWKClient] = {}


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


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def _jwks_client(issuer: str) -> PyJWKClient:
    if issuer not in _jwks_clients:
        _jwks_clients[issuer] = PyJWKClient(f"{issuer}/.well-known/jwks.json")
    return _jwks_clients[issuer]


def _verify_clerk_token(token: str) -> dict[str, Any]:
    try:
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
        issuer = str(unverified_claims.get("iss", "")).rstrip("/")
        if not issuer:
            raise InvalidTokenError("Missing issuer")
        if CLERK_ISSUER and issuer != CLERK_ISSUER:
            raise InvalidTokenError("Invalid issuer")

        signing_key = _jwks_client(issuer).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Clerk session",
        ) from exc


def _claim_email(claims: dict[str, Any]) -> str:
    for key in ("email", "primary_email_address", "email_address"):
        value = claims.get(key)
        if isinstance(value, str) and value:
            return value.lower()
    return f"{claims['sub']}@clerk.local"


async def _fetch_or_create_clerk_user(db: AsyncSession, claims: dict[str, Any]) -> UUID:
    clerk_id = str(claims["sub"])
    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()
    if user:
        return user.id

    email = _claim_email(claims)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        user.clerk_id = clerk_id
        await db.flush()
        return user.id

    user = User(
        id=uuid.uuid4(),
        clerk_id=clerk_id,
        email=email,
        subscription_tier="free",
    )
    db.add(user)
    await db.flush()
    return user.id


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

    try:
        user = await db.get(User, session_user_id)
    except (TimeoutError, SQLAlchemyError):
        return None
    if not user:
        return None

    return session_user_id


async def get_current_user_id(
    request: Request,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> UUID:
    """
    Auth guard priority:
    1. Clerk bearer token
    2. Legacy local session cookie
    3. X-User-Id header (legacy/support)
    4. DEV_USER_ID fallback when AUTH_REQUIRED=false
    """
    token = _bearer_token(authorization)
    if token:
        claims = _verify_clerk_token(token)
        try:
            return await _fetch_or_create_clerk_user(db, claims)
        except (TimeoutError, SQLAlchemyError):
            if not AUTH_REQUIRED and DEV_USER_ID:
                return _parse_uuid(DEV_USER_ID, "DEV_USER_ID")
            raise

    cookie_user_id = await _get_cookie_user_id(request, db)
    if cookie_user_id:
        return cookie_user_id

    if x_user_id and not AUTH_REQUIRED:
        result = await db.execute(select(User).where(User.clerk_id == x_user_id))
        user = result.scalar_one_or_none()
        if user:
            return user.id
        
        # If not found but DEV_USER_ID fallback is allowed
        if not AUTH_REQUIRED and DEV_USER_ID:
            return _parse_uuid(DEV_USER_ID, "DEV_USER_ID")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found for X-User-Id",
        )

    if not AUTH_REQUIRED and DEV_USER_ID:
        return _parse_uuid(DEV_USER_ID, "DEV_USER_ID")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing Clerk session",
    )


def assert_user_scope(current_user_id: UUID, target_user_id: UUID) -> None:
    if not AUTH_REQUIRED:
        return
    if current_user_id != target_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden for requested user scope",
        )
