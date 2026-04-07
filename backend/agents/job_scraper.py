from jobspy import scrape_jobs
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import pandas as pd
import sys
import os
import time # Added for small delays

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
        
        # 🟢 ADDED: 'naukri' is now back in the mix!
        target_sites = ["indeed", "linkedin", "naukri"]
        
        for role in roles:
            for loc in locations:
                
                # 🌍 THE LOCATION FIX:
                # Ensures we stay in India and don't end up scraping "Delhi, NY"
                clean_loc = loc.strip()
                search_location = clean_loc if "india" in clean_loc.lower() else f"{clean_loc}, India"
                
                print(f"\n🚀 Scraping {', '.join(target_sites).title()} for: '{role}'")
                print(f"📍 Location: '{search_location}'")
                
                try:
                    # Note: jobspy handles the internal logic for different sites
                    df = scrape_jobs(
                        site_name=target_sites,
                        search_term=role,
                        location=search_location, 
                        results_wanted=num_per_search,
                        country_indeed="India",   # Specifically helps Indeed's routing
                        hours_old=72,
                        # Adding a proxy here would be ideal for Naukri, 
                        # but we'll stick to direct requests for now.
                    )
                    
                    if df is None or df.empty:
                        print(f"  → No results found for this combination.")
                        continue
                        
                    print(f"  → Found {len(df)} total jobs!")
                    
                    parsed_jobs = self._parse_results(df)
                    
                    for job in parsed_jobs:
                        # Prevent duplicates across different platforms
                        if job.apply_url not in seen_urls:
                            seen_urls.add(job.apply_url)
                            all_jobs.append(job)
                            
                except Exception as e:
                    # If one site (like Naukri) fails, this prevents the whole loop from dying
                    print(f"⚠️ Scraping encounterd an issue for {role}: {e}")
                
                # Be a "polite" scraper to avoid IP bans
                time.sleep(1)
                    
        print(f"\n✅ Total unique jobs gathered: {len(all_jobs)}")
        return all_jobs

    def _parse_results(self, df) -> List[JobPosting]:
        jobs = []
        for _, row in df.iterrows():
            try:
                # Better Salary Handling
                salary = None
                min_amt = row.get('min_amount')
                max_amt = row.get('max_amount')
                currency = row.get('currency', 'INR')

                if pd.notna(min_amt) and pd.notna(max_amt):
                    salary = f"{min_amt} - {max_amt} {currency}"
                elif pd.notna(min_amt):
                    salary = f"{min_amt}+ {currency}"

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
                # Log malformed rows but don't stop the scraper
                continue
        return jobs