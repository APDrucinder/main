from __future__ import annotations

import abc
import os
import random
import time
from typing import Any, Dict, Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from shared.logger import logger

SCREENSHOT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "logs",
    "screenshots",
)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


class BaseATSHandler(abc.ABC):
    """
    Base class for ATS handlers using Playwright.

    Required methods:
    - fill_form
    - upload_resume
    - submit
    - detect_success
    """

    def __init__(self, page: Page, user_data: Dict[str, Any], dry_run: bool = False):
        self.page = page
        self.user_data = user_data
        self.dry_run = dry_run
        self.handler_name = self.__class__.__name__
        self.logger = logger.bind(handler=self.handler_name)

    @abc.abstractmethod
    def fill_form(self) -> None:
        pass

    @abc.abstractmethod
    def upload_resume(self) -> None:
        pass

    @abc.abstractmethod
    def submit(self) -> None:
        pass

    @abc.abstractmethod
    def detect_success(self) -> bool:
        pass

    def execute_apply_flow(self) -> bool:
        self.logger.info("Starting application flow", dry_run=self.dry_run)
        try:
            self.upload_resume()
            self._human_delay(1.5, 3.0)

            self.fill_form()
            self._human_delay(1.0, 2.5)

            self._handle_screening_questions()
            self._human_delay(0.5, 1.5)

            if self.dry_run:
                self.logger.info("DRY RUN enabled, skipping submit")
                self._take_screenshot("dry_run_before_submit")
                return True

            self.submit()
            self._human_delay(2.0, 4.0)

            is_success = self.detect_success()
            if is_success:
                self.logger.info("Application submitted successfully")
            else:
                self.logger.warning("Could not verify submission success")
                self._take_screenshot("unverified_success")
            return is_success

        except Exception as exc:
            self.logger.error("Application flow failed", error=str(exc))
            self._take_screenshot("error")
            return False

    def _handle_screening_questions(self) -> None:
        """Best-effort screening question support, disabled on failures."""
        try:
            from agents.screening_questions import ScreeningQuestionsAgent

            agent = ScreeningQuestionsAgent()
            agent.answer_screening_questions(
                self.page,
                self.user_data.get("parsed_resume", {}),
                self.user_data.get("job_data", {}),
            )
        except Exception as exc:
            self.logger.debug("Screening agent skipped", error=str(exc))

    def _safe_fill(self, selector: str, value: str, timeout: int = 10000) -> bool:
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
        except Exception as exc:
            self.logger.warning("Failed to fill field", selector=selector, error=str(exc))
            return False

    def _safe_click(self, selector: str, timeout: int = 10000) -> bool:
        try:
            locator = self.page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.click()
            self.logger.debug("Clicked element", selector=selector)
            return True
        except PlaywrightTimeout:
            self.logger.warning("Element not found for click (timeout)", selector=selector)
            return False
        except Exception as exc:
            self.logger.warning("Failed to click element", selector=selector, error=str(exc))
            return False

    def _safe_click_text(self, text: str, timeout: int = 10000) -> bool:
        try:
            locator = self.page.get_by_text(text, exact=False).first
            locator.wait_for(state="visible", timeout=timeout)
            locator.click()
            self.logger.debug("Clicked by text", text=text)
            return True
        except PlaywrightTimeout:
            self.logger.warning("Text element not found", text=text)
            return False
        except Exception as exc:
            self.logger.warning("Failed to click text element", text=text, error=str(exc))
            return False

    def _safe_upload(self, selector: str, file_path: str, timeout: int = 10000) -> bool:
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
        except Exception as exc:
            self.logger.warning("Failed to upload file", selector=selector, error=str(exc))
            return False

    def _select_dropdown(self, selector: str, value: str, timeout: int = 10000) -> bool:
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
            except Exception as exc:
                self.logger.warning(
                    "Failed to select dropdown",
                    selector=selector,
                    value=value,
                    error=str(exc),
                )
                return False

    def _wait_for(self, selector: str, timeout: int = 15000, state: str = "visible") -> bool:
        try:
            self.page.locator(selector).first.wait_for(state=state, timeout=timeout)
            return True
        except PlaywrightTimeout:
            return False

    def _element_exists(self, selector: str) -> bool:
        return self.page.locator(selector).count() > 0

    def _get_text(self, selector: str) -> Optional[str]:
        try:
            locator = self.page.locator(selector).first
            return locator.text_content()
        except Exception:
            return None

    def _human_delay(self, min_sec: float = 1.0, max_sec: float = 3.0) -> None:
        time.sleep(random.uniform(min_sec, max_sec))

    def _take_screenshot(self, label: str = "failure") -> None:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"{self.handler_name}_{label}_{timestamp}.png"
        filepath = os.path.join(SCREENSHOT_DIR, filename)
        try:
            self.page.screenshot(path=filepath, full_page=True)
            self.logger.info("Screenshot saved", path=filepath)
        except Exception as exc:
            self.logger.warning("Failed to save screenshot", error=str(exc))

    def _get_resume_path(self) -> str:
        return str(self.user_data.get("resume_path", ""))

    def _get_user_field(self, field: str, default: str = "") -> str:
        value = self.user_data.get(field, default)
        return "" if value is None else str(value)
