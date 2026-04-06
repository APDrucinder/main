# backend/agents/job_scraper.py

from jobspy import scrape_jobs
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from shared.base_agent import BaseAgent

class JobPosting(BaseModel):
    title: str
    company: str
    location: str
    description: str
    salary_range: Optional[str] = None
    apply_url: str
    source: str
    posted_date: Optional[datetime] = None

class JobScraper(BaseAgent):
    
    def __init__(self):
        super().__init__("job_scraper")
    
    def scrape_indeed(self, role: str, location: str, num_results: int = 30) -> List[JobPosting]:
        try:
            jobs = scrape_jobs(
                site_name=["indeed"],
                search_term=role,
                location=location,
                results_wanted=num_results,
                country_indeed="India",
                hours_old=72
            )
            if jobs is None or jobs.empty:
                print(f"  → No results for '{role}' in '{location}'")
                return []
            print(f"  → Got {len(jobs)} jobs for '{role}' in '{location}'")
            return self._parse_results(jobs, "indeed")
        except Exception as e:
            print(f"Indeed scraping failed: {e}")
            return []
    
    def _parse_results(self, df: pd.DataFrame, source: str) -> List[JobPosting]:
        jobs = []
        for _, row in df.iterrows():
            try:
                salary = str(row.get("min_amount", "")).strip()
                jobs.append(JobPosting(
                    title=str(row.get("title", "")),
                    company=str(row.get("company", "")),
                    location=str(row.get("location", "")),
                    description=str(row.get("description", ""))[:2000],
                    salary_range=salary if salary and salary != "nan" else None,
                    apply_url=str(row.get("job_url", "")),
                    source=source,
                    posted_date=row.get("date_posted")
                ))
            except Exception as e:
                print(f"Skipping malformed job: {e}")
                continue
        return jobs
    
    def scrape_all(self, roles: List[str], locations: List[str], num_per_search: int = 20) -> List[JobPosting]:
        all_jobs = []
        seen_urls = set()
        
        for role in roles:
            for location in locations:
                print(f"Scraping: {role} in {location}")
                jobs = self.scrape_indeed(role, location, num_per_search)
                for job in jobs:
                    if job.apply_url not in seen_urls:
                        seen_urls.add(job.apply_url)
                        all_jobs.append(job)
        
        print(f"\nTotal unique jobs found: {len(all_jobs)}")
        return all_jobs


if __name__ == "__main__":
    scraper = JobScraper()
    
    jobs = scraper.scrape_all(
        roles=["software engineer", "python developer"],
        locations=["Bangalore", "Mumbai"],
        num_per_search=10
    )
    
    for job in jobs[:3]:
        print(f"\nTitle: {job.title}")
        print(f"Company: {job.company}")
        print(f"Location: {job.location}")
        print(f"URL: {job.apply_url}")
        print("---")