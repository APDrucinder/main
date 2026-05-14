"""
Indeed ATS Handler
──────────────────
Flow: Click "Apply now" → Modal/form → Resume → Contact info → Questions → Submit

Indeed has two flows:
1. Easy Apply — modal-based, resume pre-selected from Indeed profile
2. External — redirects to company ATS (not handled here, falls through to routing)

Must be logged into Indeed before this handler runs.
"""

from .base_ats import BaseATSHandler


class IndeedHandler(BaseATSHandler):

    # ── Selectors ─────────────────────────────────────────────
    APPLY_BTN = '#indeedApplyButton, button[id*="indeedApply"], .ia-IndeedApplyButton'
    APPLY_BTN_ALT = 'button:has-text("Apply now"), a:has-text("Apply now")'

    # Modal / iframe
    APPLY_MODAL = '.ia-BasePage, .ia-SmartApply, #ia-container'
    APPLY_IFRAME = 'iframe[id*="indeedapply"], iframe[title*="Apply"]'

    # Form fields
    FIRST_NAME = '#input-applicant\\.name, input[name*="firstName"], #ia-first-name'
    LAST_NAME = 'input[name*="lastName"], #ia-last-name'
    EMAIL = '#input-applicant\\.email, input[name*="email"], #ia-email'
    PHONE = '#input-applicant\\.phoneNumber, input[name*="phone"], #ia-phone-number'
    LOCATION = 'input[name*="location"], input[name*="city"]'

    # Resume
    FILE_INPUT = 'input[type="file"]'
    RESUME_SELECT = '.ia-ResumeSelector, .resume-display-container'

    # Navigation
    CONTINUE_BTN = 'button[id*="continue"], button:has-text("Continue"), .ia-continueButton'
    SUBMIT_BTN = 'button:has-text("Submit your application"), button:has-text("Submit"), .ia-submitButton'
    REVIEW_BTN = 'button:has-text("Review"), .ia-reviewButton'

    # Questions
    TEXT_INPUT = 'input[type="text"]:visible'
    TEXTAREA = 'textarea:visible'
    SELECT = 'select:visible'
    RADIO = 'input[type="radio"]:visible'

    # Success
    SUCCESS_MSG = '.ia-PostApply, .ia-ThankYou, :has-text("Your application has been submitted")'

    def upload_resume(self) -> None:
        """Upload or select resume on Indeed."""
        self.logger.info("Handling Indeed resume step")

        # Check if inside an iframe
        self._switch_to_apply_iframe()

        # If file input is visible, upload
        if self._element_exists(self.FILE_INPUT):
            resume_path = self._get_resume_path()
            if resume_path:
                self._safe_upload(self.FILE_INPUT, resume_path)
                return

        # Otherwise, rely on Indeed's saved resume
        self.logger.info("Using Indeed profile resume")

    def fill_form(self) -> None:
        """Click Apply and navigate through the Indeed application steps."""
        self.logger.info("Navigating Indeed application flow")

        # Click Apply Now
        if not self._safe_click(self.APPLY_BTN):
            if not self._safe_click(self.APPLY_BTN_ALT):
                raise Exception("Could not find Indeed Apply button")

        self._human_delay(2, 4)

        # Switch into iframe if present
        self._switch_to_apply_iframe()

        # Navigate through steps
        max_steps = 8
        for step in range(max_steps):
            self.logger.info("Processing Indeed step", step=step + 1)
            self._human_delay(1, 2)

            # Fill personal info fields
            self._fill_contact_info()

            # Handle any questions
            self._fill_questions()

            # Check for submit button (final step)
            if self._element_exists(self.SUBMIT_BTN):
                self.logger.info("Reached Indeed submit step")
                return

            # Check for review button
            if self._element_exists(self.REVIEW_BTN):
                self._safe_click(self.REVIEW_BTN)
                self._human_delay(1, 2)
                continue

            # Click continue
            if self._safe_click(self.CONTINUE_BTN, timeout=5000):
                self._human_delay(1, 2)
                continue

            self.logger.info("No navigation button found, assuming final step")
            return

    def submit(self) -> None:
        """Submit the Indeed application."""
        self.logger.info("Submitting Indeed application")

        self._switch_to_apply_iframe()

        if self._safe_click(self.SUBMIT_BTN):
            self._human_delay(2, 4)
            return

        raise Exception("Could not find Indeed submit button")

    def detect_success(self) -> bool:
        """Check for Indeed's submission confirmation."""
        self._human_delay(2, 3)

        # Switch back to main frame for success detection
        try:
            self.page.main_frame
        except Exception:
            pass

        if self._wait_for(self.SUCCESS_MSG, timeout=10000):
            self.logger.info("Indeed application confirmed")
            return True

        page_text = self.page.content().lower()
        success_phrases = [
            "application has been submitted",
            "your application was sent",
            "thank you for applying",
            "successfully applied",
        ]

        for phrase in success_phrases:
            if phrase in page_text:
                return True

        return False

    # ─── Private Helpers ─────────────────────────────────────

    def _switch_to_apply_iframe(self) -> None:
        """Indeed wraps Easy Apply in an iframe — switch into it if present."""
        try:
            iframe = self.page.frame_locator(self.APPLY_IFRAME)
            # Test if iframe exists by checking for any content
            if iframe.locator('body').count() > 0:
                self.logger.debug("Switched to Indeed apply iframe")
                # Note: Playwright frame_locator auto-scopes subsequent calls
        except Exception:
            pass  # No iframe, working in main frame

    def _fill_contact_info(self) -> None:
        """Fill contact info fields if empty."""
        field_map = {
            self.FIRST_NAME: "first_name",
            self.LAST_NAME: "last_name",
            self.EMAIL: "email",
            self.PHONE: "phone",
            self.LOCATION: "city",
        }

        for selector, field in field_map.items():
            if self._element_exists(selector):
                try:
                    inp = self.page.locator(selector).first
                    if not inp.input_value().strip():
                        value = self._get_user_field(field)
                        if value:
                            inp.fill(value)
                except Exception:
                    continue

    def _fill_questions(self) -> None:
        """Fill any visible question fields."""
        # Text inputs
        inputs = self.page.locator(self.TEXT_INPUT).all()
        for inp in inputs:
            try:
                if not inp.input_value().strip():
                    label = inp.get_attribute("aria-label") or ""
                    placeholder = inp.get_attribute("placeholder") or ""
                    hint = (label + placeholder).lower()

                    if "year" in hint or "experience" in hint:
                        inp.fill(self._get_user_field("experience_years", "2"))
                    elif "salary" in hint:
                        inp.fill(self._get_user_field("salary_expectation", "Negotiable"))
                    else:
                        inp.fill(self._get_user_field("default_answer", "N/A"))
            except Exception:
                continue

        # Textareas
        textareas = self.page.locator(self.TEXTAREA).all()
        for ta in textareas:
            try:
                if not ta.input_value().strip():
                    ta.fill(self._get_user_field("cover_letter",
                        "I am interested in this opportunity and believe my skills align well with the requirements."))
            except Exception:
                continue

        # Dropdowns
        selects = self.page.locator(self.SELECT).all()
        for sel in selects:
            try:
                options = sel.locator('option').all()
                for opt in options[1:]:  # Skip placeholder
                    val = opt.get_attribute("value")
                    text = (opt.text_content() or "").lower()
                    if val and "yes" in text:
                        sel.select_option(value=val)
                        break
                else:
                    for opt in options[1:]:
                        val = opt.get_attribute("value")
                        if val:
                            sel.select_option(value=val)
                            break
            except Exception:
                continue

        # Radio buttons — prefer "Yes"
        radios = self.page.locator(self.RADIO).all()
        if radios:
            try:
                for radio in radios:
                    label_for = radio.get_attribute("id")
                    if label_for:
                        label = self.page.locator(f'label[for="{label_for}"]')
                        if label.count() > 0 and "yes" in (label.text_content() or "").lower():
                            radio.check()
                            break
            except Exception:
                pass