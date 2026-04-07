import fitz  
from docx import Document
from pydantic import BaseModel
from typing import List, Optional
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from shared.base_agent import BaseAgent

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
        raw_text = self._extract_text(file_path)
        
        if not raw_text or len(raw_text) < 50:
            raise ValueError("Could not extract text. Please use a text-based PDF.")
        
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
                print(f"--- DEBUG: RAW AI OUTPUT ---\n{response}\n---------------------------")
                raise Exception(f"AI returned invalid JSON: {e}")

        return ResumeData(**data)

async def test():
    parser = ResumeParser()
    result = await parser.parse("Dhruv_Resume.pdf")
    
    print("\n--- PARSED RESUME ---")
    print(f"Name: {result.name}")
    print(f"Email: {result.email}")
    print(f"Skills: {', '.join(result.skills[:5])}")
    print(f"Experience: {result.total_experience_years} years")
    print("--------------------\n")
    print(result.model_dump_json(indent=2))

if __name__ == "__main__":
    import asyncio
    asyncio.run(test())