import logging
import requests
import os
import sys
import time
import random
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse
from playwright.sync_api import Page

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database.storage import save_to_manual_queue
from shared.logger import logger
from ats_handlers import (
    WorkdayHandler,
    GreenhouseHandler,
    DarwinboxHandler,
    KekaHandler,
    ZohoHandler,
    NaukriHandler,
    IndeedHandler,
    LinkedInHandler
)

# ─── Constants ────────────────────────────────────────────────
MAX_APPLICATIONS_PER_DAY = 30
MIN_GAP_BETWEEN_APPLICATIONS_MINUTES = 10
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 30

# ─── Proxy Pool ───────────────────────────────────────────────
# Add your proxies here in format: "http://user:pass@host:port"
PROXY_LIST = [
    os.getenv("PROXY_1", ""),
    os.getenv("PROXY_2", ""),
    os.getenv("PROXY_3", ""),
]
PROXY_LIST = [p for p in PROXY_LIST if p]  # Remove empty ones

# ─── User Agent Pool ──────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
]

# ─── In-memory rate limit tracker ─────────────────────────────
# Format: { user_id: {"count": int, "last_applied": datetime, "date": date} }
_application_tracker: dict = {}


class RateLimitExceeded(Exception):
    pass


class AutoApplier:
    """
    Routes job URLs to the correct ATS handler.
    Includes: proxy rotation, user agent rotation, rate limiting,
    random scroll behaviour, retry logic.
    """

    def __init__(self, page: Page, user_data: dict, dry_run: bool = False):
        self.page = page
        self.user_data = user_data
        self.dry_run = dry_run
        self._proxy_index = 0

        self.routing_table = {
            "myworkdayjobs.com": WorkdayHandler,
            "greenhouse.io": GreenhouseHandler,
            "darwinbox.": DarwinboxHandler,
            "keka.com": KekaHandler,
            "zoho.com/recruit": ZohoHandler,
            "naukri.com": NaukriHandler,
            "indeed.com": IndeedHandler,
            "linkedin.com": LinkedInHandler,
        }

    # ─── Rate Limiting ────────────────────────────────────────

    def _check_rate_limits(self, user_id: str) -> None:
        """
        Enforces:
        - Max 30 applications per day per user
        - Min 10 minute gap between applications
        Raises RateLimitExceeded if either limit is hit.
        """
        today = datetime.utcnow().date()
        tracker = _application_tracker.get(user_id)

        if tracker:
            # Reset count if it's a new day
            if tracker["date"] != today:
                _application_tracker[user_id] = {
                    "count": 0,
                    "last_applied": None,
                    "date": today
                }
                tracker = _application_tracker[user_id]

            # Check daily limit
            if tracker["count"] >= MAX_APPLICATIONS_PER_DAY:
                raise RateLimitExceeded(
                    f"Daily limit of {MAX_APPLICATIONS_PER_DAY} applications reached for user {user_id}"
                )

            # Check minimum gap
            if tracker["last_applied"]:
                elapsed = datetime.utcnow() - tracker["last_applied"]
                min_gap = timedelta(minutes=MIN_GAP_BETWEEN_APPLICATIONS_MINUTES)
                if elapsed < min_gap:
                    wait_seconds = (min_gap - elapsed).seconds
                    raise RateLimitExceeded(
                        f"Too soon. Wait {wait_seconds // 60}m {wait_seconds % 60}s before next application."
                    )
        else:
            _application_tracker[user_id] = {
                "count": 0,
                "last_applied": None,
                "date": today
            }

    def _record_application(self, user_id: str) -> None:
        """Increment counter and update last_applied timestamp."""
        tracker = _application_tracker.setdefault(user_id, {
            "count": 0,
            "last_applied": None,
            "date": datetime.utcnow().date()
        })
        tracker["count"] += 1
        tracker["last_applied"] = datetime.utcnow()
        logger.info(
            "Application recorded",
            user_id=user_id,
            count=tracker["count"],
            limit=MAX_APPLICATIONS_PER_DAY
        )

    # ─── Proxy Rotation ───────────────────────────────────────

    def _get_next_proxy(self) -> Optional[str]:
        """Round-robin through proxy list. Returns None if no proxies configured."""
        if not PROXY_LIST:
            return None
        proxy = PROXY_LIST[self._proxy_index % len(PROXY_LIST)]
        self._proxy_index += 1
        logger.debug("Using proxy", proxy=proxy.split("@")[-1])  # Log host only, not credentials
        return proxy

    def _resolve_external_redirects(self, url: str) -> str:
        """Unroll tracking URLs to find actual ATS domain."""
        proxy = self._get_next_proxy()
        proxies = {"http": proxy, "https": proxy} if proxy else None

        try:
            response = requests.head(
                url,
                allow_redirects=True,
                timeout=10,
                proxies=proxies,
                headers={"User-Agent": random.choice(USER_AGENTS)}
            )
            return response.url
        except requests.RequestException as e:
            logger.warning("Redirect resolution failed", url=url, error=str(e))
            return url

    # ─── Anti-Detection ───────────────────────────────────────

    def _set_random_user_agent(self) -> None:
        """Set a random user agent on the page context."""
        try:
            agent = random.choice(USER_AGENTS)
            self.page.evaluate(f"""
                Object.defineProperty(navigator, 'userAgent', {{
                    get: () => '{agent}'
                }});
            """)
            logger.debug("User agent set", agent=agent[:50])
        except Exception as e:
            logger.warning("Could not set user agent", error=str(e))

    def _random_scroll(self) -> None:
        """
        Perform realistic random scroll behaviour before clicking anything.
        Scrolls down slowly, pauses, scrolls back up slightly.
        """
        try:
            # Get page height
            page_height = self.page.evaluate("document.body.scrollHeight")

            # Scroll down in chunks with random pauses
            scroll_steps = random.randint(3, 6)
            for i in range(scroll_steps):
                scroll_to = int((page_height / scroll_steps) * (i + 1) * random.uniform(0.7, 1.0))
                self.page.evaluate(f"window.scrollTo({{top: {scroll_to}, behavior: 'smooth'}})")
                time.sleep(random.uniform(0.4, 1.2))

            # Pause at bottom
            time.sleep(random.uniform(1.0, 2.5))

            # Scroll back up slightly (like a human re-reading)
            scroll_back = int(page_height * random.uniform(0.1, 0.3))
            self.page.evaluate(f"window.scrollTo({{top: {scroll_back}, behavior: 'smooth'}})")
            time.sleep(random.uniform(0.5, 1.5))

            logger.debug("Random scroll complete", steps=scroll_steps)
        except Exception as e:
            logger.warning("Random scroll failed", error=str(e))

    def _random_mouse_movement(self) -> None:
        """Move mouse to a random position to simulate human presence."""
        try:
            viewport = self.page.viewport_size
            if viewport:
                x = random.randint(100, viewport["width"] - 100)
                y = random.randint(100, viewport["height"] - 100)
                self.page.mouse.move(x, y)
                time.sleep(random.uniform(0.2, 0.6))
        except Exception:
            pass

    # ─── Retry Logic ──────────────────────────────────────────

    def _apply_with_retry(
        self,
        handler_class,
        final_url: str,
        user_id: str,
        job_id: str
    ) -> bool:
        """
        Try to apply up to MAX_RETRIES times.
        On failure, wait RETRY_DELAY_SECONDS before retrying.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(
                    "Application attempt",
                    attempt=attempt,
                    max=MAX_RETRIES,
                    handler=handler_class.__name__,
                    url=final_url
                )

                # Anti-detection: set user agent + scroll before interacting
                self._set_random_user_agent()

                # Navigate to page
                self.page.goto(final_url, wait_until="domcontentloaded")
                time.sleep(random.uniform(1.5, 3.0))

                # Scroll before clicking anything
                self._random_scroll()
                self._random_mouse_movement()

                # Initialize handler and run apply flow
                handler = handler_class(
                    page=self.page,
                    user_data=self.user_data,
                    dry_run=self.dry_run,
                )

                success = handler.execute_apply_flow()

                if success:
                    logger.info(
                        "Application succeeded",
                        attempt=attempt,
                        handler=handler_class.__name__
                    )
                    return True
                else:
                    logger.warning(
                        "Application attempt failed, will retry",
                        attempt=attempt,
                        handler=handler_class.__name__
                    )

            except Exception as e:
                logger.error(
                    "Application attempt threw exception",
                    attempt=attempt,
                    error=str(e),
                    handler=handler_class.__name__
                )

            # Wait before retrying (not after last attempt)
            if attempt < MAX_RETRIES:
                logger.info("Waiting before retry", delay=RETRY_DELAY_SECONDS)
                time.sleep(RETRY_DELAY_SECONDS)

        logger.error(
            "All retry attempts exhausted",
            handler=handler_class.__name__,
            url=final_url
        )
        return False

    # ─── Main Entry Point ─────────────────────────────────────

    def process_job(self, job_url: str, user_id: str, job_id: str) -> bool:
        """
        Determines ATS, enforces rate limits, runs anti-detection,
        executes application with retry logic.
        """

        # ── Step 1: Rate limit check ──
        try:
            self._check_rate_limits(user_id)
        except RateLimitExceeded as e:
            logger.warning("Rate limit hit", user_id=user_id, reason=str(e))
            return False

        # ── Step 2: Resolve redirects with proxy ──
        final_url = self._resolve_external_redirects(job_url)
        final_url_lower = final_url.lower()

        # ── Step 3: Match ATS handler ──
        matched_handler = None
        for domain_signature, handler_class in self.routing_table.items():
            if domain_signature in final_url_lower:
                matched_handler = handler_class
                logger.info(
                    "Routing to handler",
                    handler=handler_class.__name__,
                    url=final_url,
                    dry_run=self.dry_run,
                )
                break

        # ── Step 4: No handler matched → manual queue ──
        if not matched_handler:
            logger.warning("No ATS handler matched", url=final_url)
            self._save_to_manual_queue(user_id, job_id)
            return False

        # ── Step 5: Apply with retry + anti-detection ──
        success = self._apply_with_retry(matched_handler, final_url, user_id, job_id)

        # ── Step 6: Record application if successful ──
        if success and not self.dry_run:
            self._record_application(user_id)

        return success

    def _save_to_manual_queue(self, user_id: str, job_id: str) -> None:
        save_to_manual_queue(user_id, job_id)
        logger.info("Job flagged for manual queue", user_id=user_id, job_id=job_id)

    # ─── Utility: Current stats ───────────────────────────────

    def get_usage_stats(self, user_id: str) -> dict:
        """Return current application count and rate limit info for a user."""
        tracker = _application_tracker.get(user_id, {})
        return {
            "applications_today": tracker.get("count", 0),
            "daily_limit": MAX_APPLICATIONS_PER_DAY,
            "last_applied": tracker.get("last_applied"),
            "min_gap_minutes": MIN_GAP_BETWEEN_APPLICATIONS_MINUTES,
        }