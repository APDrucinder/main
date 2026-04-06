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
    description: str

class Education(BaseModel):
    institution: str
    degree: str
    field: str
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
    
    def _extract_text(self, file_path: str) -> str:
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
        # Step 1: Extract raw text
        raw_text = self._extract_text(file_path)
        
        if not raw_text or len(raw_text) < 50:
            raise ValueError("Could not extract text. Please use a text-based PDF.")
        
        # Step 2: Stricter Prompt for Ollama
        prompt = f"""
        TASK: Convert the Resume Text below into a SINGLE valid JSON object.
        RULES:
        1. Output ONLY the JSON object. 
        2. NO introductory text, NO markdown code blocks, NO triple backticks.
        3. If a field is missing, use null or [].
        4. Ensure all strings use double quotes.

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
        
        # Step 3: Clean the response (removes ```json ... ``` if AI adds it)
        clean_response = response.strip()
        if clean_response.startswith("```"):
            clean_response = clean_response.strip("`").replace("json", "", 1).strip()
        
        try:
            parsed = json.loads(clean_response)
            return ResumeData(**parsed)
        except json.JSONDecodeError as e:
            print(f"--- DEBUG: RAW AI OUTPUT ---\n{response}\n---------------------------")
            raise Exception(f"AI returned invalid JSON: {e}")


async def test():
    parser = ResumeParser()
    result = await parser.parse("MidamResume.pdf")
    
    print("\n--- PARSED RESUME ---")
    print(f"Name: {result.name}")
    print(f"Email: {result.email}")
    print(f"Skills: {', '.join(result.skills[:5])}")
    print(f"Experience: {result.total_experience_years} years")
    print(f"Education: {result.education[0].institution}")
    print("--------------------\n")
    print("Full JSON:")
    print(result.model_dump_json(indent=2))

if __name__ == "__main__":
    import asyncio
    asyncio.run(test())