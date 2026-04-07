# backend/agents/pre_filter.py

import asyncio
import sys
import os
from typing import List

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from shared.base_agent import BaseAgent
from agents.job_scraper import JobPosting

class PreFilterResult:
    def __init__(self, job: JobPosting, passed: bool, reason: str, score: int):
        self.job = job
        self.passed = passed
        self.reason = reason
        self.score = score

class PreFilter(BaseAgent):

    def __init__(self):
        super().__init__("pre_filter")
        # FIX: Added a semaphore to limit concurrent LLM requests to 10 at a time.
        # Adjust this number based on your specific LLM API rate limits.
        self.semaphore = asyncio.Semaphore(10)

    async def filter_job(self, job: JobPosting, candidate_skills: List[str], pref_remote: bool = False) -> PreFilterResult:
        # Convert the boolean to a readable string for the LLM
        remote_status = "Remote" if job.is_remote else "On-site / Hybrid"
        
        prompt = f"""
You are a strict job pre-filter. Given a job posting and a candidate's profile, 
decide if this job is worth sending to the candidate for a detailed review.

Candidate Skills: {', '.join(candidate_skills)}
Candidate Prefers Remote: {pref_remote}

Job Title: {job.title}
Company: {job.company}
Location: {job.location}
Work Mode: {remote_status}
Description: {job.description[:1000]}

Respond ONLY in JSON. No explanation, no markdown.

{{
    "passed": true or false,
    "score": a number from 0 to 100 indicating how well the candidate fits,
    "reason": "one sentence explaining why it passed or failed (mention skills or remote status)"
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
                    reason=parsed.get("reason", "No reason given")
                )
            except Exception as e:
                print(f"  → LLM Error on '{job.title}': {e}")
                return PreFilterResult(job=job, passed=False, reason="Evaluation failed", score=0)

    async def filter_all(self, jobs: List[JobPosting], candidate_skills: List[str], pref_remote: bool = False) -> List[PreFilterResult]:
        print(f"\nPre-filtering {len(jobs)} jobs...")
        
        # Pass the pref_remote preference to every task
        tasks = [self.filter_job(job, candidate_skills, pref_remote) for job in jobs]
        results = await asyncio.gather(*tasks)

        for i, result in enumerate(results):
            status = "✅ PASSED" if result.passed else "❌ FAILED"
            # Show the remote status in the log
            mode = "Remote" if result.job.is_remote else "On-site"
            print(f"  [{i+1}/{len(jobs)}] {status} ({result.score}) — {result.job.company} ({mode}) | {result.reason}")

        passed = [r for r in results if r.passed]
        print(f"\nPre-filter done: {len(passed)}/{len(jobs)} jobs passed")
        return results