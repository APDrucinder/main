import asyncio
import sys
import os

sys.path.append(os.path.dirname(__file__))
from agents.job_scraper import JobScraper
from agents.pre_filter import PreFilter
from agents.resume_parser import ResumeParser  # <-- NEW IMPORT

# ─── CONFIG — edit these ───────────────────────────────────────
ROLES       = ["software engineer", "python developer", "backend developer"]
NUM_JOBS    = 10  # per role per location per platform
RESUME_PATH = "Dhruv_Resume.pdf" # <-- Make sure this matches your file
# ───────────────────────────────────────────────────────────────

async def run_pipeline():
    print("=" * 60)
    print("      JOB PIPELINE — PARSE → SCRAPE → FILTER")
    print("=" * 60)

    # ---------------------------------------------------------
    # NEW STEP 0 — Parse Resume
    # ---------------------------------------------------------
    print(f"\n📄 STEP 0: Parsing resume ({RESUME_PATH})...")
    parser = ResumeParser()
    try:
        resume = await parser.parse(RESUME_PATH)
        candidate_skills = resume.skills
        print(f"  → Found {len(candidate_skills)} skills: {', '.join(candidate_skills)}")
    except Exception as e:
        print(f"Failed to parse resume. Exiting.\nError: {e}")
        return

    # ---------------------------------------------------------
    # LOCATION SETUP
    # ---------------------------------------------------------
    print("\n🌍 LOCATION SETUP")
    loc_input = input("Enter locations separated by commas (or press Enter for default 'Bangalore, Mumbai'): ")
    if loc_input.strip():
        locations = [loc.strip() for loc in loc_input.split(',')]
    else:
        locations = ["Bangalore", "Mumbai"]

    # ---------------------------------------------------------
    # Step 1 — Scrape
    # ---------------------------------------------------------
    print(f"\n📥 STEP 1: Scraping jobs in {', '.join(locations)}...")
    scraper = JobScraper()
    jobs = scraper.scrape_all(
        roles=ROLES,
        locations=locations,
        num_per_search=NUM_JOBS
    )

    if not jobs:
        print("No jobs found. Exiting.")
        return

    # ---------------------------------------------------------
    # Step 2 — Pre-filter
    # ---------------------------------------------------------
    print("\n🔍 STEP 2: Pre-filtering jobs with LLM...")
    pre_filter = PreFilter()
    
    # NEW: Feeding your real extracted skills to the filter
    results = await pre_filter.filter_all(jobs, candidate_skills)

    # ---------------------------------------------------------
    # Step 3 — Show final results
    # ---------------------------------------------------------
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
            
            # Safely determine the work method (Remote vs On-site)
            is_remote = getattr(r.job, 'is_remote', None)
            if is_remote is True:
                work_method = "Remote"
            elif is_remote is False:
                work_method = "On-site / Hybrid"
            else:
                work_method = getattr(r.job, 'job_type', 'Not specified')

            print(f"  Score:    {r.score}/100")
            print(f"  Title:    {r.job.title}")
            print(f"  Company:  {r.job.company}")
            print(f"  Location: {r.job.location}")
            print(f"  Method:   {work_method}") 
            print(f"  Source:   {r.job.source}")
            print(f"  Reason:   {r.reason}")
            print(f"  URL:      {r.job.apply_url}")
            print("-" * 60)

if __name__ == "__main__":
    asyncio.run(run_pipeline())