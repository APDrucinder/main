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
    
    def scrape_all(self, roles: List[str], locations: List[str], num_per_search: int = 20) -> List[JobPosting]:
        all_jobs = []
        seen_urls = set()
        
        # Dropped Naukri to avoid bot blocks. Sticking to the most reliable two.
        target_sites = ["indeed", "linkedin"]
        
        for role in roles:
            for loc in locations:
                
                # 🚀 THE LINKEDIN FIX:
                # We dynamically ensure ", India" is attached to the location string here 
                # so LinkedIn stops routing you to Ohio!
                clean_loc = loc.strip()
                search_location = clean_loc if "india" in clean_loc.lower() else f"{clean_loc}, India"
                
                print(f"\nScraping {', '.join(target_sites).title()} for: '{role}' in '{search_location}'")
                
                try:
                    df = scrape_jobs(
                        site_name=target_sites,
                        search_term=role,
                        location=search_location, # Passing the explicit country string
                        results_wanted=num_per_search,
                        country_indeed="India",   # Indeed still requires this explicit flag
                        hours_old=72
                    )
                    
                    if df is None or df.empty:
                        print(f"  → No results found.")
                        continue
                        
                    print(f"  → Found {len(df)} total jobs!")
                    
                    parsed_jobs = self._parse_results(df)
                    
                    for job in parsed_jobs:
                        if job.apply_url not in seen_urls:
                            seen_urls.add(job.apply_url)
                            all_jobs.append(job)
                            
                except Exception as e:
                    print(f"Scraping failed for {role} in {search_location}: {e}")
                    
        print(f"\nTotal unique jobs found: {len(all_jobs)}")
        return all_jobs

    def _parse_results(self, df) -> List[JobPosting]:
        jobs = []
        for _, row in df.iterrows():
            try:
                salary = None
                if pd.notna(row.get('min_amount')) and pd.notna(row.get('max_amount')):
                    salary = f"{row['min_amount']} - {row['max_amount']} {row.get('currency', 'INR')}"
                elif pd.notna(row.get('min_amount')):
                    salary = f"{row['min_amount']} {row.get('currency', 'INR')}"

                raw_date = row.get('date_posted')
                clean_date = raw_date if pd.notna(raw_date) else None
                
                source_site = str(row.get('site', 'unknown'))

                job = JobPosting(
                    title=str(row.get('title', '')),
                    company=str(row.get('company', '')),
                    location=str(row.get('location', '')),
                    description=str(row.get('description', '')),
                    salary_range=salary,
                    experience_required=str(row.get('job_level', 'Not Specified')),
                    apply_url=str(row.get('job_url', '')),
                    source=source_site, 
                    posted_date=clean_date,
                    is_remote=bool(row.get('is_remote', False))
                )
                jobs.append(job)
            except Exception as e:
                print(f"Skipping malformed job: {e}")
                continue
        return jobs