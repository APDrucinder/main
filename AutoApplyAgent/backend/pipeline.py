from __future__ import annotations

import asyncio
from typing import List, Optional

from pydantic import BaseModel
from playwright.async_api import async_playwright

from agents.job_scraper import JobScraper
from agents.job_scorer import JobScorer
from agents.pre_filter import PreFilter
from agents.resume_parser import ResumeParser
from agents.auto_apply import AutoApplyBot
from agents.tier_limits import check_tier_limit
from database.connection import AsyncSessionLocal
from shared.logger import logger

ROLES = ["software engineer", "python developer", "backend developer"]
NUM_JOBS = 10
RESUME_PATH = "Dhruv_Resume.pdf"
AUTO_APPLY_MIN_THRESHOLD = 75
AUTO_APPLY_MAX_CONSECUTIVE_FAILURES = 2


class UserPreferences(BaseModel):
    target_roles: List[str]
    locations: List[str]
    experience_years: float = 0
    salary_min: int = 0
    remote_ok: bool = False
    auto_apply_threshold: int = 75


class JobApplicationPipeline:

    def __init__(
        self,
        apply_threshold: int = AUTO_APPLY_MIN_THRESHOLD,
        max_applications: int = 3,
        user_id: str = "default",
        dry_run: bool = False
    ):
        self.apply_threshold = max(apply_threshold, AUTO_APPLY_MIN_THRESHOLD)
        self.max_applications = max_applications
        self.user_id = user_id
        self.dry_run = dry_run
        self.resume_parser = ResumeParser()
        self.scraper = JobScraper()
        self.pre_filter = PreFilter()

    async def run(
        self,
        resume_path: str,
        preferences: UserPreferences
    ) -> dict:

        logger.info("=" * 60)
        logger.info("JOB PIPELINE — PARSE → SCRAPE → FILTER → SCORE → APPLY")
        logger.info("=" * 60)

        results = {
            "resume_parsed": False,
            "jobs_scraped": 0,
            "jobs_after_filter": 0,
            "jobs_scored": 0,
            "auto_apply_count": 0,
            "manual_review_count": 0,
            "applied_count": 0,
            "failed_count": 0,
            "passed": [],
            "failed": [],
            "scored": [],
            "apply_results": [],
            "errors": [],
        }

        # ─── STEP 0: Parse Resume ────────────────────────────────
        logger.info("STEP 0: Parsing resume", path=resume_path)

        try:
            resume = await self.resume_parser.parse(resume_path)
            candidate_skills = resume.skills
            results["resume_parsed"] = True
            logger.info(
                "Resume parsed",
                name=resume.name,
                skills_count=len(candidate_skills),
                experience_years=resume.total_experience_years,
            )
        except Exception as exc:
            logger.error("Failed to parse resume", error=str(exc))
            results["errors"].append(f"Resume parsing failed: {str(exc)}")
            return results

        # ─── STEP 1: Scrape Jobs ─────────────────────────────────
        logger.info("STEP 1: Scraping jobs", locations=preferences.locations)

        try:
            jobs = self.scraper.scrape_all(
                roles=preferences.target_roles,
                locations=preferences.locations,
                num_per_search=NUM_JOBS,
            )
        except Exception as exc:
            logger.error("Scraping failed", error=str(exc))
            results["errors"].append(f"Scraping failed: {str(exc)}")
            return results

        if not jobs:
            logger.warning("No jobs found. Exiting.")
            results["errors"].append("No jobs found")
            return results

        results["jobs_scraped"] = len(jobs)
        logger.info(
            "Scraping complete",
            total=len(jobs),
            indeed=sum(1 for j in jobs if j.source == "indeed"),
            internshala=sum(1 for j in jobs if j.source == "internshala"),
        )

        # ─── STEP 2: Pre-Filter ──────────────────────────────────
        logger.info("STEP 2: Pre-filtering jobs")

        try:
            filter_results = await self.pre_filter.filter_all(
                jobs, candidate_skills
            )
        except Exception as exc:
            logger.error("Pre-filter failed", error=str(exc))
            results["errors"].append(f"Pre-filter failed: {str(exc)}")
            return results

        passed = [r for r in filter_results if r.passed]
        failed = [r for r in filter_results if not r.passed]

        results["jobs_after_filter"] = len(passed)
        results["passed"] = passed
        results["failed"] = failed

        logger.info(
            "Pre-filter complete",
            passed=len(passed),
            failed=len(failed)
        )

        if not passed:
            logger.warning("No jobs passed pre-filter. Exiting.")
            results["errors"].append("No jobs passed pre-filter")
            return results

        # Sort by pre-filter score before LLM scoring
        passed.sort(key=lambda r: r.score, reverse=True)
        apply_candidates = passed[:self.max_applications]

        # ─── STEP 3: LLM Scoring ─────────────────────────────────
        logger.info(
            "STEP 3: LLM scoring",
            candidates=len(apply_candidates)
        )

        try:
            scorer = JobScorer(apply_threshold=self.apply_threshold)
            scored_results = await scorer.score_batch(
                resume=resume,
                jobs=[r.job for r in apply_candidates],
                max_jobs=15
            )
        except Exception as exc:
            logger.error("LLM scoring failed", error=str(exc))
            import traceback
            traceback.print_exc()
            results["errors"].append(f"LLM scoring failed: {str(exc)}")
            return results

        results["jobs_scored"] = len(scored_results)
        results["scored"] = scored_results

        # Separate auto apply vs manual review
        auto_apply_jobs = [
            (job, score) for job, score in scored_results
            if score.should_apply
        ]
        manual_review_jobs = [
            (job, score) for job, score in scored_results
            if not score.should_apply
        ]

        results["auto_apply_count"] = len(auto_apply_jobs)
        results["manual_review_count"] = len(manual_review_jobs)

        logger.info(
            "Scoring complete",
            scored=len(scored_results),
            auto_apply=len(auto_apply_jobs),
            manual_review=len(manual_review_jobs)
        )

        # Print scored results
        for job, score in scored_results:
            logger.info(
                "Scored job",
                score=score.score,
                title=job.title,
                company=job.company,
                should_apply=score.should_apply,
                matched=", ".join(score.matched_skills[:3]),
                missing=", ".join(score.missing_skills[:3]),
            )

        if not auto_apply_jobs:
            logger.warning(
                "No jobs above threshold. "
                "Consider lowering auto_apply_threshold."
            )
            return results

        # ─── STEP 4: Auto Apply ──────────────────────────────────
        logger.info(
            "STEP 4: Auto applying",
            jobs=len(auto_apply_jobs),
            dry_run=self.dry_run
        )

        # Build user_data from parsed resume
        user_data = {
            "name": resume.name,
            "email": resume.email,
            "phone": resume.phone,
            "resume_path": resume_path,
            "skills": resume.skills,
            "experience": [
                {
                    "company": exp.company,
                    "role": exp.role,
                    "duration": exp.duration,
                    "description": exp.description,
                }
                for exp in resume.experience
            ],
            "education": [
                {
                    "institution": edu.institution,
                    "degree": edu.degree,
                    "field": edu.field,
                    "year": edu.year,
                    "cgpa": edu.cgpa,
                }
                for edu in resume.education
            ],
        }

        apply_results = []
        consecutive_failures = 0

        try:
            applier = AutoApplyBot(
                headless=True,
                dry_run=self.dry_run
            )

            for job, score in auto_apply_jobs:
                logger.info(
                    "Attempting apply",
                    title=job.title,
                    company=job.company,
                    score=score.score
                )

                try:
                    result = await applier.apply(
                        job_url=job.apply_url,
                        user_data=user_data,
                        resume_url=resume_path,
                        credentials=None
                    )
                    success = (result.status == "applied")
                except Exception as exc:
                    logger.error("Apply failed", title=job.title, error=str(exc))
                    success = False
                    result = None

                apply_results.append({
                    "job_title": job.title,
                    "company": job.company,
                    "score": score.score,
                    "apply_url": job.apply_url,
                    "applied": success,
                    "source": job.source,
                    "status": result.status.value if result else "unknown_failure",
                    "reason": result.reason if result and not success else None,
                })

                if success:
                    consecutive_failures = 0
                    continue

                if result and result.status.value in {"login_failed", "no_credentials"}:
                    logger.warning(
                        "Stopping auto-apply run because platform session is invalid",
                        platform=result.platform,
                        status=result.status.value,
                        reason=result.reason,
                    )
                    break

                consecutive_failures += 1
                if consecutive_failures >= AUTO_APPLY_MAX_CONSECUTIVE_FAILURES:
                    logger.warning(
                        "Stopping auto-apply run after consecutive failures",
                        failures=consecutive_failures,
                        max_failures=AUTO_APPLY_MAX_CONSECUTIVE_FAILURES,
                    )
                    break

        except Exception as exc:
            logger.error("Playwright session failed", error=str(exc))
            import traceback
            traceback.print_exc()

        results["apply_results"] = apply_results
        results["applied_count"] = sum(
            1 for r in apply_results if r["applied"]
        )
        results["failed_count"] = sum(
            1 for r in apply_results if not r["applied"]
        )
       

        # ─── FINAL SUMMARY ───────────────────────────────────────
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info(
            "Summary",
            scraped=results["jobs_scraped"],
            after_filter=results["jobs_after_filter"],
            scored=results["jobs_scored"],
            applied=results["applied_count"],
            failed=results["failed_count"],
            manual_review=results["manual_review_count"],
            errors=len(results["errors"])
        )
        logger.info("=" * 60)

        return results


