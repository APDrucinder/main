import fitz  
from docx import Document
from pydantic import BaseModel
from typing import List, Optional
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
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
    # Set externally after upload — NOT parsed from resume text
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
    
    def _extract_text(self, file_path: str) -> str:
        file_path = file_path.strip()
        if file_path.endswith('.pdf'):
            return self._extract_pdf(file_path)
        elif file_path.endswith(('.docx', '.doc')):
            return self._extract_docx(file_path)
        else:
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
        raw_text = self._extract_text(file_path)
        
        if not raw_text or len(raw_text) < 50:
            raise ValueError("Could not extract text. Please use a text-based PDF.")
        
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
            trace_name="resume_parsing"
        )
        
        clean_response = self._clean_json_response(response)
        
        try:
            data = json.loads(clean_response)
        except json.JSONDecodeError:
            try:
                if not clean_response.endswith("}"):
                    clean_response += "}"
                data = json.loads(clean_response)
            except Exception as e:
                logger.error("AI returned invalid JSON", raw_output=response[:500], error=str(e))
                raise Exception(f"AI returned invalid JSON: {e}")

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