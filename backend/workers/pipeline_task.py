import asyncio
from celery_app import celery
from agents.job_scraper import JobScraper
from agents.pre_filter import PreFilter
from agents.resume_parser import ResumeParser
from database.connection import AsyncSessionLocal
from database.models import Job, Application, JobPreference
from sqlalchemy import select
import uuid
from datetime import datetime
from shared.logger import logger

# Fallback defaults if user has no preferences set
DEFAULT_ROLES = ["software engineer", "python developer", "backend developer"]
DEFAULT_LOCATIONS = ["Bangalore", "Mumbai"]
DEFAULT_NUM_JOBS = 10

# ── Feature flags (can be patched by tests/scripts) ──────────────
AUTO_APPLY_ENABLED: bool = False
AUTO_APPLY_DRY_RUN: bool = True


async def fetch_user_preferences(user_id: str) -> dict:
    """Fetch user's JobPreference from DB. Returns defaults if none set."""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(JobPreference).where(
                    JobPreference.user_id == uuid.UUID(user_id),
                    JobPreference.is_active == True,
                )
            )
            prefs = result.scalar_one_or_none()

            if prefs:
                logger.info(
                    "Loaded user preferences",
                    user_id=user_id,
                    roles=prefs.target_roles,
                    locations=prefs.locations,
                    remote_ok=prefs.remote_ok,
                    threshold=prefs.auto_apply_threshold,
                )
                return {
                    "roles": prefs.target_roles or DEFAULT_ROLES,
                    "locations": prefs.locations or DEFAULT_LOCATIONS,
                    "remote_ok": prefs.remote_ok,
                    "threshold": prefs.auto_apply_threshold,
                }
            else:
                logger.warning("No preferences found, using defaults", user_id=user_id)
                return {
                    "roles": DEFAULT_ROLES,
                    "locations": DEFAULT_LOCATIONS,
                    "remote_ok": False,
                    "threshold": 75,
                }
        except Exception as e:
            logger.error("Failed to fetch preferences, using defaults", user_id=user_id, error=str(e))
            return {
                "roles": DEFAULT_ROLES,
                "locations": DEFAULT_LOCATIONS,
                "remote_ok": False,
                "threshold": 75,
            }


async def save_results_to_db(user_id: str, results: list):
    async with AsyncSessionLocal() as session:
        try:
            for r in results:
                # ── Step 1: Check if job already exists in jobs table ──
                existing_job = await session.execute(
                    select(Job).where(Job.apply_url == r.job.apply_url)
                )
                job_row = existing_job.scalar_one_or_none()

                # ── Step 2: If job doesn't exist, insert it first ──
                if job_row is None:
                    job_row = Job(
                        id=uuid.uuid4(),
                        title=r.job.title,
                        company=r.job.company,
                        location=r.job.location,
                        description=r.job.description,
                        salary_range=r.job.salary_range,
                        apply_url=r.job.apply_url,
                        source=r.job.source,
                        posted_date=r.job.posted_date,
                    )
                    session.add(job_row)
                    await session.flush()
                    logger.info("Inserted new job", title=job_row.title, company=job_row.company)
                else:
                    logger.debug("Job already exists", title=job_row.title, company=job_row.company)

                # ── Step 3: Save application row ──
                application = Application(
                    id=uuid.uuid4(),
                    user_id=uuid.UUID(user_id),
                    job_id=job_row.id,
                    match_score=r.score,
                    matched_skills=getattr(r, 'matched_skills', []),
                    missing_skills=getattr(r, 'missing_skills', []),
                    reasoning=r.reason,
                    status="matched",
                    applied_at=datetime.utcnow()
                )
                session.add(application)
                logger.info("Saved application", score=r.score, title=job_row.title)

            await session.commit()
            logger.info("All results saved to database", count=len(results))

        except Exception as e:
            await session.rollback()
            logger.error("DB save failed", error=str(e))
            raise


