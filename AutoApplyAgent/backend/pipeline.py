from __future__ import annotations

import asyncio
import uuid
from typing import List, Optional

from pydantic import BaseModel
from playwright.async_api import async_playwright

from agents.job_scraper import JobScraper, JobPosting
from agents.job_scorer import JobScorer
from agents.pre_filter import PreFilter
from agents.resume_parser import ResumeParser
from agents.auto_apply import AutoApplyBot
from agents.tier_limits import check_tier_limit
from database.connection import AsyncSessionLocal
from database.models import Application, Job, User
from shared.logger import logger

ROLES = ["software engineer", "python developer", "backend developer"]
NUM_JOBS = 10
RESUME_PATH = "Dhruv_Resume.pdf"
AUTO_APPLY_MIN_THRESHOLD = 60
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

        # Deduplicate by apply_url and normalized title + company (same job listed on different URLs)
        import re
        seen_urls: set[str] = set()
        seen_jobs: set[tuple[str, str]] = set()
        unique_passed = []
        for r in passed:
            url_key = r.job.apply_url.rstrip("/").split("?")[0].lower()
            norm_title = re.sub(r'[^a-z0-9]', '', r.job.title.lower())
            norm_company = re.sub(r'[^a-z0-9]', '', r.job.company.lower())
            job_key = (norm_title, norm_company)

            is_duplicate = False
            if url_key in seen_urls:
                is_duplicate = True
            elif norm_title and norm_company and job_key in seen_jobs:
                is_duplicate = True

            if not is_duplicate:
                seen_urls.add(url_key)
                if norm_title and norm_company:
                    seen_jobs.add(job_key)
                unique_passed.append(r)
            else:
                logger.debug("Duplicate job removed before scoring", title=r.job.title, company=r.job.company, url=r.job.apply_url)

        # Score a larger pool so we're likely to find enough jobs above threshold
        scoring_pool_size = min(len(unique_passed), self.max_applications * 5, 15)
        apply_candidates = unique_passed[:scoring_pool_size]

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
            "total_experience_years": resume.total_experience_years,
            "experience_years": resume.total_experience_years,
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
                dry_run=self.dry_run,
                user_id=self.user_id,
            )

            for job, score in auto_apply_jobs:
                logger.info(
                    "Attempting apply",
                    title=job.title,
                    company=job.company,
                    score=score.score
                )

                # Enrich with nested job and resume contexts for screening questions agent and form filling compatibility
                job_user_data = dict(user_data)
                job_user_data["job_data"] = {
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "description": job.description,
                }
                job_user_data["parsed_resume"] = user_data

                try:
                    result = await applier.apply(
                        job_url=job.apply_url,
                        user_data=job_user_data,
                        resume_url=resume_path,
                        credentials=None
                    )
                    success = result.status.value == "applied"
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

        # ─── STEP 5: Persist to Database ─────────────────────────
        logger.info("STEP 5: Persisting results to database")
        try:
            await self._persist_results(resume_path, resume, scored_results, apply_results)
            logger.info("Database persistence complete")
        except Exception as exc:
            logger.error("Database persistence failed", error=str(exc))
            results["errors"].append(f"DB persistence failed: {str(exc)}")

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

    async def _persist_results(
        self,
        resume_path: str,
        resume,
        scored_results,
        apply_results: list[dict],
    ) -> None:
        """Save scored jobs and application results to the database."""
        apply_lookup = {
            (r["job_title"], r["company"]): r
            for r in apply_results
        }

        # Resolve user_id to a valid UUID
        import os
        resolved_user_id = None

        # 1. Check DEV_USER_ID env variable
        dev_user_str = os.getenv("DEV_USER_ID")
        if dev_user_str:
            try:
                resolved_user_id = uuid.UUID(dev_user_str)
            except ValueError:
                pass

        # 2. Check if self.user_id is a valid UUID
        if not resolved_user_id and self.user_id:
            try:
                resolved_user_id = uuid.UUID(self.user_id)
            except ValueError:
                pass

        # 3. Fallback to a valid stable UUID for test purposes
        if not resolved_user_id:
            resolved_user_id = uuid.UUID("858011cd-5a44-4e86-9bc7-0088c22b8efe")

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select

            # Ensure that the user exists in the users table to satisfy foreign key constraints
            user_exists = await db.execute(
                select(User).where(User.id == resolved_user_id)
            )
            user_row = user_exists.scalar_one_or_none()
            if not user_row:
                user_row = User(
                    id=resolved_user_id,
                    clerk_id=f"clerk_e2e_{resolved_user_id.hex[:12]}",
                    email=resume.email or "e2e-test@example.com",
                    phone=resume.phone,
                    subscription_tier="free",
                )
                db.add(user_row)
                await db.flush()
                logger.info("Created e2e test user in database", user_id=str(resolved_user_id))

            for job_posting, score in scored_results:
                # Upsert Job row
                existing_job = await db.execute(
                    select(Job).where(Job.apply_url == job_posting.apply_url)
                )
                job_row = existing_job.scalar_one_or_none()
                if not job_row:
                    job_row = Job(
                        id=uuid.uuid4(),
                        title=job_posting.title,
                        company=job_posting.company,
                        location=job_posting.location,
                        description=job_posting.description[:5000] if job_posting.description else None,
                        salary_range=job_posting.salary_range,
                        apply_url=job_posting.apply_url,
                        source=job_posting.source,
                        posted_date=job_posting.posted_date,
                    )
                    db.add(job_row)
                    await db.flush()

                # Determine application status
                apply_info = apply_lookup.get((job_posting.title, job_posting.company))
                if apply_info and apply_info.get("applied"):
                    status = "applied"
                elif score.should_apply:
                    status = "auto_apply_pending"
                else:
                    status = "matched"

                platform = apply_info.get("source") if apply_info else job_posting.source

                # Upsert Application row to avoid unique constraint violations on (user_id, job_id)
                existing_app = await db.execute(
                    select(Application).where(
                        Application.user_id == resolved_user_id,
                        Application.job_id == job_row.id
                    )
                )
                app_row = existing_app.scalar_one_or_none()
                if not app_row:
                    app_row = Application(
                        id=uuid.uuid4(),
                        user_id=resolved_user_id,
                        job_id=job_row.id,
                        match_score=score.score,
                        matched_skills=score.matched_skills,
                        missing_skills=score.missing_skills,
                        reasoning=score.reasoning,
                        status=status,
                        platform=platform,
                        manual_apply_url=job_posting.apply_url,
                    )
                    db.add(app_row)
                else:
                    app_row.match_score = score.score
                    app_row.matched_skills = score.matched_skills
                    app_row.missing_skills = score.missing_skills
                    app_row.reasoning = score.reasoning
                    app_row.status = status
                    app_row.platform = platform
                    app_row.manual_apply_url = job_posting.apply_url

            await db.commit()
            logger.info(
                "Persisted to database",
                jobs=len(scored_results),
                applications=len(scored_results),
            )


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
