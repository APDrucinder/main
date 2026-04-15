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