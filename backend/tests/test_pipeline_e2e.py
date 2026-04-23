import sys
import os
import asyncio
import json
from datetime import datetime
from agents.pipeline import JobApplicationPipeline
from agents.pre_filter import UserPreferences
from database.connection import AsyncSessionLocal
from database.models import Application, Job
from sqlalchemy import select

# ============================================
# CONFIGURE THIS BEFORE RUNNING
# ============================================
TEST_RESUME_PATH = "test_resume.pdf"
# Put your actual resume here

TEST_PREFERENCES = UserPreferences(
    target_roles=["software engineer", 
                  "python developer",
                  "backend developer"],
    locations=["Bangalore"],
    experience_years=2,
    salary_min=500000,
    remote_ok=True,
    auto_apply_threshold=75
)

TEST_USER_ID = "test-user-123"
# ============================================

async def test_full_pipeline():
    
    print("\n" + "="*60)
    print("FULL PIPELINE END TO END TEST")
    print(f"Started at: {datetime.now()}")
    print("="*60 + "\n")
    
    results = {
        "resume_parsed": False,
        "jobs_scraped": 0,
        "jobs_after_filter": 0,
        "jobs_scored": 0,
        "auto_applied": 0,
        "apply_failed": 0,
        "errors": []
    }
    
    try:
        # Step 1: Test resume parsing alone
        print("TEST 1: Resume Parser")
        print("-" * 40)
        
        from agents.resume_parser import ResumeParser
        parser = ResumeParser()
        resume = await parser.parse(TEST_RESUME_PATH)
        
        assert resume.name, "Name not parsed"
        assert resume.email, "Email not parsed"
        assert len(resume.skills) > 0, "No skills parsed"
        
        results["resume_parsed"] = True
        print(f"✅ Resume parsed successfully")
        print(f"   Name: {resume.name}")
        print(f"   Skills: {len(resume.skills)} found")
        print(f"   Experience: "
              f"{resume.total_experience_years} years\n")
        
        # Step 2: Test scraper alone
        print("TEST 2: Job Scraper")
        print("-" * 40)
        
        from agents.job_scraper import JobScraper
        scraper = JobScraper()
        jobs = scraper.scrape_all(
            roles=["software engineer"],
            locations=["Bangalore"],
            num_per_search=10
        )
        
        assert len(jobs) > 0, "No jobs scraped"
        results["jobs_scraped"] = len(jobs)
        
        print(f"✅ Scraped {len(jobs)} jobs")
        print(f"   Indeed: "
              f"{sum(1 for j in jobs if j.source == 'indeed')}")
        print(f"   Internshala: "
              f"{sum(1 for j in jobs if j.source == 'internshala')}\n")
        
        # Step 3: Test pre filter
        print("TEST 3: Pre Filter")
        print("-" * 40)
        
        from agents.pre_filter import keyword_prefilter
        filtered = [
            j for j in jobs
            if keyword_prefilter(j, resume, TEST_PREFERENCES)
        ]
        
        results["jobs_after_filter"] = len(filtered)
        rejected = len(jobs) - len(filtered)
        
        print(f"✅ Pre filter complete")
        print(f"   Passed: {len(filtered)}")
        print(f"   Rejected: {rejected}\n")
        
        # Step 4: Test scorer on 3 jobs only
        print("TEST 4: LLM Scorer (3 jobs only for cost)")
        print("-" * 40)
        
        from agents.job_scorer import JobScorer
        scorer = JobScorer(apply_threshold=75)
        
        test_jobs = filtered[:3]
        scored = await scorer.score_batch(
            resume=resume,
            jobs=test_jobs,
            max_jobs=3
        )
        
        results["jobs_scored"] = len(scored)
        
        print(f"✅ Scoring complete")
        for job, score in scored:
            print(f"   {score.score}/100 — "
                  f"{job.title} at {job.company}")
            print(f"   Should apply: {score.should_apply}")
            print(f"   Matched: "
                  f"{', '.join(score.matched_skills[:3])}")
            print(f"   Missing: "
                  f"{', '.join(score.missing_skills[:3])}")
        print()
        
        # Step 5: Test auto apply on ONE job only
        print("TEST 5: Auto Apply (1 job only)")
        print("-" * 40)
        
        apply_candidates = [
            (job, score) for job, score in scored
            if score.should_apply
        ]
        
        if apply_candidates:
            test_job, test_score = apply_candidates[0]
            print(f"Testing apply on: {test_job.title} "
                  f"at {test_job.company}")
            
            from agents.apply_with_retry import safe_apply
            
            apply_result = await safe_apply(
                job=test_job,
                resume_path=TEST_RESUME_PATH
            )
            
            if apply_result["success"]:
                results["auto_applied"] += 1
                print(f"✅ Application submitted successfully")
            else:
                results["apply_failed"] += 1
                print(f"⚠️  Apply failed: "
                      f"{apply_result['reason']}")
                print(f"   Manual URL: "
                      f"{apply_result.get('manual_apply_url')}")
        else:
            print("⚠️  No jobs above threshold "
                  "for auto apply test")
        
        print()
        
        # Step 6: Test database saving
        print("TEST 6: Database Saving")
        print("-" * 40)
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Application)
                .where(
                    Application.user_id == TEST_USER_ID
                )
                .order_by(Application.applied_at.desc())
                .limit(5)
            )
            recent_apps = result.scalars().all()
            
            print(f"✅ Found {len(recent_apps)} recent "
                  f"applications in database")
            for app in recent_apps:
                print(f"   Score: {app.match_score} — "
                      f"Status: {app.status}")
        
        print()
        
    except AssertionError as e:
        results["errors"].append(f"Assertion failed: {str(e)}")
        print(f"❌ Test failed: {str(e)}")
        
    except Exception as e:
        results["errors"].append(f"Unexpected error: {str(e)}")
        print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Final report
    print("="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    print(f"Resume parsed:        "
          f"{'✅' if results['resume_parsed'] else '❌'}")
    print(f"Jobs scraped:         {results['jobs_scraped']}")
    print(f"After filter:         {results['jobs_after_filter']}")
    print(f"Jobs scored:          {results['jobs_scored']}")
    print(f"Auto applied:         {results['auto_applied']}")
    print(f"Apply failed:         {results['apply_failed']}")
    
    if results["errors"]:
        print(f"\nErrors:")
        for error in results["errors"]:
            print(f"  ❌ {error}")
    else:
        print(f"\n✅ All tests passed")
    
    print("="*60)
    print(f"Finished at: {datetime.now()}")
    
    return results

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())