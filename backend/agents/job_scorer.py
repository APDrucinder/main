from pydantic import BaseModel
from typing import List, Tuple
import json
import sys, os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from shared.base_agent import BaseAgent
from shared.logger import logger
from .resume_parser import ResumeData
from .job_scraper import JobPosting

class MatchScore(BaseModel):
    score: int                    
    matched_skills: List[str]
    missing_skills: List[str]
    experience_match: str         
    reasoning: str                
    should_apply: bool 

class JobScorer(BaseAgent):
    
    def __init__(self, apply_threshold: int = 80):
        super().__init__("job_scorer")
        self.apply_threshold = apply_threshold

    async def score(self, resume: ResumeData, job: JobPosting) -> MatchScore:
        prompt = f"""
        You are a senior technical recruiter...
        Score how well this candidate matches this job.
        
        CANDIDATE PROFILE:
        Skills: {', '.join(resume.skills)}
        Total Experience: {resume.total_experience_years} years
        
        Work Experience:
        {self._format_experience(resume.experience)}
        
        Education:
        {self._format_education(resume.education)}
        
        Projects:
        {chr(10).join(resume.projects[:3])}
        
        JOB DETAILS:
        Title: {job.title} | Company: {job.company} | Location: {job.location}
        Description: {job.description[:1500]}
        
        Return ONLY this JSON:
        {{
            "score": <int>,
            "matched_skills": [],
            "missing_skills": [],
            "experience_match": "match",
            "reasoning": "string"
        }}
        """
        response = await self._call_llm(prompt=prompt, max_tokens=500, trace_name="job_scoring")
        data = self._parse_json(response)
        
        return MatchScore(
            score=data['score'],
            matched_skills=data['matched_skills'],
            missing_skills=data['missing_skills'],
            experience_match=data['experience_match'],
            reasoning=data['reasoning'],
            should_apply=data['score'] >= self.apply_threshold
        )

    async def score_batch(self, resume: ResumeData, jobs: List[JobPosting], max_jobs: int = 20) -> List[Tuple[JobPosting, MatchScore]]:
        results = []
        for job in jobs[:max_jobs]:
            try:
                m_score = await self.score(resume, job)
                results.append((job, m_score))
                logger.info("Job scored", title=job.title, company=job.company, score=m_score.score)
            except Exception as e:
                logger.warning("Job scoring failed", title=job.title, error=str(e))
                continue
        results.sort(key=lambda x: x[1].score, reverse=True)
        return results
    
    def _format_experience(self, experience) -> str:
        if not experience: return "No work experience listed"
        return "\n".join([f"- {exp.role} at {exp.company}: {exp.description[:100]}" for exp in experience])

    def _format_education(self, education) -> str:
        if not education: return "No education listed"
        return "\n".join([f"- {edu.degree} from {edu.institution}" for edu in education])

async def test():
    from .resume_parser import ResumeParser
    from .job_scraper import JobScraper
    from .pre_filter import PreFilter
    
    logger.info("Starting test pipeline")
    
    parser = ResumeParser()
    scraper = JobScraper()
    pre_filter = PreFilter()
    scorer = JobScorer(apply_threshold=75)

    resume = await parser.parse("Dhruv_Resume.pdf")
    
    jobs = scraper.scrape_all(roles=["software engineer"], locations=["Bangalore"], num_per_search=5)
    
    filtered_results = await pre_filter.filter_all(jobs, resume.skills)
    filtered_jobs = [res.job for res in filtered_results if res.passed]
    
    logger.info("Filter complete", passed=len(filtered_jobs), total=len(jobs))
    
    results = await scorer.score_batch(resume, filtered_jobs, max_jobs=5)
    
    for job, s in results:
        logger.info(
            "Final score",
            title=job.title,
            company=job.company,
            score=s.score,
            should_apply=s.should_apply,
            reasoning=s.reasoning,
        )

if __name__ == "__main__":
    asyncio.run(test())