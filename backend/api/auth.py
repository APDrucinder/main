from __future__ import annotations

import os
from uuid import UUID

from fastapi import Header, HTTPException, status

AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() == "true"
DEV_USER_ID = os.getenv("DEV_USER_ID")


def _parse_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid {field_name} format",
        ) from exc


async def get_current_user_id(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> UUID:
    """
    Temporary auth guard:
    - Production/default: requires trusted X-User-Id header.
    - Local/dev only (AUTH_REQUIRED=false): falls back to DEV_USER_ID.
    """
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
