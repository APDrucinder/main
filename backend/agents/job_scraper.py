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
    is_remote: bool = False          # FIX: Added remote indicator
    description: str
    salary_range: Optional[str] = None
    experience_required: Optional[str] = None 
    apply_url: str
    source: str
    posted_date: Optional[datetime] = None

class JobScraper(BaseAgent):
    
    def __init__(self):
        super().__init__("job_scraper")
    
    def scrape_indeed(self, role: str, location: str, num_results: int = 30, remote_only: bool = False) -> List[JobPosting]:
        try:
            jobs = scrape_jobs(
                site_name=["indeed"],
                search_term=role,
                location=location,
                results_wanted=num_results,
                country_indeed="India",
                hours_old=72,
                is_remote=remote_only  # FIX: Added ability to filter by remote strictly
            )
            if jobs is None or jobs.empty:
                print(f"  → No results for '{role}' in '{location}'")
                return []
            print(f"  → Got {len(jobs)} jobs for '{role}' in '{location}'")
            return self._parse_results(jobs, "indeed")
        except Exception as e:
            print(f"Indeed scraping failed: {e}")
            return []
    
    def _parse_results(self, df, source: str) -> List[JobPosting]:
        jobs = []
        
        for _, row in df.iterrows():
            try:
                # Build salary string from min/max amount
                salary = None
                if pd.notna(row.get('min_amount')) and pd.notna(row.get('max_amount')):
                    salary = f"{row['min_amount']} - {row['max_amount']} {row.get('currency', '')}"
                elif pd.notna(row.get('min_amount')):
                    salary = f"{row['min_amount']} {row.get('currency', '')}"

                # Handle pandas NaT/NaN for dates
                raw_date = row.get('date_posted')
                clean_date = raw_date if pd.notna(raw_date) else None

                # Handle pandas NaN for booleans
                raw_remote = row.get('is_remote')
                is_remote = bool(raw_remote) if pd.notna(raw_remote) else False

                job = JobPosting(
                    title=str(row.get('title', '')),
                    company=str(row.get('company', '')),
                    location=str(row.get('location', '')),
                    is_remote=is_remote,  # FIX: Populate remote status
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
    
    def scrape_all(self, roles: List[str], locations: List[str], num_per_search: int = 20, remote_only: bool = False) -> List[JobPosting]:
        all_jobs = []
        seen_urls = set()
        
        for role in roles:
            for location in locations:
                mode = "Remote" if remote_only else "On-site/Hybrid/Remote"
                print(f"Scraping ({mode}): {role} in {location}")
                jobs = self.scrape_indeed(role, location, num_per_search, remote_only)
                for job in jobs:
                    if job.apply_url not in seen_urls:
                        seen_urls.add(job.apply_url)
                        all_jobs.append(job)
        
        print(f"\nTotal unique jobs found: {len(all_jobs)}")
        return all_jobs


if __name__ == "__main__":
    scraper = JobScraper()
    
    # FIX: Interactive location selection
    print("=== Job Scraper ===")
    user_location = input("Enter a location to search (e.g., Bangalore, Delhi, Pune): ").strip()
    user_remote = input("Do you want ONLY remote jobs? (y/n): ").strip().lower() == 'y'
    
    # Use the input or fallback to a default if they just press Enter
    locations_to_search = [user_location] if user_location else ["Bangalore", "Mumbai"]

    jobs = scraper.scrape_all(
        roles=["software engineer", "python developer"],
        locations=locations_to_search,
        num_per_search=10,
        remote_only=user_remote
    )
    
    for job in jobs[:5]:
        # Format remote indicator nicely for terminal
        remote_badge = "[REMOTE]" if job.is_remote else "[ON-SITE/HYBRID]"
        
        print(f"\nTitle:       {job.title} {remote_badge}")
        print(f"Company:     {job.company}")
        print(f"Location:    {job.location}")
        print(f"Salary:      {job.salary_range}")
        print(f"Experience:  {job.experience_required}")
        print(f"Posted:      {job.posted_date}")
        print(f"URL:         {job.apply_url}")
        print(f"Description:\n{job.description[:300]}...")
        print("-" * 60)