from __future__ import annotations

import asyncio
import os
import random
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

import requests
from pydantic import BaseModel, ConfigDict

from agents.ats_handlers import (
    DarwinboxHandler,
    GreenhouseHandler,
    IndeedHandler,
    KekaHandler,
    LinkedInHandler,
    NaukriHandler,
    WorkdayHandler,
    ZohoHandler,
)
from cookie_manager import load_cookies
from shared.logger import logger


USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]


class ApplyStatus(str, Enum):
    SUCCESS = "applied"
    CAPTCHA = "captcha"
    NO_CREDENTIALS = "no_credentials"
    LOGIN_FAILED = "login_failed"
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    FAILED = "failed"


class PlatformCredentials(BaseModel):
    model_config = ConfigDict(extra="allow")

    workday_email: Optional[str] = None
    workday_password: Optional[str] = None
    linkedin_email: Optional[str] = None
    linkedin_password: Optional[str] = None
    indeed_email: Optional[str] = None
    indeed_password: Optional[str] = None
    naukri_email: Optional[str] = None
    naukri_password: Optional[str] = None


class ApplyResult(BaseModel):
    status: ApplyStatus
    platform: str
    reason: Optional[str] = None


class AutoApplyBot:
    """Routes a job URL to a platform handler and executes the apply flow."""

    _ROUTING_TABLE = {
        "myworkdayjobs.com": ("workday", WorkdayHandler),
        "greenhouse.io": ("greenhouse", GreenhouseHandler),
        "darwinbox": ("darwinbox", DarwinboxHandler),
        "keka.com": ("keka", KekaHandler),
        "zoho.com/recruit": ("zoho", ZohoHandler),
        "naukri.com": ("naukri", NaukriHandler),
        "indeed.com": ("indeed", IndeedHandler),
        "linkedin.com": ("linkedin", LinkedInHandler),
    }

    _CREDENTIAL_REQUIRED_PLATFORMS = {"workday"}

    def __init__(
        self,
        *,
        headless: bool = True,
        debug: bool = False,
        dry_run: bool = False,
        navigation_timeout_ms: int = 45000,
        browser_engine: str = "chromium",
    ):
        self.headless = headless
        self.debug = debug
        self.dry_run = dry_run
        self.navigation_timeout_ms = navigation_timeout_ms
        self.browser_engine = browser_engine

    async def apply(
        self,
        *,
        job_url: str,
        user_data: dict[str, Any],
        resume_url: str,
        credentials: PlatformCredentials | None,
    ) -> ApplyResult:
        return await asyncio.to_thread(
            self._apply_sync,
            job_url,
            user_data,
            resume_url,
            credentials,
        )

    def _apply_sync(
        self,
        job_url: str,
        user_data: dict[str, Any],
        resume_url: str,
        credentials: PlatformCredentials | None,
    ) -> ApplyResult:
        final_url = self._resolve_external_redirects(job_url)
        final_url = self._normalize_platform_url(final_url)
        platform, handler_class = self._resolve_handler(final_url)

        if not handler_class:
            return ApplyResult(
                status=ApplyStatus.UNSUPPORTED_PLATFORM,
                platform="unknown",
                reason=f"No ATS handler for URL: {final_url}",
            )

        if platform in self._CREDENTIAL_REQUIRED_PLATFORMS and not self._has_platform_credentials(
            platform, credentials
        ):
            return ApplyResult(
                status=ApplyStatus.NO_CREDENTIALS,
                platform=platform,
                reason=f"{platform} credentials missing",
            )

        resume_path: Optional[str] = None
        browser = None
        context = None

        try:
            resume_path = self._materialize_resume(resume_url)
            enriched_user_data = self._build_user_data(user_data, resume_path, credentials)

            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=self.headless)
                context = browser.new_context(user_agent=random.choice(USER_AGENTS))

                # Inject saved session cookies for this platform
                cookie_status = load_cookies(platform, context)
                if cookie_status.loaded:
                    logger.info(
                        "Session cookies injected",
                        platform=platform,
                        cookie_count=cookie_status.cookie_count,
                    )
                elif cookie_status.expired:
                    logger.warning(
                        "Session cookies expired — re-capture needed",
                        platform=platform,
                        message=cookie_status.message,
                    )
                else:
                    logger.debug(
                        "No saved cookies for platform",
                        platform=platform,
                        message=cookie_status.message,
                    )
                    if platform == "linkedin":
                        return ApplyResult(
                            status=ApplyStatus.LOGIN_FAILED,
                            platform=platform,
                            reason=cookie_status.message or "LinkedIn session cookies are missing.",
                        )

                page = context.new_page()
                page.goto(final_url, wait_until="domcontentloaded", timeout=self.navigation_timeout_ms)

                if self._login_required_visible(page, platform):
                    return ApplyResult(
                        status=ApplyStatus.LOGIN_FAILED,
                        platform=platform,
                        reason=f"{platform} opened a sign-in page. Reconnect this platform before auto-apply.",
                    )

                handler = handler_class(page=page, user_data=enriched_user_data, dry_run=self.dry_run)
                success = handler.execute_apply_flow()

                if success:
                    return ApplyResult(status=ApplyStatus.SUCCESS, platform=platform)

                return ApplyResult(
                    status=ApplyStatus.FAILED,
                    platform=platform,
                    reason="Handler reported unsuccessful apply flow",
                )

        except Exception as exc:
            logger.error(
                "Auto-apply failed",
                platform=platform,
                url=final_url,
                error=str(exc),
            )
            return ApplyResult(status=ApplyStatus.FAILED, platform=platform, reason=str(exc))
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception:
                    pass
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass

            if resume_path and resume_path.startswith(tempfile.gettempdir()):
                try:
                    Path(resume_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def _resolve_external_redirects(self, url: str) -> str:
        try:
            response = requests.head(
                url,
                allow_redirects=True,
                timeout=15,
                headers={"User-Agent": random.choice(USER_AGENTS)},
            )
            if response.url:
                return response.url
        except requests.RequestException as exc:
            logger.warning("Redirect resolution failed", url=url, error=str(exc))
        return url

    def _normalize_platform_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.hostname and parsed.hostname.endswith("linkedin.com") and parsed.hostname != "www.linkedin.com":
            return urlunparse(parsed._replace(netloc="www.linkedin.com"))
        return url

    def _resolve_handler(self, url: str):
        url_lower = url.lower()
        for signature, handler in self._ROUTING_TABLE.items():
            if signature in url_lower:
                return handler
        return "unknown", None

    def _login_required_visible(self, page, platform: str) -> bool:
        if platform != "linkedin":
            return False
        try:
            page_text = page.locator("body").inner_text(timeout=5000).lower()
        except Exception:
            page_text = page.content().lower()

        signed_out_markers = (
            "sign in to see",
            "sign in with email",
            "continue with google",
            "new to linkedin?",
        )
        has_signed_out_copy = any(marker in page_text for marker in signed_out_markers)
        has_signed_in_nav = "my network" in page_text and "messaging" in page_text and "notifications" in page_text
        return has_signed_out_copy and not has_signed_in_nav

    def _has_platform_credentials(
        self,
        platform: str,
        credentials: PlatformCredentials | None,
    ) -> bool:
        if not credentials:
            return False
        if platform == "workday":
            return bool(credentials.workday_email and credentials.workday_password)
        return True

    def _build_user_data(
        self,
        base_user_data: dict[str, Any],
        resume_path: str,
        credentials: PlatformCredentials | None,
    ) -> dict[str, Any]:
        user_data = dict(base_user_data)
        user_data["resume_path"] = resume_path

        if credentials:
            user_data.update(credentials.model_dump(exclude_none=True))
            # Handler compatibility aliases
            if credentials.workday_password:
                user_data.setdefault("workday_password", credentials.workday_password)
            if credentials.workday_email:
                user_data.setdefault("workday_email", credentials.workday_email)

        return user_data

    def _materialize_resume(self, resume_source: str) -> str:
        if not resume_source:
            raise ValueError("resume_url is required for auto-apply")

        parsed = urlparse(resume_source)
        if parsed.scheme in {"http", "https"}:
            return self._download_resume(resume_source)

        path = Path(resume_source).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Resume file not found: {path}")
        return str(path)

    def _download_resume(self, url: str) -> str:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        suffix = Path(urlparse(url).path).suffix or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(response.content)
            return temp_file.name


async def auto_apply(job, resume_path: str) -> dict[str, Any]:
    """Backward-compatible helper used by older retry wrappers."""
    bot = AutoApplyBot(headless=True, debug=False, dry_run=False)
    result = await bot.apply(
        job_url=job.apply_url,
        user_data={},
        resume_url=resume_path,
        credentials=None,
    )
    return {
        "success": result.status == ApplyStatus.SUCCESS,
        "reason": None if result.status == ApplyStatus.SUCCESS else result.reason,
        "status": result.status.value,
        "platform": result.platform,
        "job_url": job.apply_url,
        "manual_apply_url": job.apply_url,
    }