@celery.task(bind=True)
def run_pipeline_task(self, user_id: str, resume_path: str, locations: list = None):

    # ── Step 0: Fetch user preferences ──
    self.update_state(state="STARTED", meta={"step": "loading_preferences"})
    prefs = asyncio.run(fetch_user_preferences(user_id))

    # Use provided locations, or fall back to preference locations
    effective_locations = locations or prefs["locations"]
    effective_roles = prefs["roles"]

    logger.info(
        "Pipeline starting",
        user_id=user_id,
        roles=effective_roles,
        locations=effective_locations,
        remote_ok=prefs["remote_ok"],
    )

    # ── Step 1: Parse Resume ──
    self.update_state(state="STARTED", meta={"step": "parsing_resume"})
    parser = ResumeParser()
    resume = asyncio.run(parser.parse(resume_path))
    candidate_skills = resume.skills
    logger.info("Resume parsed", skills_count=len(candidate_skills))

    # ── Step 2: Scrape Jobs ──
    self.update_state(state="STARTED", meta={"step": "scraping_jobs"})
    scraper = JobScraper()
    jobs = scraper.scrape_all(
        roles=effective_roles,
        locations=effective_locations,
        num_per_search=DEFAULT_NUM_JOBS
    )

    # ── Step 3: Pre-filter ──
    self.update_state(state="STARTED", meta={"step": "filtering_jobs"})
    pre_filter = PreFilter()
    results = asyncio.run(
        pre_filter.filter_all(jobs, candidate_skills, pref_remote=prefs["remote_ok"])
    )
    passed = [r for r in results if r.passed]
    passed.sort(key=lambda r: r.score, reverse=True)

    # ── Step 4: Save to Database ──
    self.update_state(state="STARTED", meta={"step": "saving_to_database"})
    logger.info("Saving results to database", count=len(passed))
    asyncio.run(save_results_to_db(user_id, passed))

    # ── Step 5: Mark Complete ──
    logger.info("Pipeline complete", user_id=user_id, total_passed=len(passed))
    return {
        "status": "complete",
        "total_passed": len(passed),
        "jobs": [
            {
                "title": r.job.title,
                "company": r.job.company,
                "location": r.job.location,
                "score": r.score,
                "reason": r.reason,
                "url": r.job.apply_url,
            }
            for r in passed
        ]
    }


async def execute_pipeline_task(
    task,
    user_id: str,
    *,
    resume_path: str,
    locations: list = None,
    pipeline_runner=None,
    auto_apply_callable=None,
) -> dict:
    """
    Plain (non-Celery) entry point used by verification scripts and tests.

    Accepts injectable ``pipeline_runner`` and ``auto_apply_callable`` so that
    fake data can be supplied without a real broker or resume file.

    ``task`` must expose an ``update_state(state, meta)`` method (the Celery
    task instance in production, or a :class:`FakeTask` in tests).
    """
    import sys
    import os

    # ── Step 0: Fetch preferences ──────────────────────────────────
    task.update_state(state="STARTED", meta={"step": "loading_preferences"})
    prefs = await fetch_user_preferences(user_id)

    effective_locations = locations or prefs["locations"]
    effective_roles = prefs["roles"]

    logger.info(
        "Pipeline starting (execute_pipeline_task)",
        user_id=user_id,
        roles=effective_roles,
        locations=effective_locations,
    )

    # ── Step 1: Run pipeline (real or injected) ────────────────────
    task.update_state(state="STARTED", meta={"step": "running_pipeline"})
    if pipeline_runner is not None:
        pipeline_result = await pipeline_runner(
                user_id=user_id,
                resume_path=resume_path,
                roles=effective_roles,
                locations=effective_locations,
                prefs=prefs,
            )
    else:
        # Real path: parse resume, scrape, pre-filter
        task.update_state(state="STARTED", meta={"step": "parsing_resume"})
        parser = ResumeParser()
        resume = await parser.parse(resume_path)

        task.update_state(state="STARTED", meta={"step": "scraping_jobs"})
        scraper = JobScraper()
        jobs = scraper.scrape_all(
            roles=effective_roles,
            locations=effective_locations,
            num_per_search=DEFAULT_NUM_JOBS,
        )

        task.update_state(state="STARTED", meta={"step": "filtering_jobs"})
        pre_filter = PreFilter()
        results = await pre_filter.filter_all(jobs, resume.skills, pref_remote=prefs["remote_ok"])
        passed = sorted([r for r in results if r.passed], key=lambda r: r.score, reverse=True)

        pipeline_result = type("R", (), {
            "resume": resume,
            "scored_results": results,
            "passed_results": passed,
            "failed_results": [],
        })()

    passed_results = pipeline_result.passed_results
    threshold = prefs.get("threshold", 75)

    # ── Step 2: Auto-apply (if enabled) ───────────────────────────
    apply_results: list[dict] = []
    if AUTO_APPLY_ENABLED and passed_results:
        task.update_state(state="STARTED", meta={"step": "auto_applying"})
        resume_obj = pipeline_result.resume
        user_data = {
            "name": resume_obj.name,
            "email": resume_obj.email,
            "phone": resume_obj.phone,
            "skills": resume_obj.skills,
        }
        for r in passed_results:
            if r.score < threshold:
                continue
            callable_ = auto_apply_callable
            if callable_ is None:
                from agents.auto_apply import AutoApplier
                # Real auto-apply requires a live Playwright page — skip here
                logger.warning("No auto_apply_callable provided; skipping auto-apply", url=r.job.apply_url)
                continue
            result = callable_(
                job_url=r.job.apply_url,
                user_id=user_id,
                job_id=uuid.uuid4(),
                user_data=user_data,
            )
            apply_results.append({
                "url": r.job.apply_url,
                "success": result.success,
                "manual_apply_url": result.manual_apply_url,
                "failure_reason": result.failure_reason,
            })

    # ── Step 3: Save to DB ────────────────────────────────────────
    task.update_state(state="STARTED", meta={"step": "saving_to_database"})

    # Annotate each result with auto-apply outcome before saving
    apply_map = {a["url"]: a for a in apply_results}
    for r in pipeline_result.scored_results:
        outcome = apply_map.get(r.job.apply_url)
        if outcome:
            r.auto_apply_status = "applied" if outcome["success"] else "failed"
            r.manual_apply_url = outcome.get("manual_apply_url")
        else:
            r.auto_apply_status = None
            r.manual_apply_url = None

    await _save_results_with_status(user_id, pipeline_result.scored_results, threshold)

    logger.info(
        "execute_pipeline_task complete",
        user_id=user_id,
        total_scored=len(pipeline_result.scored_results),
        total_applied=len([a for a in apply_results if a["success"]]),
    )
    return {
        "status": "complete",
        "total_scored": len(pipeline_result.scored_results),
        "apply_results": apply_results,
    }


