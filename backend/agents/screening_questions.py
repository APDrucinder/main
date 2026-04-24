"""
Screening Questions Agent
─────────────────────────
Scans an apply form for non-standard questions and uses the LLM
to answer them based on the user's resume and job context.

Handles: text inputs, textareas, dropdowns, radio buttons.
Flags sensitive or unclear questions for user review instead of guessing.
"""

import asyncio
import time
from typing import Optional, List, Dict, Any
from playwright.sync_api import Page

from shared.base_agent import BaseAgent
from shared.logger import logger

# ─── Questions that should never be auto-answered ─────────────
SENSITIVE_KEYWORDS = [
    "criminal", "background check", "drug test",
    "disability", "veteran", "race", "gender",
    "ethnicity", "religion", "political",
    "medical", "health condition", "date of birth", "age",
]

# ─── Standard fields to skip (already handled by ATS handlers) ─
STANDARD_FIELD_KEYWORDS = [
    "first name", "last name", "email", "phone",
    "address", "city", "zip", "postal", "country",
    "resume", "cv", "cover letter", "linkedin",
    "github", "portfolio", "website",
]

# ─── Common screening questions and their field keywords ───────
COMMON_QUESTIONS = {
    "notice_period": ["notice period", "joining", "available from", "start date"],
    "current_salary": ["current salary", "current ctc", "current compensation"],
    "expected_salary": ["expected salary", "expected ctc", "salary expectation", "desired salary"],
    "relocate": ["willing to relocate", "open to relocation", "relocation"],
    "visa_status": ["visa", "work permit", "right to work", "authorized to work"],
    "remote": ["remote", "work from home", "wfh", "hybrid"],
    "experience_years": ["years of experience", "total experience", "work experience"],
}

class ScreeningAnswer:
    def __init__(
        self,
        question: str,
        answer: str,
        flagged: bool = False,
        flag_reason: str = ""
    ):
        self.question = question
        self.answer = answer
        self.flagged = flagged
        self.flag_reason = flag_reason

