import abc
import time
import os
from typing import Any, Dict, Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from shared.logger import logger

# Screenshots directory
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


class BaseATSHandler(abc.ABC):
    """
    Base class for all ATS handlers. Uses Playwright for browser automation.
    
    Every handler must implement:
        - fill_form()       → Fill text inputs, dropdowns, checkboxes
        - upload_resume()   → Handle file upload interaction
        - submit()          → Final review and submission click
        - detect_success()  → Verify the application was received
    
    The execute_apply_flow() template method governs execution order
    and supports dry_run mode for safe testing.
    """

    def __init__(self, page: Page, user_data: Dict[str, Any], dry_run: bool = False):
        self.page = page
        self.user_data = user_data
        self.dry_run = dry_run
        self.handler_name = self.__class__.__name__
        self.logger = logger.bind(handler=self.handler_name)

    # ─── Abstract Methods ────────────────────────────────────

    @abc.abstractmethod
    def fill_form(self) -> None:
        """Handles filling out standard text inputs, dropdowns, and checkboxes."""
        pass

    @abc.abstractmethod
    def upload_resume(self) -> None:
        """Handles the file upload interaction."""
        pass

    @abc.abstractmethod
    def submit(self) -> None:
        """Handles the final review and submission clicks."""
        pass

    @abc.abstractmethod
    def detect_success(self) -> bool:
        """Verifies if the application was actually received."""
        pass

    # ─── Template Method ─────────────────────────────────────

    def execute_apply_flow(self) -> bool:
        """Template method governing the strict order of execution."""
        self.logger.info("Starting application flow", dry_run=self.dry_run)
        try:
            self.upload_resume()
            self._human_delay(2, 4)

            self.fill_form()
            self._human_delay(1, 3)

            if self.dry_run:
                self.logger.info("DRY RUN — skipping submit")
                self._take_screenshot("dry_run_before_submit")
                return True

            self.submit()
            self._human_delay(3, 6)

            is_success = self.detect_success()
            if is_success:
                self.logger.info("Application submitted successfully")
            else:
                self.logger.warning("Could not verify submission success")
                self._take_screenshot("unverified_success")
            return is_success

        except Exception as e:
            self.logger.error("Application flow failed", error=str(e))
            self._take_screenshot("error")
            return False

    # ─── Safe Interaction Helpers ────────────────────────────

    def _safe_fill(self, selector: str, value: str, timeout: int = 10000) -> bool:
        """Wait for element, clear it, and type value. Returns True on success."""
        try:
            locator = self.page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.clear()
            locator.fill(value)
            self.logger.debug("Filled field", selector=selector, value_len=len(value))
            return True
        except PlaywrightTimeout:
            self.logger.warning("Field not found (timeout)", selector=selector)
            return False
        except Exception as e:
            self.logger.warning("Failed to fill field", selector=selector, error=str(e))
            return False

    def _safe_click(self, selector: str, timeout: int = 10000) -> bool:
        """Wait for element and click it. Returns True on success."""
        try:
            locator = self.page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.click()
            self.logger.debug("Clicked element", selector=selector)
            return True
        except PlaywrightTimeout:
            self.logger.warning("Element not found for click (timeout)", selector=selector)
            return False
        except Exception as e:
            self.logger.warning("Failed to click element", selector=selector, error=str(e))
            return False

    def _safe_click_text(self, text: str, timeout: int = 10000) -> bool:
        """Click an element by its visible text content."""
        try:
            locator = self.page.get_by_text(text, exact=False).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.click()
            self.logger.debug("Clicked by text", text=text)
            return True
        except PlaywrightTimeout:
            self.logger.warning("Text element not found", text=text)
            return False
        except Exception as e:
            self.logger.warning("Failed to click text element", text=text, error=str(e))
            return False

    def _safe_upload(self, selector: str, file_path: str, timeout: int = 10000) -> bool:
        """Upload a file to a file input element."""
        if not os.path.exists(file_path):
            self.logger.error("Resume file not found", path=file_path)
            return False
        try:
            locator = self.page.locator(selector).first
            locator.wait_for(state="attached", timeout=timeout)
            locator.set_input_files(file_path)
            self.logger.info("File uploaded", selector=selector, file=os.path.basename(file_path))
            return True
        except PlaywrightTimeout:
            self.logger.warning("File input not found (timeout)", selector=selector)
            return False
        except Exception as e:
            self.logger.warning("Failed to upload file", selector=selector, error=str(e))
            return False

    def _select_dropdown(self, selector: str, value: str, timeout: int = 10000) -> bool:
        """Select an option from a <select> dropdown by value or label."""
        try:
            locator = self.page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.select_option(label=value)
            self.logger.debug("Selected dropdown option", selector=selector, value=value)
            return True
        except Exception:
            try:
                locator.select_option(value=value)
                return True
            except Exception as e:
                self.logger.warning("Failed to select dropdown", selector=selector, value=value, error=str(e))
                return False

    def _wait_for(self, selector: str, timeout: int = 15000, state: str = "visible") -> bool:
        """Wait for an element to reach a state. Returns True if found."""
        try:
            self.page.locator(selector).first.wait_for(state=state, timeout=timeout)
            return True
        except PlaywrightTimeout:
            return False

    def _element_exists(self, selector: str) -> bool:
        """Check if an element exists on the page (no waiting)."""
        return self.page.locator(selector).count() > 0

    def _get_text(self, selector: str) -> Optional[str]:
        """Get text content of an element, or None if not found."""
        try:
            locator = self.page.locator(selector).first
            return locator.text_content()
        except Exception:
            return None

    # ─── Utilities ───────────────────────────────────────────

    def _human_delay(self, min_sec: float = 1.0, max_sec: float = 3.0) -> None:
        """Randomized delay to mimic human interaction speed."""
        import random
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def _take_screenshot(self, label: str = "failure") -> None:
        """Save a screenshot for debugging."""
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"{self.handler_name}_{label}_{timestamp}.png"
        filepath = os.path.join(SCREENSHOT_DIR, filename)
        try:
            self.page.screenshot(path=filepath, full_page=True)
            self.logger.info("Screenshot saved", path=filepath)
        except Exception as e:
            self.logger.warning("Failed to save screenshot", error=str(e))

    def _get_resume_path(self) -> str:
        """Get resume file path from user_data."""
        return self.user_data.get("resume_path", "")

    def _get_user_field(self, field: str, default: str = "") -> str:
        """Safely get a field from user_data."""
        return self.user_data.get(field, default)