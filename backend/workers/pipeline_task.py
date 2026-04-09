import asyncio
from celery_app import celery
from agents.job_scraper import JobScraper
from agents.pre_filter import PreFilter
from agents.resume_parser import ResumeParser
from database.connection import AsyncSessionLocal
from database.models import Job, Application
from sqlalchemy import select
import uuid
from datetime import datetime

ROLES = ["software engineer", "python developer", "backend developer"]
NUM_JOBS = 10

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
                    await session.flush()  # gives job_row.id without full commit
                    print(f"  → Inserted new job: {job_row.title} at {job_row.company}")
                else:
                    print(f"  → Job already exists: {job_row.title} at {job_row.company}")

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
                print(f"  → Saved application: score={r.score} for {job_row.title}")

            await session.commit()
            print(f"\n✅ All results saved to database.")

        except Exception as e:
            await session.rollback()
            print(f"❌ DB save failed: {e}")
            raise


@celery.task(bind=True)
def run_pipeline_task(self, user_id: str, resume_path: str, locations: list):

    # ── Step 0: Parse Resume ──
    self.update_state(state="STARTED", meta={"step": "parsing_resume"})
    parser = ResumeParser()
    resume = asyncio.run(parser.parse(resume_path))
    candidate_skills = resume.skills
    print(f"  → Parsed {len(candidate_skills)} skills")

    # ── Step 1: Scrape Jobs ──
    self.update_state(state="STARTED", meta={"step": "scraping_jobs"})
    scraper = JobScraper()
    jobs = scraper.scrape_all(
        roles=ROLES,
        locations=locations,
        num_per_search=NUM_JOBS
    )

    # ── Step 2: Pre-filter ──
    self.update_state(state="STARTED", meta={"step": "filtering_jobs"})
    pre_filter = PreFilter()
    results = asyncio.run(pre_filter.filter_all(jobs, candidate_skills))
    passed = [r for r in results if r.passed]
    passed.sort(key=lambda r: r.score, reverse=True)

    # ── Step 3: Save to Database ──
    self.update_state(state="STARTED", meta={"step": "saving_to_database"})
    print(f"\n💾 STEP 3: Saving {len(passed)} results to database...")
    asyncio.run(save_results_to_db(user_id, passed))

    # ── Step 4: Mark Complete ──
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