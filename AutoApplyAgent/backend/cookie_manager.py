"""
Cookie Manager — Session Cookie Capture & Reload
──────────────────────────────────────────────────
Launches a visible Playwright browser for each job platform so the user can
manually log in.  After the user confirms login, cookies are captured and
persisted as JSON files under ./cookies/<platform>_cookies.json.

A companion `load_cookies()` helper lets the AutoApplyBot inject saved cookies
into a fresh Playwright browser context, bypassing repeated manual logins.

Usage (CLI):
    python cookie_manager.py                    # all platforms
    python cookie_manager.py linkedin naukri     # specific platforms only
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

def _cookie_path(platform: str) -> Path:
    """Return the canonical path for a platform's cookie file."""
    return COOKIES_DIR / f"{platform.lower()}_cookies.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Core: Capture Cookies ────────────────────────────────────────────────────

def capture_cookies(
    platforms: Optional[List[str]] = None,
    *,
    slow_mo: int = 50,
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
    targets = platforms or list(PLATFORM_LOGIN_URLS.keys())
    results: Dict[str, bool] = {}

    for platform in targets:
        login_url = PLATFORM_LOGIN_URLS.get(platform.lower())
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
            success = _capture_single_platform(platform, login_url, slow_mo)
            results[platform] = success
        except KeyboardInterrupt:
            print("\n  ⏹  Skipped by user.")
            results[platform] = False
        except Exception as exc:
            print(f"  ❌  Error capturing {platform}: {exc}")
            results[platform] = False

    # ── Summary ──────────────────────────────────────────────
    print(f"\n{'━' * 60}")
    print("  📋  CAPTURE SUMMARY")
    print(f"{'━' * 60}")
    for plat, ok in results.items():
        icon = "✅" if ok else "❌"
        path = _cookie_path(plat) if ok else "—"
        print(f"  {icon}  {plat:<15}  {path}")
    print()

    return results


def _capture_single_platform(platform: str, login_url: str, slow_mo: int) -> bool:
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
        payload = {
            "platform": platform,
            "captured_at": _now_iso(),
            "cookie_count": len(cookies),
            "cookies": cookies,
        }

        cookie_file = _cookie_path(platform)
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

    def __repr__(self) -> str:
        status = "OK" if self.loaded else ("EXPIRED" if self.expired else "MISSING")
        return f"<CookieStatus {self.platform} {status} cookies={self.cookie_count}>"


def load_cookies(platform: str, context: BrowserContext) -> CookieStatus:
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
    cookie_file = _cookie_path(platform)

    # ── File missing ──────────────────────────────────────────
    if not cookie_file.exists():
        return CookieStatus(
            loaded=False,
            platform=platform,
            message=f"No cookie file found at {cookie_file}. Run `python cookie_manager.py {platform}` to capture.",
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
                f"Re-capture with: python cookie_manager.py {platform}"
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

    return CookieStatus(
        loaded=True,
        platform=platform,
        cookie_count=len(valid_cookies),
        captured_at=captured_at,
        expired=False,
        message=" ".join(msg_parts),
    )


# ─── Utilities ────────────────────────────────────────────────────────────────

def list_saved_cookies() -> Dict[str, Dict[str, Any]]:
    """
    Return metadata for all saved cookie files.

    Returns
    -------
    dict[str, dict]
        ``{ platform: { path, captured_at, cookie_count, has_expired } }``
    """
    result: Dict[str, Dict[str, Any]] = {}
    for platform in PLATFORM_LOGIN_URLS:
        cookie_file = _cookie_path(platform)
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
                "captured_at": payload.get("captured_at"),
                "cookie_count": len(cookies),
                "all_expired": all_expired,
            }
        except Exception:
            result[platform] = {
                "path": str(cookie_file),
                "captured_at": None,
                "cookie_count": 0,
                "all_expired": True,
            }
    return result


def delete_cookies(platform: str) -> bool:
    """Delete the cookie file for a given platform."""
    cookie_file = _cookie_path(platform)
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
    saved = list_saved_cookies()
    if saved:
        print("\n  📂  Existing cookie files:")
        for plat, info in saved.items():
            status = "⚠ expired" if info["all_expired"] else "✅ valid"
            print(f"      {plat:<15}  {info['cookie_count']:>3} cookies  {status}  ({info['captured_at'] or '?'})")
    else:
        print("\n  📂  No saved cookies found.")

    # Determine which platforms to capture
    if len(sys.argv) > 1:
        if sys.argv[1] in ("--help", "-h"):
            print(f"\n  Usage: python cookie_manager.py [platform ...]")
            print(f"  Platforms: {', '.join(PLATFORM_LOGIN_URLS.keys())}")
            print(f"  Options:")
            print(f"    --list     Show saved cookie status")
            print(f"    --delete   Delete cookies for a platform")
            print()
            return

        if sys.argv[1] == "--list":
            # Already printed above
            print()
            return

        if sys.argv[1] == "--delete":
            for plat in sys.argv[2:]:
                if delete_cookies(plat):
                    print(f"  🗑  Deleted cookies for {plat}")
                else:
                    print(f"  ⚠  No cookies found for {plat}")
            print()
            return

        platforms = [p.lower() for p in sys.argv[1:]]
    else:
        print(f"\n  Supported platforms: {', '.join(PLATFORM_LOGIN_URLS.keys())}")
        platforms = list(PLATFORM_LOGIN_URLS.keys())

    print(f"\n  🎯  Capturing cookies for: {', '.join(platforms)}")
    print("  A browser window will open for each platform.")
    print("  Log in manually, then return here and press ENTER.\n")

    capture_cookies(platforms)


if __name__ == "__main__":
    _cli_main()
