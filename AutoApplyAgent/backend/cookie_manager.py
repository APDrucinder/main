"""
Cookie Manager — Session Cookie Capture & Reload
──────────────────────────────────────────────────
Launches a visible Playwright browser for each job platform so the user can
manually log in.  After the user confirms login, cookies are captured and
persisted as JSON files under ./cookies/users/<user_id>/<platform>_cookies.json.

A companion `load_cookies()` helper lets the AutoApplyBot inject saved cookies
into a fresh Playwright browser context, bypassing repeated manual logins.
Cookies are user-scoped by default so one user's LinkedIn session can never be
loaded for another user's auto-apply run.

Usage (CLI):
    python cookie_manager.py --user-id <uuid> linkedin naukri
    ALLOW_GLOBAL_PLATFORM_COOKIES=true python cookie_manager.py --global linkedin
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import BrowserContext, sync_playwright

# ─── Directory Setup ──────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
COOKIES_DIR = BASE_DIR / "cookies"
COOKIES_DIR.mkdir(exist_ok=True)
USER_COOKIES_DIR = COOKIES_DIR / "users"
USER_COOKIES_DIR.mkdir(exist_ok=True)

ALLOW_GLOBAL_PLATFORM_COOKIES = (
    os.getenv("ALLOW_GLOBAL_PLATFORM_COOKIES", "false").lower() == "true"
)

# ─── Supported Platforms ──────────────────────────────────────────────────────
# Each entry maps a platform key to its login URL.  Add more here as needed.

PLATFORM_LOGIN_URLS: Dict[str, str] = {
    "linkedin": "https://www.linkedin.com/login",
    "naukri": "https://www.naukri.com/nlogin/login",
    "indeed": "https://secure.indeed.com/auth",
    "internshala": "https://internshala.com/login",
    "glassdoor": "https://www.glassdoor.co.in/profile/login_input.htm",
    "foundit": "https://www.foundit.in/login",
}


# ─── Cookie File Helpers ──────────────────────────────────────────────────────

def _platform_key(platform: str) -> str:
    return platform.lower().strip()


def _safe_user_id(user_id: str) -> str:
    """Validate and normalize user ids used in cookie paths."""
    from uuid import UUID

    return str(UUID(str(user_id)))


def _user_cookie_dir(user_id: str, *, create: bool = False) -> Path:
    user_dir = USER_COOKIES_DIR / _safe_user_id(user_id)
    if create:
        user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _cookie_path(
    platform: str,
    *,
    user_id: str | None = None,
    create_parent: bool = False,
) -> Path:
    """Return the canonical path for a platform cookie file."""
    filename = f"{_platform_key(platform)}_cookies.json"
    if user_id:
        return _user_cookie_dir(user_id, create=create_parent) / filename
    return COOKIES_DIR / filename


def _resolve_cookie_path(platform: str, user_id: str | None) -> Path | None:
    """
    Resolve the cookie file that may be loaded for this call.

    User-scoped calls never fall back to the legacy global cookie file. A
    userless call may read the legacy global file only when explicitly enabled
    via ALLOW_GLOBAL_PLATFORM_COOKIES=true.
    """
    if user_id:
        return _cookie_path(platform, user_id=user_id)
    if ALLOW_GLOBAL_PLATFORM_COOKIES:
        return _cookie_path(platform)
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Core: Capture Cookies ────────────────────────────────────────────────────

def capture_cookies(
    platforms: Optional[List[str]] = None,
    *,
    slow_mo: int = 50,
    user_id: str | None = None,
) -> Dict[str, bool]:
    """
    Launch a visible browser for each platform, let the user log in, then
    capture & save session cookies.

    Parameters
    ----------
    platforms : list[str] | None
        Platform keys to capture.  ``None`` means all platforms in
        ``PLATFORM_LOGIN_URLS``.
    slow_mo : int
        Playwright ``slow_mo`` value (ms).  Gives a more human-like feel.

    Returns
    -------
    dict[str, bool]
        Mapping of platform → whether capture succeeded.
    """
    if not user_id and not ALLOW_GLOBAL_PLATFORM_COOKIES:
        raise ValueError(
            "user_id is required for cookie capture. Use --user-id <uuid>, or set "
            "ALLOW_GLOBAL_PLATFORM_COOKIES=true and pass --global for a legacy local-only capture."
        )

    targets = platforms or list(PLATFORM_LOGIN_URLS.keys())
    results: Dict[str, bool] = {}

    for platform in targets:
        platform_key = _platform_key(platform)
        login_url = PLATFORM_LOGIN_URLS.get(platform_key)
        if not login_url:
            print(f"\n⚠  Unknown platform '{platform}'. Skipping.")
            print(f"   Supported: {', '.join(PLATFORM_LOGIN_URLS.keys())}")
            results[platform] = False
            continue

        print(f"\n{'━' * 60}")
        print(f"  🌐  {platform.upper()}")
        print(f"{'━' * 60}")
        print(f"  Opening {login_url} …")

        try:
            success = _capture_single_platform(platform_key, login_url, slow_mo, user_id=user_id)
            results[platform_key] = success
        except KeyboardInterrupt:
            print("\n  ⏹  Skipped by user.")
            results[platform_key] = False
        except Exception as exc:
            print(f"  ❌  Error capturing {platform}: {exc}")
            results[platform_key] = False

    # ── Summary ──────────────────────────────────────────────
    print(f"\n{'━' * 60}")
    print("  📋  CAPTURE SUMMARY")
    print(f"{'━' * 60}")
    for plat, ok in results.items():
        icon = "✅" if ok else "❌"
        path = _cookie_path(plat, user_id=user_id) if ok else "—"
        print(f"  {icon}  {plat:<15}  {path}")
    print()

    return results


def _capture_single_platform(
    platform: str,
    login_url: str,
    slow_mo: int,
    *,
    user_id: str | None,
) -> bool:
    """Open browser, wait for user login, capture cookies, close browser."""

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel="chrome",
            headless=False,
            slow_mo=slow_mo,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            print(f"  ⚠  Could not load login page: {exc}")
            print("  The browser is still open — navigate manually if needed.")

        # ── Wait for user confirmation ────────────────────────
        print()
        print(f"  👉  Log in to {platform.upper()} in the browser window.")
        print("  ────────────────────────────────────────────────")
        input("  ✋  Press ENTER here after you have logged in … ")

        # ── Capture cookies ───────────────────────────────────
        cookies = context.cookies()
        if not cookies:
            print("  ⚠  No cookies found.  Did you log in successfully?")
            browser.close()
            return False

        # Build metadata-enriched cookie payload
        user_agent_str = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
        payload = {
            "platform": platform,
            "user_id": _safe_user_id(user_id) if user_id else None,
            "captured_at": _now_iso(),
            "cookie_count": len(cookies),
            "user_agent": user_agent_str,
            "cookies": cookies,
        }

        cookie_file = _cookie_path(platform, user_id=user_id, create_parent=True)
        cookie_file.write_text(json.dumps(payload, indent=2, default=str))
        print(f"  💾  Saved {len(cookies)} cookies → {cookie_file}")

        browser.close()
        return True


# ─── Load Cookies Into Playwright Context ─────────────────────────────────────

class CookieStatus:
    """Result of a ``load_cookies`` call."""

    def __init__(
        self,
        *,
        loaded: bool,
        platform: str,
        cookie_count: int = 0,
        captured_at: Optional[str] = None,
        expired: bool = False,
        message: str = "",
    ):
        self.loaded = loaded
        self.platform = platform
        self.cookie_count = cookie_count
        self.captured_at = captured_at
        self.expired = expired
        self.message = message
        self.user_agent = None

    def __repr__(self) -> str:
        status = "OK" if self.loaded else ("EXPIRED" if self.expired else "MISSING")
        return f"<CookieStatus {self.platform} {status} cookies={self.cookie_count}>"


def load_cookies(
    platform: str,
    context: BrowserContext,
    *,
    user_id: str | None = None,
) -> CookieStatus:
    """
    Load previously captured cookies for *platform* into a Playwright
    ``BrowserContext``.

    Parameters
    ----------
    platform : str
        Platform key (e.g. ``"linkedin"``).
    context : BrowserContext
        The Playwright browser context to inject cookies into.

    Returns
    -------
    CookieStatus
        Contains ``loaded=True`` on success; on failure ``expired=True`` if
        the cookies exist but have expired, and a human-readable ``message``.
    """
    try:
        cookie_file = _resolve_cookie_path(platform, user_id)
    except ValueError as exc:
        return CookieStatus(
            loaded=False,
            platform=platform,
            message=f"Invalid user_id for platform cookie loading: {exc}",
        )

    if cookie_file is None:
        return CookieStatus(
            loaded=False,
            platform=platform,
            message=(
                "No user_id was provided for platform cookie loading. "
                "Refusing to load legacy global cookies unless "
                "ALLOW_GLOBAL_PLATFORM_COOKIES=true."
            ),
        )

    # ── File missing ──────────────────────────────────────────
    if not cookie_file.exists():
        scope = f"user {user_id}" if user_id else "legacy global"
        return CookieStatus(
            loaded=False,
            platform=platform,
            message=(
                f"No {scope} cookie file found at {cookie_file}. "
                f"Run `python cookie_manager.py --user-id <uuid> {platform}` to capture."
            ),
        )

    # ── Parse cookie file ─────────────────────────────────────
    try:
        payload = json.loads(cookie_file.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return CookieStatus(
            loaded=False,
            platform=platform,
            message=f"Corrupt cookie file: {exc}",
        )

    cookies: List[Dict[str, Any]] = payload.get("cookies", [])
    captured_at = payload.get("captured_at")

    if not cookies:
        return CookieStatus(
            loaded=False,
            platform=platform,
            captured_at=captured_at,
            message="Cookie file exists but contains no cookies.",
        )

    # ── Expiry check ──────────────────────────────────────────
    now_epoch = time.time()
    valid_cookies: List[Dict[str, Any]] = []
    expired_count = 0

    for cookie in cookies:
        expires = cookie.get("expires", -1)
        # expires == -1 means session cookie (no explicit expiry) — keep it
        if expires > 0 and expires < now_epoch:
            expired_count += 1
            continue
        valid_cookies.append(cookie)

    if not valid_cookies:
        return CookieStatus(
            loaded=False,
            platform=platform,
            cookie_count=0,
            captured_at=captured_at,
            expired=True,
            message=(
                f"All {len(cookies)} cookies have expired.  "
                f"Re-capture with: python cookie_manager.py --user-id <uuid> {platform}"
            ),
        )

    # ── Inject into context ───────────────────────────────────
    try:
        context.add_cookies(valid_cookies)
    except Exception as exc:
        return CookieStatus(
            loaded=False,
            platform=platform,
            captured_at=captured_at,
            message=f"Failed to inject cookies: {exc}",
        )

    msg_parts = [f"Loaded {len(valid_cookies)} cookies for {platform}."]
    if expired_count:
        msg_parts.append(f"({expired_count} expired cookies skipped)")

    status_obj = CookieStatus(
        loaded=True,
        platform=platform,
        cookie_count=len(valid_cookies),
        captured_at=captured_at,
        expired=False,
        message=" ".join(msg_parts),
    )
    status_obj.user_agent = payload.get("user_agent")
    return status_obj


# ─── Utilities ────────────────────────────────────────────────────────────────

def get_cookie_user_agent(platform: str, *, user_id: str | None = None) -> Optional[str]:
    """Retrieve the User-Agent string used during cookie capture for a platform."""
    try:
        cookie_file = _resolve_cookie_path(platform, user_id)
    except ValueError:
        return None
    if cookie_file is None:
        return None
    if not cookie_file.exists():
        return None
    try:
        payload = json.loads(cookie_file.read_text())
        return payload.get("user_agent")
    except Exception:
        return None

def list_saved_cookies(*, user_id: str | None = None) -> Dict[str, Dict[str, Any]]:
    """
    Return metadata for all saved cookie files.

    Returns
    -------
    dict[str, dict]
        ``{ platform: { path, captured_at, cookie_count, has_expired } }``
    """
    result: Dict[str, Dict[str, Any]] = {}
    for platform in PLATFORM_LOGIN_URLS:
        try:
            cookie_file = _resolve_cookie_path(platform, user_id)
        except ValueError:
            continue
        if cookie_file is None:
            continue
        if not cookie_file.exists():
            continue
        try:
            payload = json.loads(cookie_file.read_text())
            cookies = payload.get("cookies", [])
            now = time.time()
            all_expired = all(
                (c.get("expires", -1) > 0 and c["expires"] < now)
                for c in cookies
            ) if cookies else True
            result[platform] = {
                "path": str(cookie_file),
                "user_id": _safe_user_id(user_id) if user_id else payload.get("user_id"),
                "captured_at": payload.get("captured_at"),
                "cookie_count": len(cookies),
                "all_expired": all_expired,
            }
        except Exception:
            result[platform] = {
                "path": str(cookie_file),
                "user_id": _safe_user_id(user_id) if user_id else None,
                "captured_at": None,
                "cookie_count": 0,
                "all_expired": True,
            }
    return result


def delete_cookies(platform: str, *, user_id: str | None = None) -> bool:
    """Delete the cookie file for a given platform."""
    try:
        cookie_file = _resolve_cookie_path(platform, user_id)
    except ValueError:
        return False
    if cookie_file is None:
        return False
    if cookie_file.exists():
        cookie_file.unlink()
        return True
    return False


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

def _cli_main() -> None:
    """CLI entry point with optional platform arguments."""

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          🍪  CelerixAi Cookie Capture Tool              ║")
    print("║     Session cookie manager for job platform logins      ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # Show saved cookies status
    raw_args = sys.argv[1:]
    user_id = None
    use_global = False

    if "--user-id" in raw_args:
        idx = raw_args.index("--user-id")
        try:
            user_id = raw_args[idx + 1]
        except IndexError:
            print("  ❌  --user-id requires a UUID value")
            return
        del raw_args[idx:idx + 2]

    if "--global" in raw_args:
        raw_args.remove("--global")
        use_global = True
        if not ALLOW_GLOBAL_PLATFORM_COOKIES:
            print("  ❌  --global requires ALLOW_GLOBAL_PLATFORM_COOKIES=true")
            return

    if not user_id and not use_global and "--help" not in raw_args and "-h" not in raw_args:
        print("  ❌  Cookie capture/list/delete now requires --user-id <uuid>.")
        print("      This prevents one user's platform session from being reused for another user.")
        print("      For legacy local-only global cookies, set ALLOW_GLOBAL_PLATFORM_COOKIES=true and pass --global.")
        print()
        return

    saved = list_saved_cookies(user_id=user_id)
    if saved:
        print("\n  📂  Existing cookie files:")
        for plat, info in saved.items():
            status = "⚠ expired" if info["all_expired"] else "✅ valid"
            print(f"      {plat:<15}  {info['cookie_count']:>3} cookies  {status}  ({info['captured_at'] or '?'})")
    else:
        print("\n  📂  No saved cookies found.")

    # Determine which platforms to capture
    if raw_args:
        if raw_args[0] in ("--help", "-h"):
            print(f"\n  Usage: python cookie_manager.py --user-id <uuid> [platform ...]")
            print(f"  Platforms: {', '.join(PLATFORM_LOGIN_URLS.keys())}")
            print(f"  Options:")
            print(f"    --user-id  User UUID whose platform session should be captured")
            print(f"    --list     Show saved cookie status")
            print(f"    --delete   Delete cookies for a platform")
            print(f"    --global   Use legacy global cookies only when ALLOW_GLOBAL_PLATFORM_COOKIES=true")
            print()
            return

        if raw_args[0] == "--list":
            # Already printed above
            print()
            return

        if raw_args[0] == "--delete":
            for plat in raw_args[1:]:
                if delete_cookies(plat, user_id=user_id):
                    print(f"  🗑  Deleted cookies for {plat}")
                else:
                    print(f"  ⚠  No cookies found for {plat}")
            print()
            return

        platforms = [p.lower() for p in raw_args]
    else:
        print(f"\n  Supported platforms: {', '.join(PLATFORM_LOGIN_URLS.keys())}")
        platforms = list(PLATFORM_LOGIN_URLS.keys())

    print(f"\n  🎯  Capturing cookies for: {', '.join(platforms)}")
    print("  A browser window will open for each platform.")
    print("  Log in manually, then return here and press ENTER.\n")

    capture_cookies(platforms, user_id=user_id)


if __name__ == "__main__":
    _cli_main()
