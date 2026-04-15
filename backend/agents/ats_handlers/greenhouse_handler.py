"""
Greenhouse ATS Handler
──────────────────────
Flow: Single-page form → Fill name/email/phone → Upload resume → Custom questions → Submit

Greenhouse uses standardized form IDs making it one of the most reliable ATS to automate.
Career pages are hosted at: boards.greenhouse.io/{company}/jobs/{id}
"""

from .base_ats import BaseATSHandler


class GreenhouseHandler(BaseATSHandler):

    # ── Selectors ─────────────────────────────────────────────
    FIRST_NAME = '#first_name'
    LAST_NAME = '#last_name'
    EMAIL = '#email'
    PHONE = '#phone'
    RESUME_INPUT = 'input[type="file"][id*="resume"], input[type="file"][data-field="resume"]'
    RESUME_INPUT_ALT = '#resume_input, input[name*="resume"]'
    COVER_LETTER_INPUT = 'input[type="file"][id*="cover_letter"]'
    COVER_LETTER_TEXT = '#cover_letter'
    LOCATION = '#job_application_location'
    SUBMIT_BTN = '#submit_app'
    SUBMIT_BTN_ALT = 'input[type="submit"], button[type="submit"]'
    CUSTOM_QUESTION_TEXT = '.field input[type="text"]:not(#first_name):not(#last_name):not(#email):not(#phone)'
    CUSTOM_QUESTION_TEXTAREA = '.field textarea:not(#cover_letter)'
    CUSTOM_QUESTION_SELECT = '.field select'
    SUCCESS_TEXT = 'h1, h2, .flash-success, .application-confirmation'
    LINKEDIN_FIELD = '#job_application_answers_attributes_0_text_value'

    def upload_resume(self) -> None:
        """Upload resume PDF to Greenhouse file input."""
        self.logger.info("Uploading resume to Greenhouse form")

        resume_path = self._get_resume_path()
        if not resume_path:
            self.logger.warning("No resume path in user_data")
            return

        # Try primary selector
        if self._safe_upload(self.RESUME_INPUT, resume_path):
            return

        # Try alternate selector
        if self._safe_upload(self.RESUME_INPUT_ALT, resume_path):
            return

        self.logger.warning("Could not find resume upload field")

    def fill_form(self) -> None:
        """Fill the single-page Greenhouse application form."""
        self.logger.info("Filling Greenhouse application form")

        # Core fields
        self._safe_fill(self.FIRST_NAME, self._get_user_field("first_name"))
        self._safe_fill(self.LAST_NAME, self._get_user_field("last_name"))
        self._safe_fill(self.EMAIL, self._get_user_field("email"))
        self._safe_fill(self.PHONE, self._get_user_field("phone"))

        # Location field (if present)
        location = self._get_user_field("location")
        if location:
            self._safe_fill(self.LOCATION, location)

        # LinkedIn URL (common custom field on Greenhouse)
        linkedin = self._get_user_field("linkedin_url")
        if linkedin and self._element_exists(self.LINKEDIN_FIELD):
            self._safe_fill(self.LINKEDIN_FIELD, linkedin)

        # Cover letter (text area version, if present)
        cover_letter = self._get_user_field("cover_letter")
        if cover_letter and self._element_exists(self.COVER_LETTER_TEXT):
            self._safe_fill(self.COVER_LETTER_TEXT, cover_letter)

        # Handle custom questions
        self._fill_custom_questions()

        self._human_delay(0.5, 1)

    def submit(self) -> None:
        """Click the Greenhouse submit button."""
        self.logger.info("Submitting Greenhouse application")

        if self._safe_click(self.SUBMIT_BTN):
            return

        if self._safe_click(self.SUBMIT_BTN_ALT):
            return

        raise Exception("Could not find Greenhouse submit button")

    def detect_success(self) -> bool:
        """Check for Greenhouse confirmation page or message."""
        self._human_delay(2, 3)

        # Greenhouse typically redirects to a confirmation page
        page_text = self.page.content().lower()

        success_phrases = [
            "application has been submitted",
            "thank you for applying",
            "thanks for applying",
            "application received",
            "we have received your application",
            "successfully submitted",
        ]

        for phrase in success_phrases:
            if phrase in page_text:
                self.logger.info("Greenhouse submission confirmed", matched_phrase=phrase)
                return True

        # Check URL for confirmation indicator
        if "confirmation" in self.page.url.lower() or "thank" in self.page.url.lower():
            return True

        return False

    # ─── Private Helpers ─────────────────────────────────────

    def _fill_custom_questions(self) -> None:
        """Handle Greenhouse custom screening questions."""
        # Text inputs
        custom_texts = self.page.locator(self.CUSTOM_QUESTION_TEXT + ':visible').all()
        for inp in custom_texts:
            try:
                if inp.input_value().strip():
                    continue  # Already filled
                label_el = inp.locator('xpath=ancestor::div[contains(@class,"field")]/label')
                label = label_el.text_content().lower() if label_el.count() > 0 else ""

                if "linkedin" in label:
                    inp.fill(self._get_user_field("linkedin_url", ""))
                elif "github" in label or "portfolio" in label:
                    inp.fill(self._get_user_field("github_url", ""))
                elif "website" in label:
                    inp.fill(self._get_user_field("website_url", ""))
                elif "salary" in label:
                    inp.fill(self._get_user_field("salary_expectation", "Negotiable"))
                elif "visa" in label or "sponsor" in label:
                    inp.fill(self._get_user_field("visa_status", "Yes"))
                elif "year" in label or "experience" in label:
                    inp.fill(self._get_user_field("experience_years", "2"))
                else:
                    inp.fill(self._get_user_field("default_answer", "N/A"))
            except Exception:
                continue

        # Textareas
        custom_textareas = self.page.locator(self.CUSTOM_QUESTION_TEXTAREA + ':visible').all()
        for ta in custom_textareas:
            try:
                if not ta.input_value().strip():
                    ta.fill(self._get_user_field("cover_letter",
                        "I am excited about this opportunity and believe my skills align well with your requirements."))
            except Exception:
                continue

        # Dropdowns
        custom_selects = self.page.locator(self.CUSTOM_QUESTION_SELECT + ':visible').all()
        for sel in custom_selects:
            try:
                options = sel.locator('option').all()
                for opt in options:
                    val = opt.get_attribute("value")
                    text = (opt.text_content() or "").strip().lower()
                    # Skip placeholders, prefer "Yes" if available
                    if val and text not in ("", "select", "select an option", "-- select --"):
                        if "yes" in text:
                            sel.select_option(value=val)
                            break
                else:
                    # If no "Yes", select the first non-placeholder option
                    for opt in options:
                        val = opt.get_attribute("value")
                        text = (opt.text_content() or "").strip().lower()
                        if val and text not in ("", "select", "select an option", "-- select --"):
                            sel.select_option(value=val)
                            break
            except Exception:
                continue