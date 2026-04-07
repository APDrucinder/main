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
    experience_required: Optional[str] = None
    apply_url: str
    source: str
    posted_date: Optional[datetime] = None
    is_remote: Optional[bool] = False

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
            print(f"  → Got {len(jobs)} indeed jobs for '{role}' in '{location}'")
            return self._parse_results(jobs, "indeed")
        except Exception as e:
            print(f"Indeed scraping failed: {e}")
            return []

    def scrape_linkedin(self, role: str, location: str, num_results: int = 30) -> List[JobPosting]:
        try:
            jobs = scrape_jobs(
                site_name=["linkedin"],
                search_term=role,
                location=location,
                results_wanted=num_results,
                hours_old=72
            )
            if jobs is None or jobs.empty:
                print(f"  → No LinkedIn results for '{role}' in '{location}'")
                return []
            print(f"  → Got {len(jobs)} linkedin jobs for '{role}' in '{location}'")
            return self._parse_results(jobs, "linkedin")
        except Exception as e:
            print(f"LinkedIn scraping failed: {e}")
            return []
    
    def _parse_results(self, df, source: str) -> List[JobPosting]:
        jobs = []
        for _, row in df.iterrows():
            try:
                salary = None
                if pd.notna(row.get('min_amount')) and pd.notna(row.get('max_amount')):
                    salary = f"{row['min_amount']} - {row['max_amount']} {row.get('currency', '')}"
                elif pd.notna(row.get('min_amount')):
                    salary = f"{row['min_amount']} {row.get('currency', '')}"

                raw_date = row.get('date_posted')
                clean_date = raw_date if pd.notna(raw_date) else None

                job = JobPosting(
                    title=str(row.get('title', '')),
                    company=str(row.get('company', '')),
                    location=str(row.get('location', '')),
                    description=str(row.get('description', '')),
                    salary_range=salary,
                    experience_required=str(row.get('job_level', 'Not Specified')),
                    apply_url=str(row.get('job_url', '')),
                    source=source,
                    posted_date=clean_date
                )
                jobs.append(job)
            except Exception as e:
                print(f"Skipping malformed job: {e}")
                continue
        return jobs
    
    def scrape_all(self, roles: List[str], locations: List[str], num_per_search: int = 20) -> List[JobPosting]:
        all_jobs = []
        seen_urls = set()
        
        for role in roles:
            for location in locations:
                print(f"\nScraping Indeed: {role} in {location}")
                for job in self.scrape_indeed(role, location, num_per_search):
                    if job.apply_url not in seen_urls:
                        seen_urls.add(job.apply_url)
                        all_jobs.append(job)

                print(f"Scraping LinkedIn: {role} in {location}")
                for job in self.scrape_linkedin(role, location, num_per_search):
                    if job.apply_url not in seen_urls:
                        seen_urls.add(job.apply_url)
                        all_jobs.append(job)
        
        print(f"\nTotal unique jobs found: {len(all_jobs)}")
        return all_jobs