from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import fitz
import requests
from docx import Document
from pydantic import BaseModel

from shared.base_agent import BaseAgent
from shared.logger import logger


class WorkExperience(BaseModel):
    company: str
    role: str
    duration: str
    description: Optional[str] = ""


class Education(BaseModel):
    institution: str
    degree: str
    field: Optional[str] = "Not Specified"
    year: str
    cgpa: Optional[float] = None


class ResumeData(BaseModel):
    name: str
    email: str
    phone: str
    skills: List[str]
    experience: List[WorkExperience]
    education: List[Education]
    projects: List[str]
    total_experience_years: Optional[float] = None

    # Fields used by AutoApplyBot — parsed from resume when present
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    current_company: Optional[str] = None

    # Set externally after upload — not parsed from resume text
    file_url: Optional[str] = None


class ResumeParser(BaseAgent):
    def __init__(self):
        super().__init__("resume_parser")

    def _clean_json_response(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return text.strip()

    def _materialize_local_file(self, source: str) -> tuple[str, bool]:
        parsed = urlparse(source)
        if parsed.scheme in {"http", "https"}:
            response = requests.get(source, timeout=30)
            response.raise_for_status()
            suffix = Path(parsed.path).suffix or ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(response.content)
                return temp_file.name, True

        path = Path(source).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Resume file not found: {path}")
        return str(path), False

    def _extract_text(self, file_path: str) -> str:
        file_path = file_path.strip()
        if file_path.endswith(".pdf"):
            return self._extract_pdf(file_path)
        if file_path.endswith((".docx", ".doc")):
            return self._extract_docx(file_path)
        raise ValueError(f"Unsupported file type: {file_path}")

    def _extract_pdf(self, file_path: str) -> str:
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text.strip()

    def _extract_docx(self, file_path: str) -> str:
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

    async def parse(self, file_path: str) -> ResumeData:
        logger.info("Parsing resume", file_path=file_path)

        local_path, is_temp = self._materialize_local_file(file_path)
        try:
            raw_text = self._extract_text(local_path)
        finally:
            if is_temp:
                try:
                    Path(local_path).unlink(missing_ok=True)
                except Exception:
                    pass

        if not raw_text or len(raw_text) < 50:
            raise ValueError("Could not extract text. Please use a text-based PDF or DOCX.")

        logger.debug("Text extracted from resume", char_count=len(raw_text))

        prompt = f"""
TASK: Convert the Resume Text below into a SINGLE valid JSON object.
RULES:
1. Output ONLY the JSON object.
2. No introductory text.
3. If a field is missing, use null or [].

JSON STRUCTURE:
{{
    "name": "string",
    "email": "string",
    "phone": "string",
    "location": "string or null",
    "linkedin_url": "string or null",
    "portfolio_url": "string or null",
    "current_company": "string or null (most recent employer)",
    "skills": ["string"],
    "experience": [{{ "company": "string", "role": "string", "duration": "string", "description": "string" }}],
    "education": [{{ "institution": "string", "degree": "string", "field": "string", "year": "string", "cgpa": 0.0 }}],
    "projects": ["string"],
    "total_experience_years": 0.0
}}

RESUME TEXT:
{raw_text}
"""

        response = await self._call_llm(
            prompt=prompt,
            max_tokens=2000,
            trace_name="resume_parsing",
        )

        clean_response = self._clean_json_response(response)

        try:
            data = json.loads(clean_response)
        except json.JSONDecodeError:
            try:
                if not clean_response.endswith("}"):
                    clean_response += "}"
                data = json.loads(clean_response)
            except Exception as exc:
                logger.error("AI returned invalid JSON", raw_output=response[:500], error=str(exc))
                raise ValueError(f"AI returned invalid JSON: {exc}") from exc

        result = ResumeData(**data)
        logger.info(
            "Resume parsed successfully",
            name=result.name,
            skills_count=len(result.skills),
            experience_years=result.total_experience_years,
        )
        return result


async def test():
    parser = ResumeParser()
    result = await parser.parse("Dhruv_Resume.pdf")

    logger.info("Parsed resume", name=result.name, email=result.email)
    logger.info("Top skills", skills=result.skills[:5])
    logger.info("Experience", years=result.total_experience_years)
    logger.info("Full output", data=result.model_dump_json(indent=2))


if __name__ == "__main__":
    import asyncio

    asyncio.run(test())
