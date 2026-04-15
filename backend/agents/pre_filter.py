# backend/agents/pre_filter.py

import asyncio
import sys
import os
from typing import List

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from shared.base_agent import BaseAgent
from shared.logger import logger
from agents.job_scraper import JobPosting

class PreFilterResult:
    def __init__(self, job: JobPosting, passed: bool, reason: str, score: int, matched_skills: list = [], missing_skills: list = []):
        self.job = job
        self.passed = passed
        self.reason = reason
        self.score = score
        self.matched_skills = matched_skills
        self.missing_skills = missing_skills

class PreFilter(BaseAgent):

    def __init__(self):
        super().__init__("pre_filter")
        # Semaphore to limit concurrent LLM requests to 10 at a time.
        self.semaphore = asyncio.Semaphore(10)

    async def filter_job(self, job: JobPosting, candidate_skills: List[str], pref_remote: bool = False) -> PreFilterResult:
        remote_status = "Remote" if getattr(job, 'is_remote', False) else "On-site / Hybrid"
        prompt = f"""
You are a strict job pre-filter. Given a job posting and a candidate's skills,
decide if this job is worth sending to the candidate for a detailed review.

Candidate Skills: {', '.join(candidate_skills)}

Job Title: {job.title}
Company: {job.company}
Location: {job.location}
Description: {job.description[:1000]}

Respond ONLY in JSON. No explanation, no markdown.

{{
    "passed": true or false,
    "score": 0 to 100,
    "reason": "one sentence explaining why",
    "matched_skills": ["skill1", "skill2"],
    "missing_skills": ["skill3", "skill4"]
}}
"""
        async with self.semaphore:
            try:
                response = await self._call_llm(prompt=prompt, max_tokens=200, trace_name="pre_filter")
                parsed = self._parse_json(response)

                return PreFilterResult(
                    job=job,
                    passed=parsed.get("passed", False),
                    score=parsed.get("score", 0),
                    reason=parsed.get("reason", "No reason given"),
                    matched_skills=parsed.get("matched_skills", []),
                    missing_skills=parsed.get("missing_skills", [])
                )
            except Exception as e:
                logger.warning("LLM pre-filter failed for job", title=job.title, error=str(e))
                return PreFilterResult(job=job, passed=False, reason="Evaluation failed", score=0)

    async def filter_all(self, jobs: List[JobPosting], candidate_skills: List[str], pref_remote: bool = False) -> List[PreFilterResult]:
        logger.info("Starting pre-filter", total_jobs=len(jobs))
        
        tasks = [self.filter_job(job, candidate_skills, pref_remote) for job in jobs]
        results = await asyncio.gather(*tasks)

        for i, result in enumerate(results):
            status = "PASSED" if result.passed else "FAILED"
            mode = "Remote" if result.job.is_remote else "On-site"
            logger.info(
                "Pre-filter result",
                index=f"{i+1}/{len(jobs)}",
                status=status,
                score=result.score,
                company=result.job.company,
                mode=mode,
                reason=result.reason,
            )

        passed = [r for r in results if r.passed]
        logger.info("Pre-filter complete", passed=len(passed), total=len(jobs))
        return results