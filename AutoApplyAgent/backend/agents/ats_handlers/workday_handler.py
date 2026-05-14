"""
Workday ATS Handler
───────────────────
Flow: Upload resume → Parser auto-fills → Review/correct → Multi-step Next → Submit

Workday is the most complex ATS. Key characteristics:
- Uses `data-automation-id` attributes for element identification
- Multi-step wizard with "Next" and "Submit" navigation
- Resume parser auto-fills many fields after upload
- Dynamic JavaScript-heavy pages with custom components
- Career pages at: {company}.myworkdayjobs.com
"""

from .base_ats import BaseATSHandler


class WorkdayHandler(BaseATSHandler):

    # ── Selectors (data-automation-id is Workday's convention) ──
    # Apply button
    APPLY_BTN = 'a[data-automation-id="jobPostingApplyButton"]'
    APPLY_BTN_ALT = 'a:has-text("Apply"), button:has-text("Apply")'

    # Resume upload
    FILE_INPUT = 'input[data-automation-id="file-upload-input-ref"]'
    FILE_INPUT_ALT = 'input[type="file"]'
    FILE_DROP_ZONE = 'div[data-automation-id="file-upload-drop-zone"]'

    # Form fields
    LEGAL_NAME_FIRST = 'input[data-automation-id="legalNameSection_firstName"]'
    LEGAL_NAME_LAST = 'input[data-automation-id="legalNameSection_lastName"]'
    EMAIL = 'input[data-automation-id="email"]'
    PHONE = 'input[data-automation-id="phone-number"]'
    PHONE_DEVICE = 'select[data-automation-id="phone-device-type"]'
    ADDRESS_LINE1 = 'input[data-automation-id="addressSection_addressLine1"]'
    CITY = 'input[data-automation-id="addressSection_city"]'
    COUNTRY = 'select[data-automation-id="addressSection_countryRegion"]'
    POSTAL_CODE = 'input[data-automation-id="addressSection_postalCode"]'

    # Experience section
    ADD_EXPERIENCE_BTN = 'button[data-automation-id="Add"]'
    JOB_TITLE = 'input[data-automation-id="jobTitle"]'
    COMPANY_INPUT = 'input[data-automation-id="company"]'

    # Navigation
    NEXT_BTN = 'button[data-automation-id="bottom-navigation-next-button"]'
    SUBMIT_BTN = 'button[data-automation-id="bottom-navigation-next-button"]'  # Same button, text changes
    PREVIOUS_BTN = 'button[data-automation-id="bottom-navigation-previous-button"]'

    # Login/Account
    CREATE_ACCOUNT_LINK = 'a[data-automation-id="createAccountLink"]'
    SIGN_IN_EMAIL = 'input[data-automation-id="signIn-email"]'
    SIGN_IN_PASSWORD = 'input[data-automation-id="signIn-password"]'
    SIGN_IN_BTN = 'button[data-automation-id="signInSubmitButton"]'

    # Consent & Agreement
    CONSENT_CHECKBOX = 'input[data-automation-id="agreementCheckbox"]'

    # Success
    SUCCESS_INDICATOR = '[data-automation-id="thankYouMessage"]'

    # Generic inputs/textareas
    TEXT_INPUT = 'input[type="text"]:visible'
    TEXTAREA = 'textarea:visible'
    SELECT = 'select:visible'

    def upload_resume(self) -> None:
        """Upload resume to trigger Workday's parser."""
        self.logger.info("Uploading resume to Workday parser")

        resume_path = self._get_resume_path()
        if not resume_path:
            self.logger.warning("No resume path in user_data")
            return

        # Try the standard Workday file input
        if self._safe_upload(self.FILE_INPUT, resume_path):
            self.logger.info("Resume uploaded, waiting for parser...")
            # Workday parser takes a few seconds to auto-fill
            self._human_delay(3, 6)
            return

        # Fallback to generic file input
        if self._safe_upload(self.FILE_INPUT_ALT, resume_path):
            self._human_delay(3, 6)
            return

        self.logger.warning("Could not find Workday file upload")

    def fill_form(self) -> None:
        """
        Navigate through Workday's multi-step form.
        Many fields may already be populated by the resume parser.
        We only fill empty fields.
        """
        self.logger.info("Navigating Workday multi-step form")

        # Click Apply if on the job posting page
        if self._element_exists(self.APPLY_BTN):
            self._safe_click(self.APPLY_BTN)
            self._human_delay(2, 4)
        elif self._element_exists(self.APPLY_BTN_ALT):
            self._safe_click(self.APPLY_BTN_ALT)
            self._human_delay(2, 4)

        # Handle login/account creation if needed
        self._handle_auth()

        # Navigate through form steps
        max_steps = 8
        for step in range(max_steps):
            self.logger.info("Processing Workday step", step=step + 1)
            self._human_delay(1, 2)

            # Fill any visible personal info fields
            self._fill_personal_info()

            # Handle consent checkboxes
            self._handle_consent()

            # Fill any generic empty inputs
            self._fill_generic_fields()

            # Check if submit button says "Submit" (final step)
            submit_btn = self.page.locator(self.NEXT_BTN).first
            if submit_btn.is_visible():
                btn_text = (submit_btn.text_content() or "").lower()
                if "submit" in btn_text:
                    self.logger.info("Reached submit step")
                    return  # submit() will handle the click

            # Click Next to proceed
            if self._safe_click(self.NEXT_BTN, timeout=5000):
                self._human_delay(2, 4)
            else:
                self.logger.info("No Next button found, assuming final step")
                return

    def submit(self) -> None:
        """Click Workday's submit button."""
        self.logger.info("Submitting Workday application")

        # The submit button is the same as "Next" but with different text
        if self._safe_click(self.SUBMIT_BTN):
            self._human_delay(3, 5)
            return

        # Fallback: try text-based click
        if self._safe_click_text("Submit"):
            self._human_delay(3, 5)
            return

        raise Exception("Could not find Workday submit button")

    def detect_success(self) -> bool:
        """Check for Workday's thank you / confirmation page."""
        self._human_delay(2, 3)

        # Check for the data-automation-id thank you message
        if self._wait_for(self.SUCCESS_INDICATOR, timeout=10000):
            self.logger.info("Workday submission confirmed via thank you message")
            return True

        page_text = self.page.content().lower()
        success_phrases = [
            "thank you for your application",
            "application has been submitted",
            "successfully submitted",
            "application received",
            "thank you for applying",
        ]

        for phrase in success_phrases:
            if phrase in page_text:
                self.logger.info("Workday submission confirmed", matched_phrase=phrase)
                return True

        return False

    # ─── Private Helpers ─────────────────────────────────────

    def _handle_auth(self) -> None:
        """Handle Workday's sign-in or create account flow."""
        if self._element_exists(self.SIGN_IN_EMAIL):
            email = self._get_user_field("email")
            password = self._get_user_field("workday_password")

            if email and password:
                self._safe_fill(self.SIGN_IN_EMAIL, email)
                self._safe_fill(self.SIGN_IN_PASSWORD, password)
                self._safe_click(self.SIGN_IN_BTN)
                self._human_delay(3, 5)
                self.logger.info("Signed into Workday")
            else:
                self.logger.warning("Workday credentials not in user_data")

    def _fill_personal_info(self) -> None:
        """Fill personal information fields if empty."""
        field_map = {
            self.LEGAL_NAME_FIRST: ("first_name", ""),
            self.LEGAL_NAME_LAST: ("last_name", ""),
            self.EMAIL: ("email", ""),
            self.PHONE: ("phone", ""),
            self.ADDRESS_LINE1: ("address_line1", ""),
            self.CITY: ("city", ""),
            self.POSTAL_CODE: ("postal_code", ""),
        }

        for selector, (field, default) in field_map.items():
            if self._element_exists(selector):
                try:
                    inp = self.page.locator(selector).first
                    if not inp.input_value().strip():
                        value = self._get_user_field(field, default)
                        if value:
                            inp.fill(value)
                except Exception:
                    continue

        # Country dropdown
        country = self._get_user_field("country", "India")
        if country and self._element_exists(self.COUNTRY):
            self._select_dropdown(self.COUNTRY, country)

    def _handle_consent(self) -> None:
        """Check any visible consent/agreement checkboxes."""
        try:
            checkboxes = self.page.locator('input[type="checkbox"]:visible').all()
            for cb in checkboxes:
                if not cb.is_checked():
                    cb.check()
                    self.logger.debug("Checked consent checkbox")
        except Exception:
            pass

    def _fill_generic_fields(self) -> None:
        """Fill any remaining empty visible input fields."""
        # Empty text inputs
        inputs = self.page.locator('input[type="text"]:visible').all()
        for inp in inputs:
            try:
                if not inp.input_value().strip():
                    label_text = inp.get_attribute("aria-label") or ""
                    placeholder = inp.get_attribute("placeholder") or ""
                    hint = (label_text + placeholder).lower()

                    if any(kw in hint for kw in ["year", "experience"]):
                        inp.fill(self._get_user_field("experience_years", "2"))
                    elif "salary" in hint:
                        inp.fill(self._get_user_field("salary_expectation", "Negotiable"))
            except Exception:
                continue

        # Empty select dropdowns — select first valid option
        selects = self.page.locator('select:visible').all()
        for sel in selects:
            try:
                current = sel.input_value()
                if not current:
                    options = sel.locator('option').all()
                    for opt in options:
                        val = opt.get_attribute("value")
                        if val and val.strip():
                            sel.select_option(value=val)
                            break
            except Exception:
                continue