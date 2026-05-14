"""
LinkedIn Easy Apply Handler
───────────────────────────
Flow: Click "Easy Apply" → Multi-step modal → Resume → Questions → Review → Submit

Prerequisites: User must be logged into LinkedIn before this handler runs.
The login flow is handled separately (cookie injection or manual login).
"""

from .base_ats import BaseATSHandler


class LinkedInHandler(BaseATSHandler):

    # ── Selectors ─────────────────────────────────────────────
    EASY_APPLY_BTN = 'button.jobs-apply-button'
    MODAL = 'div[role="dialog"]'
    NEXT_BTN = f'{MODAL} button[aria-label="Continue to next step"]'
    REVIEW_BTN = f'{MODAL} button[aria-label="Review your application"]'
    SUBMIT_BTN = f'{MODAL} button[aria-label="Submit application"]'
    DISMISS_BTN = f'{MODAL} button[aria-label="Dismiss"]'
    FILE_INPUT = f'{MODAL} input[type="file"]'
    RESUME_DROPDOWN = f'{MODAL} select[id*="resume"]'
    # Text/textarea inputs inside modal
    TEXT_INPUT = f'{MODAL} input[type="text"]'
    TEXTAREA = f'{MODAL} textarea'
    SELECT_INPUT = f'{MODAL} select'
    FOLLOW_CHECKBOX = f'{MODAL} input[id*="follow-company"]'
    SUCCESS_BANNER = 'div[data-test-modal-id="applied-confirmation"]'
    # Alternate success indicators
    SUCCESS_ALT = 'h2:has-text("Your application was sent")'

    def upload_resume(self) -> None:
        """
        LinkedIn Easy Apply uses a pre-uploaded resume from the profile.
        If a file input is visible, upload. Otherwise, select from existing.
        """
        self.logger.info("Handling resume selection")

        # Check if there's a direct file upload input
        if self._element_exists(self.FILE_INPUT):
            resume_path = self._get_resume_path()
            if resume_path:
                self._safe_upload(self.FILE_INPUT, resume_path)
                return

        # Check if there's a resume dropdown to select existing
        if self._element_exists(self.RESUME_DROPDOWN):
            # Select the first available resume (most recent)
            try:
                dropdown = self.page.locator(self.RESUME_DROPDOWN).first
                options = dropdown.locator('option').all()
                if len(options) > 1:
                    # Select second option (first is usually placeholder)
                    dropdown.select_option(index=1)
                    self.logger.info("Selected existing resume from dropdown")
            except Exception as e:
                self.logger.warning("Could not select resume", error=str(e))

        self.logger.info("Relying on LinkedIn profile resume")

    def fill_form(self) -> None:
        """
        Click Easy Apply, then cycle through the multi-step modal.
        Handles: text inputs, textareas, dropdowns, and checkbox questions.
        """
        self.logger.info("Initiating Easy Apply flow")

        # Step 1: Click the Easy Apply button
        if not self._safe_click(self.EASY_APPLY_BTN):
            raise Exception("Easy Apply button not found — job may require external application")

        # Wait for modal
        if not self._wait_for(self.MODAL):
            raise Exception("Easy Apply modal did not appear")

        self._human_delay(1, 2)

        # Step 2: Cycle through modal steps
        max_steps = 10  # safety limit
        for step in range(max_steps):
            self.logger.info("Processing modal step", step=step + 1)
            self._human_delay(0.5, 1.5)

            # Fill any visible text inputs with user data
            self._fill_visible_inputs()

            # Handle any dropdown questions
            self._handle_dropdowns()

            # Uncheck "Follow company" if present
            self._uncheck_follow()

            # Determine which button to click next
            if self._element_exists(self.SUBMIT_BTN):
                # We've reached the final submit step — stop here
                # submit() will handle the actual click
                self.logger.info("Reached submit step")
                return

            if self._element_exists(self.REVIEW_BTN):
                self._safe_click(self.REVIEW_BTN)
                self._human_delay(1, 2)
                continue

            if self._element_exists(self.NEXT_BTN):
                self._safe_click(self.NEXT_BTN)
                self._human_delay(1, 2)
                continue

            # No navigation button found — might be single-step
            self.logger.info("No next/review button found, assuming final step")
            return

    def submit(self) -> None:
        """Click the final Submit Application button."""
        self.logger.info("Submitting LinkedIn application")

        if self._safe_click(self.SUBMIT_BTN, timeout=5000):
            self.logger.info("Submit button clicked")
            self._human_delay(2, 4)
        else:
            self.logger.warning("Submit button not found")
            raise Exception("Could not find submit button")

    def detect_success(self) -> bool:
        """Check for LinkedIn's 'Application sent' confirmation."""
        self._human_delay(1, 2)

        if self._wait_for(self.SUCCESS_BANNER, timeout=10000):
            self.logger.info("Application confirmed via banner")
            # Dismiss the success modal
            self._safe_click(self.DISMISS_BTN, timeout=3000)
            return True

        if self._wait_for(self.SUCCESS_ALT, timeout=5000):
            self.logger.info("Application confirmed via heading")
            return True

        # Check page text as fallback
        page_text = self.page.content().lower()
        if "application was sent" in page_text or "applied" in page_text:
            return True

        return False

    # ─── Private Helpers ─────────────────────────────────────

    def _fill_visible_inputs(self) -> None:
        """Fill any empty text/textarea inputs in the current modal step."""
        user_data_map = {
            "phone": self._get_user_field("phone"),
            "city": self._get_user_field("city"),
            "linkedin": self._get_user_field("linkedin_url"),
        }

        # Fill empty text inputs
        inputs = self.page.locator(f'{self.MODAL} input[type="text"]:visible').all()
        for inp in inputs:
            try:
                current_val = inp.input_value()
                if current_val.strip():
                    continue  # Already filled (pre-populated from profile)

                label = inp.get_attribute("aria-label") or ""
                placeholder = inp.get_attribute("placeholder") or ""
                field_hint = (label + placeholder).lower()

                if "phone" in field_hint or "mobile" in field_hint:
                    inp.fill(user_data_map.get("phone", ""))
                elif "city" in field_hint or "location" in field_hint:
                    inp.fill(user_data_map.get("city", ""))
                elif "linkedin" in field_hint:
                    inp.fill(user_data_map.get("linkedin", ""))
                elif "year" in field_hint or "experience" in field_hint:
                    inp.fill(self._get_user_field("experience_years", "2"))
                else:
                    # Default: fill with a safe generic answer
                    inp.fill(self._get_user_field("default_answer", "N/A"))
            except Exception:
                continue

        # Fill empty textareas
        textareas = self.page.locator(f'{self.MODAL} textarea:visible').all()
        for ta in textareas:
            try:
                if not ta.input_value().strip():
                    ta.fill(self._get_user_field("cover_letter", "I am very interested in this role."))
            except Exception:
                continue

    def _handle_dropdowns(self) -> None:
        """Handle visible select dropdowns in the current step."""
        selects = self.page.locator(f'{self.MODAL} select:visible').all()
        for sel in selects:
            try:
                # Select the first non-placeholder option
                options = sel.locator('option').all()
                for opt in options:
                    val = opt.get_attribute("value")
                    text = opt.text_content()
                    if val and val != "" and text.strip().lower() != "select an option":
                        sel.select_option(value=val)
                        break
            except Exception:
                continue

    def _uncheck_follow(self) -> None:
        """Uncheck the 'Follow company' checkbox if present."""
        try:
            checkbox = self.page.locator(self.FOLLOW_CHECKBOX).first
            if checkbox.is_visible() and checkbox.is_checked():
                checkbox.uncheck()
        except Exception:
            pass