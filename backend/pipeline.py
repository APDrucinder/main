import asyncio
import sys
import os

sys.path.append(os.path.dirname(__file__))
from agents.job_scraper import JobScraper
from agents.pre_filter import PreFilter
from agents.resume_parser import ResumeParser
from shared.logger import logger

# ─── CONFIG — edit these ───────────────────────────────────────
ROLES       = ["software engineer", "python developer", "backend developer"]
NUM_JOBS    = 10  # per role per location per platform
RESUME_PATH = "Dhruv_Resume.pdf"
# ───────────────────────────────────────────────────────────────

async def run_pipeline():
    logger.info("=" * 60)
    logger.info("JOB PIPELINE — PARSE → SCRAPE → FILTER")
    logger.info("=" * 60)

    # ---------------------------------------------------------
    # STEP 0 — Parse Resume
    # ---------------------------------------------------------
    logger.info("STEP 0: Parsing resume", path=RESUME_PATH)
    parser = ResumeParser()
    try:
        resume = await parser.parse(RESUME_PATH)
        candidate_skills = resume.skills
        logger.info("Resume parsed", skills_count=len(candidate_skills), skills=", ".join(candidate_skills))
    except Exception as e:
        logger.error("Failed to parse resume, exiting", error=str(e))
        return

    # ---------------------------------------------------------
    # LOCATION SETUP
    # ---------------------------------------------------------
    logger.info("LOCATION SETUP")
    loc_input = input("Enter locations separated by commas (or press Enter for default 'Bangalore, Mumbai'): ")
    if loc_input.strip():
        locations = [loc.strip() for loc in loc_input.split(',')]
    else:
        locations = ["Bangalore", "Mumbai"]

    # ---------------------------------------------------------
    # Step 1 — Scrape
    # ---------------------------------------------------------
    logger.info("STEP 1: Scraping jobs", locations=locations)
    scraper = JobScraper()
    jobs = scraper.scrape_all(
        roles=ROLES,
        locations=locations,
        num_per_search=NUM_JOBS
    )

    if not jobs:
        logger.warning("No jobs found. Exiting.")
        return

    # ---------------------------------------------------------
    # Step 2 — Pre-filter
    # ---------------------------------------------------------
    logger.info("STEP 2: Pre-filtering jobs with LLM")
    pre_filter = PreFilter()
    results = await pre_filter.filter_all(jobs, candidate_skills)

    # ---------------------------------------------------------
    # Step 3 — Show final results
    # ---------------------------------------------------------
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    logger.info("Pipeline results", passed=len(passed), failed=len(failed))

    if passed:
        passed.sort(key=lambda r: r.score, reverse=True)

        logger.info("TOP MATCHES:")
        for r in passed:
            is_remote = getattr(r.job, 'is_remote', None)
            if is_remote is True:
                work_method = "Remote"
            elif is_remote is False:
                work_method = "On-site / Hybrid"
            else:
                work_method = getattr(r.job, 'job_type', 'Not specified')

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

if __name__ == "__main__":
    asyncio.run(run_pipeline())