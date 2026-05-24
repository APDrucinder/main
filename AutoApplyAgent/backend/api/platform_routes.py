from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends

from api.auth import get_current_user_id
from cookie_manager import PLATFORM_LOGIN_URLS, list_saved_cookies

router = APIRouter(prefix="/platform-sessions", tags=["platform-sessions"])

LIVE_REQUIRED_PLATFORMS = {"linkedin"}


def _status_for(platform: str, saved: dict[str, dict]) -> dict[str, object]:
    info = saved.get(platform)
    if not info:
        state = "missing"
        message = (
            f"No user-specific {platform} session is saved. Capture it on the deployment "
            f"machine with: python cookie_manager.py --user-id <this-user-uuid> {platform}"
        )
    elif info.get("all_expired"):
        state = "expired"
        message = (
            f"This user's saved {platform} session cookies are expired. Recapture on the "
            f"deployment machine before live auto-apply."
        )
    else:
        state = "available"
        message = (
            f"A user-specific {platform} session capture exists. Live runs will still stop "
            f"if the platform opens signed out."
        )

    return {
        "platform": platform,
        "state": state,
        "required_for_live": platform in LIVE_REQUIRED_PLATFORMS,
        "cookie_count": info.get("cookie_count", 0) if info else 0,
        "captured_at": info.get("captured_at") if info else None,
        "user_scoped": bool(info and info.get("user_id")),
        "message": message,
    }


@router.get("")
async def platform_sessions(current_user_id: UUID = Depends(get_current_user_id)):
    saved = list_saved_cookies(user_id=str(current_user_id))
    platforms = sorted(set(PLATFORM_LOGIN_URLS) | LIVE_REQUIRED_PLATFORMS)

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "user_id": str(current_user_id),
        "sessions": [_status_for(platform, saved) for platform in platforms],
    }
