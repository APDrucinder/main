import asyncio
import sys
import os

sys.path.append(os.path.dirname(__file__))
from agents.job_scraper import JobScraper
from agents.pre_filter import PreFilter

# ─── CONFIG — edit these ───────────────────────────────────────
ROLES     = ["software engineer", "python developer", "backend developer"]
LOCATIONS = ["Bangalore", "Mumbai"]
NUM_JOBS  = 10  # per role per location per platform

CANDIDATE_SKILLS = [
    "Python", "FastAPI", "React", "PostgreSQL",
    "REST APIs", "Git", "Docker"
]
# ───────────────────────────────────────────────────────────────

async def run_pipeline():
    print("=" * 60)
    print("       JOB PIPELINE — SCRAPE → FILTER")
    print("=" * 60)

    # Step 1 — Scrape
    print("\n📥 STEP 1: Scraping jobs...")
    scraper = JobScraper()
    jobs = scraper.scrape_all(
        roles=ROLES,
        locations=LOCATIONS,
        num_per_search=NUM_JOBS
    )

    if not jobs:
        print("No jobs found. Exiting.")
        return

    # Step 2 — Pre-filter
    print("\n🔍 STEP 2: Pre-filtering jobs with LLM...")
    pre_filter = PreFilter()
    results = await pre_filter.filter_all(jobs, CANDIDATE_SKILLS)

    # Step 3 — Show final results
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    print("\n" + "=" * 60)
    print(f"  ✅ PASSED: {len(passed)} jobs")
    print(f"  ❌ FAILED: {len(failed)} jobs")
    print("=" * 60)

    if passed:
        # Sort by score descending
        passed.sort(key=lambda r: r.score, reverse=True)

        print("\n🏆 TOP MATCHES:\n")
        for r in passed:
            print(f"  Score:    {r.score}/100")
            print(f"  Title:    {r.job.title}")
            print(f"  Company:  {r.job.company}")
            print(f"  Location: {r.job.location}")
            print(f"  Source:   {r.job.source}")
            print(f"  Reason:   {r.reason}")
            print(f"  URL:      {r.job.apply_url}")
            print("-" * 60)

if __name__ == "__main__":
    asyncio.run(run_pipeline())