class ScreeningQuestionsAgent(BaseAgent):
    def __init__(self):
        super().__init__("screening_questions")

    def _call_llm_sync(self, prompt: str, max_tokens: int = 100) -> str:
        """Sync wrapper used by Playwright sync handlers."""
        return asyncio.run(self._call_llm(prompt=prompt, max_tokens=max_tokens))

    # ─── Main Entry (Now Synchronous) ─────────────────────────

    def answer_screening_questions(
        self,
        page: Page,
        resume_data: Dict[str, Any],
        job_data: Dict[str, Any],
        container_selector: str = "body"
    ) -> List[ScreeningAnswer]:
        """
        Scan the page for non-standard screening questions,
        get LLM answers, fill them in, and return results.
        """
        logger.info("Scanning for screening questions", job=job_data.get("title"))

        questions = self._scan_for_questions(page, container_selector)

        if not questions:
            logger.info("No screening questions found")
            return []

        logger.info("Found screening questions", count=len(questions))

        results = []
        for q in questions:
            # Called synchronously to match Playwright Sync API
            answer = self._get_answer(q, resume_data, job_data)
            results.append(answer)

            if answer.flagged:
                logger.warning(
                    "Question flagged for review",
                    question=answer.question,
                    reason=answer.flag_reason
                )
            else:
                self._fill_question(page, q, answer.answer)
                logger.info(
                    "Filled screening question",
                    question=answer.question[:60],
                    answer=answer.answer[:60]
                )

        flagged = [r for r in results if r.flagged]
        filled = [r for r in results if not r.flagged]
        logger.info(
            "Screening questions complete",
            filled=len(filled),
            flagged=len(flagged)
        )

        return results

    # ─── Page Scanner ─────────────────────────────────────────

    def _scan_for_questions(self, page: Page, container: str) -> List[Dict[str, Any]]:
        questions = []

        # 1. Text inputs
        inputs = page.locator(f'{container} input[type="text"]:visible').all()
        for inp in inputs:
            try:
                label = self._get_field_label(page, inp)
                if not label or self._is_standard_field(label):
                    continue
                if inp.input_value().strip():
                    continue

                questions.append({"type": "text", "label": label, "element": inp})
            except Exception:
                continue

        # 2. Textareas
        textareas = page.locator(f'{container} textarea:visible').all()
        for ta in textareas:
            try:
                label = self._get_field_label(page, ta)
                if not label or self._is_standard_field(label):
                    continue
                if ta.input_value().strip():
                    continue

                questions.append({"type": "textarea", "label": label, "element": ta})
            except Exception:
                continue

        # 3. Dropdowns
        selects = page.locator(f'{container} select:visible').all()
        for sel in selects:
            try:
                label = self._get_field_label(page, sel)
                if not label or self._is_standard_field(label):
                    continue
                
                options = [
                    opt.text_content().strip()
                    for opt in sel.locator('option').all()
                    if opt.get_attribute("value") and opt.text_content().strip()
                ]

                questions.append({
                    "type": "select",
                    "label": label,
                    "element": sel,
                    "options": options
                })
            except Exception:
                continue

        # 4. Radio buttons
        radio_groups = {}
        radios = page.locator(f'{container} input[type="radio"]:visible').all()
        for radio in radios:
            try:
                label = self._get_field_label(page, radio)
                group_label = self._get_radio_group_label(page, radio) or "Other Question"

                if not group_label or self._is_standard_field(group_label):
                    continue

                if group_label not in radio_groups:
                    radio_groups[group_label] = {
                        "type": "radio",
                        "label": group_label,
                        "options": [],
                        "elements": []
                    }

                radio_groups[group_label]["options"].append(label or radio.get_attribute("value"))
                radio_groups[group_label]["elements"].append(radio)
            except Exception:
                continue

        questions.extend(radio_groups.values())
        return questions

    # ─── LLM Answering ────────────────────────────────────────

    def _get_answer(
        self,
        question: Dict[str, Any],
        resume_data: Dict[str, Any],
        job_data: Dict[str, Any]
    ) -> ScreeningAnswer:
        label = question["label"]

        if self._is_sensitive(label):
            return ScreeningAnswer(label, "", True, "Sensitive/Demographic info")

        direct_answer = self._get_direct_answer(label, resume_data)
        if direct_answer:
            return ScreeningAnswer(label, direct_answer)

        options_text = f"\nAvailable options: {', '.join(question['options'])}" if question.get("options") else ""
        
        prompt = f"""
Applicant: {resume_data.get('name', 'User')}
Experience: {resume_data.get('total_experience_years', '0')} years
Skills: {', '.join(resume_data.get('skills', [])[:10])}

Job: {job_data.get('title')} at {job_data.get('company')}

Question: {label}
{options_text}

Answer the question professionally based on the profile. 
If unsure or info is missing, respond with: FLAG: <reason>
Answer:"""

        try:
            # Note: Ensure your BaseAgent._call_llm supports sync calls 
            # or wrap your async call if needed.
            response = self._call_llm_sync(prompt=prompt, max_tokens=100)
            response = response.strip()

            if response.upper().startswith("FLAG:"):
                return ScreeningAnswer(label, "", True, response[5:].strip())

            return ScreeningAnswer(label, response)
        except Exception as e:
            return ScreeningAnswer(label, "", True, f"LLM Error: {str(e)}")

    # ─── Form Filler ──────────────────────────────────────────

    def _fill_question(self, page: Page, question: Dict[str, Any], answer: str) -> None:
        try:
            el = question["element"] if "element" in question else None
            q_type = question["type"]

            if q_type in ("text", "textarea") and el:
                el.fill(answer)

            elif q_type == "select" and el:
                # Direct match or partial match
                el.select_option(label=answer)

            elif q_type == "radio":
                elements = question.get("elements", [])
                opts = question.get("options", [])
                for i, opt_label in enumerate(opts):
                    if answer.lower() in (opt_label or "").lower():
                        elements[i].check()
                        return
                # Default safety
                if elements: elements[0].check()

        except Exception as e:
            logger.warning("Fill failed", question=question.get("label"), error=str(e))

    # ─── Helpers ──────────────────────────────────────────────

    def _get_field_label(self, page: Page, element) -> Optional[str]:
        try:
            for attr in ["aria-label", "placeholder", "name", "id"]:
                val = element.get_attribute(attr)
                if val: return val.replace("_", " ").title()
            
            # Label lookup
            field_id = element.get_attribute("id")
            if field_id:
                label_text = page.locator(f'label[for="{field_id}"]').text_content()
                if label_text: return label_text.strip()
        except: pass
        return None

    def _get_radio_group_label(self, page: Page, radio) -> Optional[str]:
        try:
            return radio.locator('xpath=ancestor::fieldset/legend').first.text_content().strip()
        except: return None

    def _is_standard_field(self, label: str) -> bool:
        return any(kw in label.lower() for kw in STANDARD_FIELD_KEYWORDS)

    def _is_sensitive(self, label: str) -> bool:
        return any(kw in label.lower() for kw in SENSITIVE_KEYWORDS)

    def _get_direct_answer(self, label: str, resume_data: dict) -> Optional[str]:
        label_lower = label.lower()
        for q_type, keywords in COMMON_QUESTIONS.items():
            if any(kw in label_lower for kw in keywords):
                return str(resume_data.get(q_type, "Yes"))
        return None
