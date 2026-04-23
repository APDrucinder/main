from __future__ import annotations

import asyncio
from typing import List

from pydantic import BaseModel

from agents.job_scraper import JobScraper
from agents.pre_filter import PreFilter
from agents.resume_parser import ResumeParser
from agents.tier_limits import check_tier_limit
from database.connection import AsyncSessionLocal
from shared.logger import logger

ROLES = ["software engineer", "python developer", "backend developer"]
NUM_JOBS = 10
RESUME_PATH = "Dhruv_Resume.pdf"


class UserPreferences(BaseModel):
    target_roles: List[str]
    locations: List[str]
    experience_years: float = 0
    salary_min: int = 0
    remote_ok: bool = False
    auto_apply_threshold: int = 75


class JobApplicationPipeline:
    def __init__(self, apply_threshold: int = 75, max_applications: int = 50):
        self.apply_threshold = apply_threshold
        self.max_applications = max_applications
        self.resume_parser = ResumeParser()
        self.scraper = JobScraper()
        self.pre_filter = PreFilter()

    async def run(self, resume_path: str, preferences: UserPreferences) -> dict:
        logger.info("JOB PIPELINE — PARSE → SCRAPE → FILTER")

        results = {
            "resume_parsed": False,
            "jobs_scraped": 0,
            "jobs_after_filter": 0,
            "passed": [],
            "failed": [],
            "errors": [],
        }

        logger.info("STEP 0: Parsing resume", path=resume_path)
        try:
            resume = await self.resume_parser.parse(resume_path)
            candidate_skills = resume.skills
            results["resume_parsed"] = True
            logger.info(
                "Resume parsed",
                skills_count=len(candidate_skills),
                skills=", ".join(candidate_skills),
            )
        except Exception as exc:
            logger.error("Failed to parse resume", error=str(exc))
            results["errors"].append(str(exc))
            return results

        logger.info("STEP 1: Scraping jobs", locations=preferences.locations)
        jobs = self.scraper.scrape_all(
            roles=preferences.target_roles,
            locations=preferences.locations,
            num_per_search=NUM_JOBS,
        )

        if not jobs:
            logger.warning("No jobs found. Exiting.")
            results["errors"].append("No jobs found")
            return results

        results["jobs_scraped"] = len(jobs)
        logger.info("Scraped jobs", count=len(jobs))

        logger.info("STEP 2: Pre-filtering jobs with LLM")
        filter_results = await self.pre_filter.filter_all(jobs, candidate_skills)

        passed = [r for r in filter_results if r.passed]
        failed = [r for r in filter_results if not r.passed]

        results["jobs_after_filter"] = len(passed)
        results["passed"] = passed
        results["failed"] = failed

        logger.info("Pipeline results", passed=len(passed), failed=len(failed))

        if passed:
            passed.sort(key=lambda r: r.score, reverse=True)
            apply_candidates = passed[: self.max_applications]

            logger.info("TOP MATCHES")
            for r in apply_candidates:
                is_remote = getattr(r.job, "is_remote", None)
                if is_remote is True:
                    work_method = "Remote"
                elif is_remote is False:
                    work_method = "On-site / Hybrid"
                else:
                    work_method = getattr(r.job, "job_type", "Not specified")

                logger.info(
                    "Match",
                    score=r.score,
                    title=r.job.title,
                    company=r.job.company,
                    location=r.job.location,
                    method=work_method,
                    source=r.job.source,
                    reason=r.reason,
                    url=r.job.apply_url,
                )

        return results


async def run_with_limits(user_id: str, resume_path: str, preferences: UserPreferences) -> dict:
    async with AsyncSessionLocal() as db:
        limit_status = await check_tier_limit(user_id, db)

        if not limit_status["can_apply"]:
            return {
                "status": "limit_reached",
                "message": (
                    f"Daily limit reached. You are on {limit_status['tier']} tier "
                    f"with a limit of {limit_status['limit']} applications per day."
                ),
                "upgrade_required": True,
            }

        logger.info("Tier status", tier=limit_status["tier"], remaining=limit_status["remaining"])

        pipeline = JobApplicationPipeline(
            apply_threshold=preferences.auto_apply_threshold,
            max_applications=limit_status["remaining"]
            if limit_status["remaining"] != "unlimited"
            else 50,
        )

        return await pipeline.run(resume_path, preferences)


async def main():
    loc_input = input(
        "Enter locations separated by commas (or press Enter for 'Bangalore, Mumbai'): "
    )

    locations = [loc.strip() for loc in loc_input.split(",")] if loc_input.strip() else ["Bangalore", "Mumbai"]

    preferences = UserPreferences(target_roles=ROLES, locations=locations)
    pipeline = JobApplicationPipeline()
    results = await pipeline.run(RESUME_PATH, preferences)

    logger.info("Run complete", passed=len(results["passed"]), failed=len(results["failed"]))


if __name__ == "__main__":
    asyncio.run(main())
