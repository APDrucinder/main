import asyncio
from celery_app import celery
from agents.job_scraper import JobScraper
from agents.pre_filter import PreFilter
from agents.resume_parser import ResumeParser
ROLES = ["software engineer", "python developer", "backend developer"]
NUM_JOBS = 10
@celery.task(bind=True)
def run_pipeline_task(self, resume_path, locations):
    self.update_state(state="STARTED",meta={"step":"parsing_resume"})
    parser=ResumeParser()
    resume=asyncio.run(parser.parse(resume_path))
    candidate_skills=resume.skills
    
    self.update_state(state="STARTED",meta={"step":"scraping_jobs"})
    scraper=JobScraper()
    jobs=scraper.scrape_all(
        roles=ROLES,
        locations=locations,
        num_per_search=NUM_JOBS
    )

    self.update_state(state="STARTED",meta={"step":"filtering_jobs"})
    pre_filter=PreFilter()
    results=asyncio.run(pre_filter.filter_all(jobs,candidate_skills))
    passed=[r for r in results if r.passed]
    passed.sort(key=lambda r:r.score,reverse=True)
    

    #SPARSH'S PART LEFT HERE


    return {
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
    