async def _save_results_with_status(user_id: str, results: list, threshold: float):
    """Persist scored results, setting status based on auto-apply outcome."""
    async with AsyncSessionLocal() as session:
        try:
            for r in results:
                existing_job = await session.execute(
                    select(Job).where(Job.apply_url == r.job.apply_url)
                )
                job_row = existing_job.scalar_one_or_none()

                if job_row is None:
                    job_row = Job(
                        id=uuid.uuid4(),
                        title=r.job.title,
                        company=r.job.company,
                        location=r.job.location,
                        description=r.job.description,
                        salary_range=r.job.salary_range,
                        apply_url=r.job.apply_url,
                        source=r.job.source,
                        posted_date=r.job.posted_date,
                    )
                    session.add(job_row)
                    await session.flush()

                # Determine application status
                auto_status = getattr(r, "auto_apply_status", None)
                if auto_status == "applied":
                    status = "applied"
                elif auto_status == "failed":
                    status = "failed"
                elif r.score >= threshold:
                    status = "matched"
                else:
                    status = "matched"

                # Skip duplicate application rows for the same user+job
                existing_app = await session.execute(
                    select(Application).where(
                        Application.user_id == uuid.UUID(user_id),
                        Application.job_id == job_row.id,
                    )
                )
                if existing_app.scalar_one_or_none() is not None:
                    logger.debug("Application already exists, skipping", title=job_row.title)
                    continue

                application = Application(
                    id=uuid.uuid4(),
                    user_id=uuid.UUID(user_id),
                    job_id=job_row.id,
                    match_score=r.score,
                    matched_skills=getattr(r, "matched_skills", []),
                    missing_skills=getattr(r, "missing_skills", []),
                    reasoning=r.reason,
                    status=status,
                    manual_apply_url=getattr(r, "manual_apply_url", None),
                    applied_at=datetime.utcnow(),
                )
                session.add(application)
                logger.info("Saved application", score=r.score, title=job_row.title, status=status)

            await session.commit()
            logger.info("Results saved", count=len(results))
        except Exception as e:
            await session.rollback()
            logger.error("DB save failed", error=str(e))
            raise