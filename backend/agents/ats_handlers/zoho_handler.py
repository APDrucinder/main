"""
Zoho Recruit ATS Handler
────────────────────────
Flow: Single-page form → Fill details → Upload resume → Submit

Zoho Recruit career pages are at: recruit.zoho.com/recruit/ViewJob.na
or custom domains mapped to Zoho Recruit.
Standard form with candidate fields and file upload.
"""

from .base_ats import BaseATSHandler


class ZohoHandler(BaseATSHandler):

    # ── Selectors ─────────────────────────────────────────────
    APPLY_BTN = 'button:has-text("Apply"), a:has-text("Apply for this Job"), .apply-btn'

    # Form fields (Zoho Recruit uses data-zcqa attributes)
    FIRST_NAME = 'input[name*="First Name"], input[name*="first_name"], input[data-zcqa*="firstName"]'
    LAST_NAME = 'input[name*="Last Name"], input[name*="last_name"], input[data-zcqa*="lastName"]'
    EMAIL = 'input[name*="Email"], input[type="email"], input[data-zcqa*="email"]'
    PHONE = 'input[name*="Phone"], input[name*="Mobile"], input[data-zcqa*="phone"]'
    CURRENT_EMPLOYER = 'input[name*="Current Employer"], input[name*="company"]'
    EXPERIENCE = 'input[name*="Experience"], input[name*="experience"]'
    CURRENT_SALARY = 'input[name*="Current Salary"], input[name*="current_salary"]'
    EXPECTED_SALARY = 'input[name*="Expected Salary"], input[name*="expected_salary"]'
    CITY = 'input[name*="City"], input[name*="city"]'
    LINKEDIN = 'input[name*="LinkedIn"], input[name*="linkedin"]'
    COVER_LETTER = 'textarea[name*="Cover"], textarea[name*="cover_letter"]'

    # Resume
    FILE_INPUT = 'input[type="file"]'

    # Submit
    SUBMIT_BTN = 'button[type="submit"], input[type="submit"], button:has-text("Submit")'

    # Success
    SUCCESS_MSG = ':has-text("Application Submitted"), :has-text("Thank you"), .thankyou-message'

    def upload_resume(self) -> None:
        """Upload resume to Zoho Recruit form."""
        self.logger.info("Uploading resume to Zoho Recruit")

        resume_path = self._get_resume_path()
        if not resume_path:
            self.logger.warning("No resume path in user_data")
            return

        self._safe_upload(self.FILE_INPUT, resume_path)

    def fill_form(self) -> None:
        """Fill the Zoho Recruit application form."""
        self.logger.info("Filling Zoho Recruit application form")

        # Click Apply if on listing page
        if self._element_exists(self.APPLY_BTN):
            self._safe_click(self.APPLY_BTN)
            self._human_delay(2, 3)

        # Core fields
        self._safe_fill(self.FIRST_NAME, self._get_user_field("first_name"))
        self._safe_fill(self.LAST_NAME, self._get_user_field("last_name"))
        self._safe_fill(self.EMAIL, self._get_user_field("email"))
        self._safe_fill(self.PHONE, self._get_user_field("phone"))

        # Professional fields
        self._safe_fill(self.CURRENT_EMPLOYER, self._get_user_field("current_company", ""))
        self._safe_fill(self.EXPERIENCE, self._get_user_field("experience_years", ""))
        self._safe_fill(self.CURRENT_SALARY, self._get_user_field("current_ctc", ""))
        self._safe_fill(self.EXPECTED_SALARY, self._get_user_field("expected_ctc", ""))
        self._safe_fill(self.CITY, self._get_user_field("city", ""))
        self._safe_fill(self.LINKEDIN, self._get_user_field("linkedin_url", ""))

        # Cover letter
        cover = self._get_user_field("cover_letter")
        if cover and self._element_exists(self.COVER_LETTER):
            self._safe_fill(self.COVER_LETTER, cover)

        # Fill any remaining custom dropdowns
        self._fill_custom_dropdowns()

        # Handle any remaining text inputs
        self._fill_remaining_inputs()

        self._human_delay(0.5, 1)

    def submit(self) -> None:
        """Submit the Zoho Recruit application."""
        self.logger.info("Submitting Zoho Recruit application")

        if self._safe_click(self.SUBMIT_BTN):
            self._human_delay(2, 4)
            return

        raise Exception("Could not find Zoho Recruit submit button")

    def detect_success(self) -> bool:
        """Check for Zoho Recruit submission confirmation."""
        self._human_delay(2, 3)

        if self._wait_for(self.SUCCESS_MSG, timeout=10000):
            self.logger.info("Zoho Recruit application confirmed")
            return True

        page_text = self.page.content().lower()
        for phrase in ["application submitted", "thank you for applying", "thank you for your application"]:
            if phrase in page_text:
                return True

        # Check URL change
        if "thankyou" in self.page.url.lower() or "confirmation" in self.page.url.lower():
            return True

        return False

    # ─── Private Helpers ─────────────────────────────────────

    def _fill_custom_dropdowns(self) -> None:
        """Handle Zoho Recruit custom dropdown fields."""
        selects = self.page.locator('select:visible').all()
        for sel in selects:
            try:
                if sel.input_value():
                    continue
                options = sel.locator('option').all()
                for opt in options[1:]:
                    val = opt.get_attribute("value")
                    text = (opt.text_content() or "").lower()
                    # Prefer "Yes" for boolean questions
                    if val and "yes" in text:
                        sel.select_option(value=val)
                        break
                else:
                    for opt in options[1:]:
                        val = opt.get_attribute("value")
                        if val and val.strip():
                            sel.select_option(value=val)
                            break
            except Exception:
                continue

    def _fill_remaining_inputs(self) -> None:
        """Fill any empty visible text inputs with smart defaults."""
        inputs = self.page.locator('input[type="text"]:visible').all()
        for inp in inputs:
            try:
                if inp.input_value().strip():
                    continue
                placeholder = (inp.get_attribute("placeholder") or "").lower()
                name = (inp.get_attribute("name") or "").lower()
                hint = placeholder + name

                if "skill" in hint:
                    inp.fill(self._get_user_field("skills_summary", "Python, JavaScript, SQL"))
                elif "notice" in hint:
                    inp.fill(self._get_user_field("notice_period", "30 days"))
                elif "source" in hint or "how did you" in hint:
                    inp.fill("Job Portal")
            except Exception:
                continue