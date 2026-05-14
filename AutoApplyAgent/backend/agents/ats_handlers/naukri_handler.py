"""
Naukri ATS Handler
──────────────────
Flow: Click "Apply" → Chatbot questionnaire (if any) → Profile-based 1-click apply

Naukri uses a profile-based system where resume and basic info are pre-filled.
The main challenge is handling the chatbot-style questionnaire that some employers add.
Must be logged into Naukri before this handler runs.
"""

from .base_ats import BaseATSHandler


class NaukriHandler(BaseATSHandler):

    # ── Selectors ─────────────────────────────────────────────
    APPLY_BTN = '#apply-button, .apply-btn, button:has-text("Apply"), a:has-text("Apply on company site")'
    APPLY_BTN_ALT = '.styles_jhc__apply-button-container button'
    ALREADY_APPLIED = '.already-applied, :has-text("Already Applied")'

    # Chatbot questionnaire
    CHATBOT_CONTAINER = '.chatbot_container, .chat-container, #chatBot'
    CHATBOT_INPUT = '.chatbot_container input[type="text"], .chat-container input'
    CHATBOT_TEXTAREA = '.chatbot_container textarea, .chat-container textarea'
    CHATBOT_SEND_BTN = '.chatbot_container button[type="submit"], .chat-send-btn'
    CHATBOT_OPTIONS = '.chatbot_container .option-item, .chat-option'
    CHATBOT_RADIO = '.chatbot_container input[type="radio"]'
    CHATBOT_SELECT = '.chatbot_container select'

    # File upload (some jobs ask for fresh resume despite profile)
    FILE_INPUT = 'input[type="file"]'

    # Success
    SUCCESS_MSG = '.apply-success, .success-message, :has-text("Successfully Applied")'
    SUCCESS_ALT = ':has-text("application has been submitted"), :has-text("applied successfully")'

    def upload_resume(self) -> None:
        """
        Naukri primarily uses the saved profile resume.
        Only upload if explicitly prompted with a file input.
        """
        self.logger.info("Checking for resume upload prompt")

        if self._element_exists(self.FILE_INPUT):
            resume_path = self._get_resume_path()
            if resume_path:
                self._safe_upload(self.FILE_INPUT, resume_path)
                return

        self.logger.info("Relying on saved Naukri profile resume")

    def fill_form(self) -> None:
        """
        Click Apply and handle any chatbot questionnaire.
        Naukri is mostly a 1-click apply if profile is complete.
        """
        self.logger.info("Executing Naukri apply flow")

        # Check if already applied
        if self._element_exists(self.ALREADY_APPLIED):
            self.logger.info("Already applied to this job on Naukri")
            return

        # Click Apply
        if not self._safe_click(self.APPLY_BTN, timeout=5000):
            if not self._safe_click(self.APPLY_BTN_ALT, timeout=5000):
                raise Exception("Could not find Naukri Apply button")

        self._human_delay(2, 4)

        # Handle chatbot questionnaire if it appears
        if self._element_exists(self.CHATBOT_CONTAINER):
            self.logger.info("Chatbot questionnaire detected")
            self._handle_chatbot()

    def submit(self) -> None:
        """
        Naukri apply is typically instant after clicking Apply.
        If chatbot is present, the last chatbot send is the submit.
        """
        self.logger.info("Finalizing Naukri application")

        # Some Naukri flows have a final confirm button
        confirm_selectors = [
            'button:has-text("Submit")',
            'button:has-text("Confirm")',
            'button:has-text("Apply")',
        ]
        for sel in confirm_selectors:
            if self._safe_click(sel, timeout=3000):
                self._human_delay(1, 2)
                return

    def detect_success(self) -> bool:
        """Check for Naukri's success message."""
        self._human_delay(1, 2)

        if self._wait_for(self.SUCCESS_MSG, timeout=8000):
            self.logger.info("Naukri application confirmed")
            return True

        if self._wait_for(self.SUCCESS_ALT, timeout=5000):
            return True

        # Check if the Apply button changed to "Already Applied"
        if self._element_exists(self.ALREADY_APPLIED):
            return True

        page_text = self.page.content().lower()
        if "successfully applied" in page_text or "application submitted" in page_text:
            return True

        return False

    # ─── Private Helpers ─────────────────────────────────────

    def _handle_chatbot(self) -> None:
        """Process chatbot-style questionnaire step by step."""
        max_questions = 15  # safety limit

        for q in range(max_questions):
            self._human_delay(1, 2)

            # Handle radio button options (multiple choice)
            if self._element_exists(self.CHATBOT_OPTIONS):
                self._select_chatbot_option()
                continue

            # Handle radio buttons
            radios = self.page.locator(f'{self.CHATBOT_RADIO}:visible').all()
            if radios:
                try:
                    # Prefer "Yes" options
                    for radio in radios:
                        label = self.page.locator(f'label[for="{radio.get_attribute("id")}"]')
                        if label.count() > 0 and "yes" in (label.text_content() or "").lower():
                            radio.check()
                            break
                    else:
                        radios[0].check()  # Default to first option
                except Exception:
                    pass
                self._click_chatbot_next()
                continue

            # Handle select dropdowns
            if self._element_exists(self.CHATBOT_SELECT):
                try:
                    sel = self.page.locator(f'{self.CHATBOT_SELECT}:visible').first
                    options = sel.locator('option').all()
                    for opt in options[1:]:  # Skip placeholder
                        val = opt.get_attribute("value")
                        if val:
                            sel.select_option(value=val)
                            break
                except Exception:
                    pass
                self._click_chatbot_next()
                continue

            # Handle text input
            if self._element_exists(self.CHATBOT_INPUT):
                try:
                    inp = self.page.locator(f'{self.CHATBOT_INPUT}:visible').first
                    if not inp.input_value().strip():
                        inp.fill(self._get_user_field("experience_years", "2"))
                except Exception:
                    pass
                self._click_chatbot_next()
                continue

            # Handle textarea
            if self._element_exists(self.CHATBOT_TEXTAREA):
                try:
                    ta = self.page.locator(f'{self.CHATBOT_TEXTAREA}:visible').first
                    if not ta.input_value().strip():
                        ta.fill(self._get_user_field("default_answer", "N/A"))
                except Exception:
                    pass
                self._click_chatbot_next()
                continue

            # No more questions detected
            self.logger.info("Chatbot questionnaire complete", questions_answered=q)
            break

    def _select_chatbot_option(self) -> None:
        """Select an option from chatbot multiple-choice."""
        try:
            options = self.page.locator(f'{self.CHATBOT_OPTIONS}:visible').all()
            # Prefer "Yes" options
            for opt in options:
                text = (opt.text_content() or "").lower()
                if "yes" in text:
                    opt.click()
                    return
            # Default to first option
            if options:
                options[0].click()
        except Exception:
            pass

    def _click_chatbot_next(self) -> None:
        """Click the chatbot send/next button."""
        self._safe_click(self.CHATBOT_SEND_BTN, timeout=3000)
        self._human_delay(0.5, 1.5)