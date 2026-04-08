import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time
import random
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

    def _scrape_naukri_stealth(self, role: str, location: str) -> List[JobPosting]:
        """Specialized stealth scraper for Naukri using undetected-chromedriver."""
        print(f"🕵️ Launching Stealth Browser for Naukri: {role} in {location}...")
        
        options = uc.ChromeOptions()
        options.add_argument('--headless') 
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        # 🚀 VERSION FIX: Pinning to 146 to match your MacBook's Chrome version
        try:
            driver = uc.Chrome(options=options, version_main=146)
        except Exception as e:
            print(f"❌ Failed to initialize Stealth Driver: {e}")
            return []

        naukri_jobs = []

        try:
            # Format: naukri.com/role-jobs-in-location
            formatted_role = role.lower().replace(" ", "-")
            formatted_loc = location.lower().replace(" ", "-")
            url = f"https://www.naukri.com/{formatted_role}-jobs-in-{formatted_loc}"
            
            driver.get(url)
            # Human-like wait to bypass initial bot check
            time.sleep(random.uniform(5, 8)) 
            
            # Scroll to trigger lazy loading of job cards
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            # Selector for Naukri's job card container
            job_cards = soup.find_all('div', class_='srp-jobtuple-wrapper')

            for card in job_cards:
                title_tag = card.find('a', class_='title')
                comp_tag = card.find('a', class_='comp-name')
                
                if title_tag and comp_tag:
                    naukri_jobs.append(JobPosting(
                        title=title_tag.text.strip(),
                        company=comp_tag.text.strip(),
                        location=location,
                        description="Naukri listing (Scraped via Stealth Browser)",
                        apply_url=title_tag['href'],
                        source="naukri",
                        is_remote="remote" in card.text.lower()
                    ))
        except Exception as e:
            print(f"⚠️ Naukri scraping failed: {e}")
        finally:
            driver.quit()
            
        return naukri_jobs
    
    def scrape_all(self, roles: List[str], locations: List[str], num_per_search: int = 20) -> List[JobPosting]:
        all_jobs = []
        seen_urls = set()
        
        # Stick to the reliable JobSpy targets
        jobspy_sites = ["indeed", "linkedin"]
        
        for role in roles:
            for loc in locations:
                # 1. Clean location for LinkedIn/Indeed to avoid US results
                clean_loc = loc.strip()
                search_location = clean_loc if "india" in clean_loc.lower() else f"{clean_loc}, India"
                
                # --- PHASE 1: JobSpy (Indeed/LinkedIn) ---
                print(f"\n📥 Scraping {', '.join(jobspy_sites).title()} for: '{role}' in '{search_location}'")
                try:
                    df = scrape_jobs(
                        site_name=jobspy_sites,
                        search_term=role,
                        location=search_location,
                        results_wanted=num_per_search,
                        country_indeed="India",
                        hours_old=72
                    )
                    
                    if df is not None and not df.empty:
                        parsed = self._parse_results(df)
                        for job in parsed:
                            if job.apply_url not in seen_urls:
                                seen_urls.add(job.apply_url)
                                all_jobs.append(job)
                except Exception as e:
                    print(f"❌ JobSpy failed: {e}")

                # --- PHASE 2: Stealth Naukri (Selenium) ---
                naukri_results = self._scrape_naukri_stealth(role, clean_loc)
                for job in naukri_results:
                    if job.apply_url not in seen_urls:
                        seen_urls.add(job.apply_url)
                        all_jobs.append(job)
        
        print(f"\n✨ Total unique jobs found: {len(all_jobs)}")
        return all_jobs

    def _parse_results(self, df) -> List[JobPosting]:
        jobs = []
        for _, row in df.iterrows():
            try:
                salary = None
                if pd.notna(row.get('min_amount')) and pd.notna(row.get('max_amount')):
                    salary = f"{row['min_amount']} - {row['max_amount']} {row.get('currency', 'INR')}"
                
                job = JobPosting(
                    title=str(row.get('title', '')),
                    company=str(row.get('company', '')),
                    location=str(row.get('location', '')),
                    description=str(row.get('description', '')),
                    salary_range=salary,
                    experience_required=str(row.get('job_level', 'Not Specified')),
                    apply_url=str(row.get('job_url', '')),
                    source=str(row.get('site', 'unknown')), 
                    posted_date=row.get('date_posted') if pd.notna(row.get('date_posted')) else None,
                    is_remote=bool(row.get('is_remote', False))
                )
                jobs.append(job)
            except Exception:
                continue
        return jobs