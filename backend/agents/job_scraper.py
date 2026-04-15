import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time
import random
import yaml
import os
from jobspy import scrape_jobs
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import pandas as pd
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from shared.base_agent import BaseAgent
from shared.logger import logger

# ──────────────────────────────────────────────────
# Load selectors from YAML config (fallback to defaults)
# ──────────────────────────────────────────────────
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "scraper_selectors.yaml")

def _load_selectors() -> Dict:
    """Load CSS selectors from YAML config, falling back to hardcoded defaults."""
    defaults = {
        "naukri": {
            "job_card_container": "div.srp-jobtuple-wrapper",
            "title_link": "a.title",
            "company_link": "a.comp-name",
        }
    }
    try:
        with open(_CONFIG_PATH, "r") as f:
            loaded = yaml.safe_load(f) or {}
            # Merge: config overrides defaults
            for platform, selectors in loaded.items():
                defaults[platform] = {**defaults.get(platform, {}), **selectors}
            logger.debug("Loaded scraper selectors from config", path=_CONFIG_PATH)
            return defaults
    except FileNotFoundError:
        logger.warning("Selectors config not found, using defaults", path=_CONFIG_PATH)
        return defaults
    except Exception as e:
        logger.error("Failed to load selectors config", error=str(e))
        return defaults

SELECTORS = _load_selectors()


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
        logger.info("Launching stealth browser for Naukri", role=role, location=location)
        
        options = uc.ChromeOptions()
        options.add_argument('--headless') 
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        try:
            driver = uc.Chrome(options=options, version_main=146)
        except Exception as e:
            logger.error("Failed to initialize stealth driver", error=str(e))
            return []

        naukri_jobs = []
        naukri_sel = SELECTORS.get("naukri", {})

        try:
            formatted_role = role.lower().replace(" ", "-")
            formatted_loc = location.lower().replace(" ", "-")
            url = f"https://www.naukri.com/{formatted_role}-jobs-in-{formatted_loc}"
            
            driver.get(url)
            time.sleep(random.uniform(5, 8)) 
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Use selectors from config
            container_sel = naukri_sel.get("job_card_container", "div.srp-jobtuple-wrapper")
            title_sel = naukri_sel.get("title_link", "a.title") 
            company_sel = naukri_sel.get("company_link", "a.comp-name")
            
            # Parse container selector: "div.classname" → find_all('div', class_='classname')
            tag, cls = container_sel.split(".", 1) if "." in container_sel else (container_sel, None)
            job_cards = soup.find_all(tag, class_=cls) if cls else soup.find_all(tag)

            for card in job_cards:
                t_tag, t_cls = title_sel.split(".", 1) if "." in title_sel else (title_sel, None)
                c_tag, c_cls = company_sel.split(".", 1) if "." in company_sel else (company_sel, None)
                
                title_tag = card.find(t_tag, class_=t_cls) if t_cls else card.find(t_tag)
                comp_tag = card.find(c_tag, class_=c_cls) if c_cls else card.find(c_tag)
                
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
            
            logger.info("Naukri scrape complete", jobs_found=len(naukri_jobs), role=role, location=location)
            
        except Exception as e:
            logger.error("Naukri scraping failed", error=str(e), role=role, location=location)
        finally:
            driver.quit()
            
        return naukri_jobs
    
    def scrape_all(self, roles: List[str], locations: List[str], num_per_search: int = 20) -> List[JobPosting]:
        all_jobs = []
        seen_urls = set()
        
        jobspy_sites = ["indeed", "linkedin"]
        
        for role in roles:
            for loc in locations:
                clean_loc = loc.strip()
                search_location = clean_loc if "india" in clean_loc.lower() else f"{clean_loc}, India"
                
                # --- PHASE 1: JobSpy (Indeed/LinkedIn) ---
                logger.info("Scraping via JobSpy", sites=jobspy_sites, role=role, location=search_location)
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
                        logger.info("JobSpy scrape complete", new_jobs=len(parsed), role=role, location=search_location)
                except Exception as e:
                    logger.error("JobSpy scrape failed", error=str(e), role=role, location=search_location)

                # --- PHASE 2: Stealth Naukri (Selenium) ---
                naukri_results = self._scrape_naukri_stealth(role, clean_loc)
                for job in naukri_results:
                    if job.apply_url not in seen_urls:
                        seen_urls.add(job.apply_url)
                        all_jobs.append(job)
        
        logger.info("Scraping complete", total_unique_jobs=len(all_jobs))
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