async def run_with_limits(
    user_id: str,
    resume_path: str,
    preferences: UserPreferences
) -> dict:

    async with AsyncSessionLocal() as db:
        limit_status = await check_tier_limit(user_id, db)

        if not limit_status["can_apply"]:
            return {
                "status": "limit_reached",
                "message": (
                    f"Daily limit reached. You are on "
                    f"{limit_status['tier']} tier with a limit of "
                    f"{limit_status['limit']} applications per day."
                ),
                "upgrade_required": True,
            }

        logger.info(
            "Tier status",
            tier=limit_status["tier"],
            remaining=limit_status["remaining"]
        )

        pipeline = JobApplicationPipeline(
            apply_threshold=preferences.auto_apply_threshold,
            max_applications=(
                limit_status["remaining"]
                if limit_status["remaining"] != "unlimited"
                else 50
            ),
            user_id=user_id,
            dry_run=False
        )

        return await pipeline.run(resume_path, preferences)


async def main():
    loc_input = input(
        "Enter locations separated by commas "
        "(or press Enter for 'Bangalore, Mumbai'): "
    )

    locations = (
        [loc.strip() for loc in loc_input.split(",")]
        if loc_input.strip()
        else ["Bangalore", "Mumbai"]
    )

    preferences = UserPreferences(
        target_roles=ROLES,
        locations=locations
    )

    # dry_run=True means no real applications submitted
    # Change to False when ready for real applications
    pipeline = JobApplicationPipeline(
        user_id="test-user",
        dry_run=True
    )

    results = await pipeline.run(RESUME_PATH, preferences)

    logger.info(
        "Run complete",
        applied=results["applied_count"],
        failed=results["failed_count"],
        manual_review=results["manual_review_count"],
        errors=results["errors"]
    )


if __name__ == "__main__":
    asyncio.run(main())
