"""
Keka ATS Handler
────────────────
Flow: Single-page form → Fill details → Upload resume → Submit

Keka is an Indian HR platform. Career pages at: {company}.keka.com/careers/{id}
Standard form-based application with resume upload.
"""

from .base_ats import BaseATSHandler


class KekaHandler(BaseATSHandler):

    # ── Selectors ─────────────────────────────────────────────
    APPLY_BTN = 'button:has-text("Apply"), a:has-text("Apply Now"), .apply-button'

    # Form fields
    FIRST_NAME = 'input[name*="firstName"], input[placeholder*="First Name"]'
    LAST_NAME = 'input[name*="lastName"], input[placeholder*="Last Name"]'
    FULL_NAME = 'input[name*="name"], input[placeholder*="Full Name"]'
    EMAIL = 'input[name*="email"], input[type="email"]'
    PHONE = 'input[name*="phone"], input[name*="mobile"], input[type="tel"]'
    EXPERIENCE = 'input[name*="experience"], input[placeholder*="Experience"]'
    CURRENT_CTC = 'input[name*="currentCtc"], input[name*="current_ctc"]'
    EXPECTED_CTC = 'input[name*="expectedCtc"], input[name*="expected_ctc"]'
    NOTICE_PERIOD = 'input[name*="noticePeriod"], select[name*="noticePeriod"]'
    LOCATION = 'input[name*="location"], input[name*="city"]'
    LINKEDIN = 'input[name*="linkedin"], input[placeholder*="LinkedIn"]'

    # Resume
    FILE_INPUT = 'input[type="file"]'

    # Submit
    SUBMIT_BTN = 'button[type="submit"], button:has-text("Submit"), button:has-text("Apply")'

    # Success
    SUCCESS_MSG = ':has-text("Application submitted"), :has-text("Thank you"), .success'

    def upload_resume(self) -> None:
        """Upload resume to Keka form."""
        self.logger.info("Uploading resume to Keka")

        resume_path = self._get_resume_path()
        if not resume_path:
            self.logger.warning("No resume path in user_data")
            return

        self._safe_upload(self.FILE_INPUT, resume_path)

    def fill_form(self) -> None:
        """Fill the Keka application form."""
        self.logger.info("Filling Keka application form")

        # Click Apply if on listing
        if self._element_exists(self.APPLY_BTN):
            self._safe_click(self.APPLY_BTN)
            self._human_delay(2, 3)

        # Name — Keka sometimes uses one field, sometimes split
        if self._element_exists(self.FIRST_NAME):
            self._safe_fill(self.FIRST_NAME, self._get_user_field("first_name"))
            self._safe_fill(self.LAST_NAME, self._get_user_field("last_name"))
        elif self._element_exists(self.FULL_NAME):
            full_name = f"{self._get_user_field('first_name')} {self._get_user_field('last_name')}"
            self._safe_fill(self.FULL_NAME, full_name.strip())

        # Contact
        self._safe_fill(self.EMAIL, self._get_user_field("email"))
        self._safe_fill(self.PHONE, self._get_user_field("phone"))

        # Professional
        self._safe_fill(self.EXPERIENCE, self._get_user_field("experience_years", ""))
        self._safe_fill(self.CURRENT_CTC, self._get_user_field("current_ctc", ""))
        self._safe_fill(self.EXPECTED_CTC, self._get_user_field("expected_ctc", ""))
        self._safe_fill(self.LOCATION, self._get_user_field("city", ""))
        self._safe_fill(self.LINKEDIN, self._get_user_field("linkedin_url", ""))

        # Notice period
        notice = self._get_user_field("notice_period", "30 days")
        if self._element_exists('select[name*="noticePeriod"]'):
            self._select_dropdown('select[name*="noticePeriod"]', notice)
        elif self._element_exists('input[name*="noticePeriod"]'):
            self._safe_fill('input[name*="noticePeriod"]', notice)

        # Any remaining dropdowns
        self._fill_remaining_selects()

        self._human_delay(0.5, 1)

    def submit(self) -> None:
        """Submit the Keka application."""
        self.logger.info("Submitting Keka application")

        if self._safe_click(self.SUBMIT_BTN):
            self._human_delay(2, 4)
            return

        raise Exception("Could not find Keka submit button")

    def detect_success(self) -> bool:
        """Check for Keka submission confirmation."""
        self._human_delay(2, 3)

        if self._wait_for(self.SUCCESS_MSG, timeout=10000):
            self.logger.info("Keka application confirmed")
            return True

        page_text = self.page.content().lower()
        for phrase in ["application submitted", "thank you for applying", "successfully submitted"]:
            if phrase in page_text:
                return True

        return False

    def _fill_remaining_selects(self) -> None:
        """Fill any unfilled visible dropdowns."""
        selects = self.page.locator('select:visible').all()
        for sel in selects:
            try:
                if sel.input_value():
                    continue
                options = sel.locator('option').all()
                for opt in options[1:]:
                    val = opt.get_attribute("value")
                    if val and val.strip():
                        sel.select_option(value=val)
                        break
            except Exception:
                continue