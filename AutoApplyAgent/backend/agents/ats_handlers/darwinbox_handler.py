"""
Darwinbox ATS Handler
─────────────────────
Flow: Single-page form → Fill details → Upload resume → Submit

Darwinbox is widely used in Indian companies (e.g., Swiggy, Meesho, CRED).
Career pages are at: {company}.darwinbox.in/ms/candidate/careers/{id}
The form structure is fairly standard with some company-specific customizations.
"""

from .base_ats import BaseATSHandler


class DarwinboxHandler(BaseATSHandler):

    # ── Selectors ─────────────────────────────────────────────
    # Apply button on job listing
    APPLY_BTN = 'button:has-text("Apply"), a:has-text("Apply Now"), .apply-btn'

    # Core form fields
    FIRST_NAME = 'input[name*="first_name"], input[placeholder*="First Name"], #first_name'
    LAST_NAME = 'input[name*="last_name"], input[placeholder*="Last Name"], #last_name'
    EMAIL = 'input[name*="email"], input[type="email"], #email'
    PHONE = 'input[name*="phone"], input[name*="mobile"], input[type="tel"]'
    CURRENT_COMPANY = 'input[name*="current_company"], input[placeholder*="Current Company"]'
    CURRENT_DESIGNATION = 'input[name*="designation"], input[placeholder*="Designation"]'
    EXPERIENCE = 'input[name*="experience"], input[placeholder*="Experience"]'
    CURRENT_CTC = 'input[name*="current_ctc"], input[placeholder*="Current CTC"]'
    EXPECTED_CTC = 'input[name*="expected_ctc"], input[placeholder*="Expected CTC"]'
    NOTICE_PERIOD = 'input[name*="notice_period"], select[name*="notice_period"]'
    LOCATION = 'input[name*="location"], input[name*="city"]'

    # Resume
    FILE_INPUT = 'input[type="file"]'

    # Submit
    SUBMIT_BTN = 'button[type="submit"], button:has-text("Submit"), input[type="submit"]'

    # Success
    SUCCESS_MSG = ':has-text("Application submitted"), :has-text("Thank you"), .success-message'

    def upload_resume(self) -> None:
        """Upload resume to Darwinbox form."""
        self.logger.info("Uploading resume to Darwinbox")

        resume_path = self._get_resume_path()
        if not resume_path:
            self.logger.warning("No resume path in user_data")
            return

        self._safe_upload(self.FILE_INPUT, resume_path)

    def fill_form(self) -> None:
        """Fill the Darwinbox application form."""
        self.logger.info("Filling Darwinbox application form")

        # Click Apply if on the listing page
        if self._element_exists(self.APPLY_BTN):
            self._safe_click(self.APPLY_BTN)
            self._human_delay(2, 3)

        # Core fields
        self._safe_fill(self.FIRST_NAME, self._get_user_field("first_name"))
        self._safe_fill(self.LAST_NAME, self._get_user_field("last_name"))
        self._safe_fill(self.EMAIL, self._get_user_field("email"))
        self._safe_fill(self.PHONE, self._get_user_field("phone"))

        # Professional fields (common in Indian ATS)
        self._safe_fill(self.CURRENT_COMPANY, self._get_user_field("current_company", ""))
        self._safe_fill(self.CURRENT_DESIGNATION, self._get_user_field("current_designation", ""))
        self._safe_fill(self.EXPERIENCE, self._get_user_field("experience_years", ""))
        self._safe_fill(self.CURRENT_CTC, self._get_user_field("current_ctc", ""))
        self._safe_fill(self.EXPECTED_CTC, self._get_user_field("expected_ctc", ""))
        self._safe_fill(self.LOCATION, self._get_user_field("city", ""))

        # Notice period (could be input or dropdown)
        notice = self._get_user_field("notice_period", "30 days")
        if self._element_exists('select[name*="notice_period"]'):
            self._select_dropdown('select[name*="notice_period"]', notice)
        elif self._element_exists('input[name*="notice_period"]'):
            self._safe_fill('input[name*="notice_period"]', notice)

        # Handle any remaining dropdowns
        self._fill_remaining_dropdowns()

        self._human_delay(0.5, 1)

    def submit(self) -> None:
        """Submit the Darwinbox application."""
        self.logger.info("Submitting Darwinbox application")

        if self._safe_click(self.SUBMIT_BTN):
            self._human_delay(2, 4)
            return

        raise Exception("Could not find Darwinbox submit button")

    def detect_success(self) -> bool:
        """Check for Darwinbox submission confirmation."""
        self._human_delay(2, 3)

        if self._wait_for(self.SUCCESS_MSG, timeout=10000):
            self.logger.info("Darwinbox application confirmed")
            return True

        page_text = self.page.content().lower()
        success_phrases = [
            "application submitted",
            "thank you for applying",
            "successfully submitted",
            "we have received your application",
        ]

        for phrase in success_phrases:
            if phrase in page_text:
                return True

        return False

    # ─── Private Helpers ─────────────────────────────────────

    def _fill_remaining_dropdowns(self) -> None:
        """Fill any remaining visible dropdowns with first valid option."""
        selects = self.page.locator('select:visible').all()
        for sel in selects:
            try:
                current = sel.input_value()
                if current:
                    continue
                options = sel.locator('option').all()
                for opt in options[1:]:
                    val = opt.get_attribute("value")
                    if val and val.strip():
                        sel.select_option(value=val)
                        break
            except Exception:
                continue
