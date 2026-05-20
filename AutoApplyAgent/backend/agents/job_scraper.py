"""
Production-grade job scraper with Redis caching and Selenium.

Architecture (for 1K+ concurrent users):
  1. Check Redis cache for role+location combo
  2. If miss → fall back to Selenium
  3. Cache results for 2 hours so identical searches are instant
"""

from __future__ import annotations

import json
import os
import random
import ssl
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import redis
import yaml
from bs4 import BeautifulSoup
from pydantic import BaseModel

from shared.base_agent import BaseAgent
from shared.logger import logger

# Lazy-loaded — only imported if Selenium is needed (Cache Miss)
_webdriver = None
_Service = None
_ChromeDriverManager = None

def _lazy_import_selenium():
    """Import Selenium only when needed to avoid Chrome dependency at module load."""
    global _webdriver, _Service, _ChromeDriverManager
    if _webdriver is None:
        from selenium import webdriver as wd
        from selenium.webdriver.chrome.service import Service as Svc
        from webdriver_manager.chrome import ChromeDriverManager as CDM
        _webdriver = wd
        _Service = Svc
        _ChromeDriverManager = CDM


# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "scraper_selectors.yaml"
)

def _load_config() -> Dict:
    """Load scraper config from YAML, with sensible defaults."""
    defaults = {
        "naukri": {
            "cache_ttl_seconds": 7200,
            "max_pages": 3,
            "results_per_page": 20,
            "rate_limit_per_minute": 10,
            "job_card_container": "div.srp-jobtuple-wrapper",
            "row1": "div.row1",
            "row2": "div.row2",
            "row3": "div.row3",
            "row4": "div.row4",
            "row5": "div.row5",
            "row6": "div.row6",
        }
    }
    try:
        with open(_CONFIG_PATH, "r") as f:
            loaded = yaml.safe_load(f) or {}
            for platform, values in loaded.items():
                if isinstance(values, dict):
                    defaults[platform] = {**defaults.get(platform, {}), **values}
            logger.debug("Loaded scraper config", path=_CONFIG_PATH)
            return defaults
    except FileNotFoundError:
        logger.warning("Scraper config not found, using defaults", path=_CONFIG_PATH)
        return defaults
    except Exception as e:
        logger.error("Failed to load scraper config", error=str(e))
        return defaults

CONFIG = _load_config()

# ──────────────────────────────────────────────────────────────────────────────
# Redis cache connection
# ──────────────────────────────────────────────────────────────────────────────
_redis_client: Optional[redis.Redis] = None

def _get_redis() -> Optional[redis.Redis]:
    """Lazy singleton Redis connection using the Upstash URL from environment."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    redis_url = os.getenv("REDIS_URL") or os.getenv("UPSTASH_REDIS_URL")
    if not redis_url:
        logger.warning("No REDIS_URL set — scraper caching disabled")
        return None

    try:
        use_tls = redis_url.startswith("rediss://")
        ssl_cert_reqs_env = os.getenv("REDIS_SSL_CERT_REQS", "none").lower()
        cert_reqs = ssl.CERT_REQUIRED if ssl_cert_reqs_env == "required" else ssl.CERT_NONE

        _redis_client = redis.from_url(
            redis_url,
            decode_responses=True,
            ssl_cert_reqs=cert_reqs if use_tls else None,
        )
        _redis_client.ping()
        logger.info("Redis cache connected for scraper")
        return _redis_client
    except Exception as e:
        logger.warning("Redis connection failed — caching disabled", error=str(e))
        _redis_client = None
        return None

# ──────────────────────────────────────────────────────────────────────────────
# Rate limiter
# ──────────────────────────────────────────────────────────────────────────────
class _RateLimiter:
    """Simple token-bucket rate limiter. Thread-safe."""

    def __init__(self, max_per_minute: int = 10):
        self._interval = 60.0 / max(max_per_minute, 1)
        self._last_call = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._interval:
                sleep_time = self._interval - elapsed
                time.sleep(sleep_time)
            self._last_call = time.monotonic()

_naukri_limiter = _RateLimiter(
    max_per_minute=CONFIG.get("naukri", {}).get("rate_limit_per_minute", 10)
)

# ──────────────────────────────────────────────────────────────────────────────
# Fixed User-Agent (Naukri is sensitive to fake-useragent weirdness)
# ──────────────────────────────────────────────────────────────────────────────
FIXED_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _cache_key(role: str, location: str) -> str:
    """Deterministic cache key for a role+location combo."""
    raw = f"naukri:jobs:{role.lower().strip()}:{location.lower().strip()}"
    return raw

def _generate_naukri_url(role: str, location: str, page_index: int) -> str:
    """Generate a Naukri search URL with pagination."""
    formatted_role = role.lower().replace(" ", "-")
    formatted_loc = location.lower().replace(" ", "-")
    base = f"https://www.naukri.com/{formatted_role}-jobs-in-{formatted_loc}"
    if page_index <= 1:
        return base
    return f"{base}-{page_index}"

def _retry_with_backoff(fn, max_retries: int = 3, base_delay: float = 2.0):
    """Execute fn() with exponential backoff."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            logger.warning(
                "Retry attempt",
                attempt=attempt + 1,
                max_retries=max_retries,
                delay=round(delay, 1),
                error=str(e),
            )
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic model (unchanged — full backward compatibility)
# ──────────────────────────────────────────────────────────────────────────────
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

# ──────────────────────────────────────────────────────────────────────────────
# Main scraper class
# ──────────────────────────────────────────────────────────────────────────────
class JobScraper(BaseAgent):

    def __init__(self):
        super().__init__("job_scraper")
        self._naukri_cfg = CONFIG.get("naukri", {})

    def scrape_all(
        self,
        roles: List[str],
        locations: List[str],
        num_per_search: int = 20,
    ) -> List[JobPosting]:
        all_jobs: List[JobPosting] = []
        seen_urls: set = set()

        from jobspy import scrape_jobs  # local import to keep module load fast

        jobspy_sites = ["linkedin"]

        for role in roles:
            for loc in locations:
                clean_loc = loc.strip()
                search_location = (
                    clean_loc if "india" in clean_loc.lower() else f"{clean_loc}, India"
                )

                # --- PHASE 1: JobSpy (Indeed/LinkedIn) ---
                logger.info("Scraping via JobSpy", sites=jobspy_sites, role=role, location=search_location)
                try:
                    df = scrape_jobs(
                        site_name=jobspy_sites,
                        search_term=role,
                        location=search_location,
                        results_wanted=num_per_search,
                        country_indeed="India",
                        hours_old=72,
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

                # --- PHASE 2: Naukri (Cached + Selenium) ---
                try:
                    naukri_results = self._scrape_naukri(role, clean_loc)
                    logger.info("Naukri scrape complete", new_jobs=len(naukri_results), role=role, location=clean_loc)
                except Exception as e:
                    logger.error("Naukri scrape failed", error=str(e), role=role, location=clean_loc)
                    naukri_results = []

                for job in naukri_results:
                    if job.apply_url not in seen_urls:
                        seen_urls.add(job.apply_url)
                        all_jobs.append(job)

        logger.info("Scraping complete", total_unique_jobs=len(all_jobs))
        return all_jobs

    def _scrape_naukri(self, role: str, location: str) -> List[JobPosting]:
        """Checks cache first, falls back to Selenium."""
        cache_ttl = self._naukri_cfg.get("cache_ttl_seconds", 7200)
        key = _cache_key(role, location)

        # ── Check cache
        cached = self._cache_get(key)
        if cached is not None:
            logger.info("Naukri cache HIT", role=role, location=location, jobs=len(cached))
            return cached

        # ── Cache MISS, hit Selenium
        logger.info("Naukri cache MISS — scraping", role=role, location=location)
        jobs: List[JobPosting] = []

        try:
            jobs = _retry_with_backoff(
                lambda: self._scrape_naukri_selenium(role, location),
                max_retries=2,
                base_delay=5.0,
            )
        except Exception as sel_err:
            logger.error(
                "Naukri Selenium scraping failed",
                error=str(sel_err),
                role=role,
                location=location,
            )

        # ── Cache results
        if jobs:
            self._cache_set(key, jobs, ttl=cache_ttl)

        return jobs

    def _scrape_naukri_selenium(self, role: str, location: str) -> List[JobPosting]:
        """Selenium-based scraper for Naukri."""
        _lazy_import_selenium()

        max_pages = self._naukri_cfg.get("max_pages", 3)
        logger.info("Selenium for Naukri", role=role, location=location, max_pages=max_pages)

        options = _webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"user-agent={FIXED_USER_AGENT}")

        try:
            driver = _webdriver.Chrome(
                service=_Service(_ChromeDriverManager().install()),
                options=options,
            )
        except Exception as e:
            logger.error("Selenium Chrome init failed", error=str(e))
            return []

        jobs: List[JobPosting] = []

        try:
            for page in range(1, max_pages + 1):
                _naukri_limiter.wait()
                url = _generate_naukri_url(role, location, page)
                logger.debug("Selenium: fetching page", url=url, page=page)

                driver.get(url)
                time.sleep(random.uniform(5, 8))
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
                time.sleep(2)

                soup = BeautifulSoup(driver.page_source, "html.parser")
                cards = soup.find_all("div", class_="srp-jobtuple-wrapper")

                if not cards:
                    logger.info("Selenium: no more cards", page=page)
                    break

                for card in cards:
                    try:
                        parsed = self._parse_selenium_card(card, location)
                        if parsed:
                            jobs.append(parsed)
                    except Exception:
                        continue

                logger.info("Selenium page scraped", page=page, cards=len(cards), total=len(jobs))

        except Exception as e:
            logger.error("Selenium scraping failed", error=str(e))
        finally:
            driver.quit()

        logger.info("Selenium complete", jobs_found=len(jobs), role=role, location=location)
        return jobs

    @staticmethod
    def _parse_selenium_card(card, fallback_location: str) -> Optional[JobPosting]:
        """Parse a single Naukri job card using the row1–row6 DOM structure."""
        card_soup = BeautifulSoup(str(card), "html.parser")

        row1 = card_soup.find("div", class_="row1")
        row2 = card_soup.find("div", class_="row2")
        row3 = card_soup.find("div", class_="row3")
        row4 = card_soup.find("div", class_="row4")
        row5 = card_soup.find("div", class_="row5")

        # Title & URL
        if row1 is None or row1.a is None:
            return None
        job_title = row1.a.text.strip()
        apply_url = row1.a.get("href", "")
        if not apply_url:
            return None

        # Company
        company_name = ""
        if row2 is not None:
            comp_a = row2.find("a")
            if comp_a:
                company_name = comp_a.text.strip()
            elif row2.span and row2.span.a:
                company_name = row2.span.a.text.strip()
        if not company_name:
            return None

        # Experience & location (row3)
        experience = "Not Specified"
        parsed_location = fallback_location
        if row3 is not None:
            job_details = row3.find("div", class_="job-details")
            if job_details:
                exp_wrap = job_details.find("span", class_="exp-wrap")
                if exp_wrap:
                    inner = exp_wrap.find("span")
                    if inner:
                        deep = inner.find("span")
                        experience = (deep or inner).text.strip()

                loc_wrap = job_details.find("span", class_="loc-wrap")
                if loc_wrap is None:
                    loc_wrap = job_details.find("span", class_="loc-wrap ver-line")
                if loc_wrap:
                    inner = loc_wrap.find("span")
                    if inner:
                        deep = inner.find("span")
                        parsed_location = (deep or inner).text.strip()

        # Description (row4)
        description_parts: List[str] = []
        if row4 is not None and row4.span:
            description_parts.append(row4.span.text.strip())

        # Tech stack (row5)
        if row5 is not None:
            ul = row5.find("ul")
            if ul:
                tags = [li.text.strip() for li in ul.find_all("li") if li.text.strip()]
                if tags:
                    description_parts.append("Tech Stack: " + ", ".join(tags))

        description = " | ".join(description_parts) if description_parts else "Naukri listing"
        is_remote = "remote" in card.text.lower() if hasattr(card, "text") else False

        return JobPosting(
            title=job_title,
            company=company_name,
            location=parsed_location,
            description=description,
            experience_required=experience,
            apply_url=apply_url,
            source="naukri",
            is_remote=is_remote,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Redis cache helpers
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _cache_get(key: str) -> Optional[List[JobPosting]]:
        """Get cached job results from Redis."""
        r = _get_redis()
        if r is None:
            return None
        try:
            raw = r.get(key)
            if raw is None:
                return None
            data = json.loads(raw)
            return [JobPosting(**item) for item in data]
        except Exception as e:
            logger.debug("Cache read failed", key=key, error=str(e))
            return None

    @staticmethod
    def _cache_set(key: str, jobs: List[JobPosting], ttl: int = 7200):
        """Store job results in Redis with TTL."""
        r = _get_redis()
        if r is None:
            return
        try:
            data = [job.model_dump(mode="json") for job in jobs]
            r.setex(key, ttl, json.dumps(data, default=str))
            logger.debug("Cached Naukri results", key=key, count=len(jobs), ttl=ttl)
        except Exception as e:
            logger.debug("Cache write failed", key=key, error=str(e))

    # ──────────────────────────────────────────────────────────────────────
    # JobSpy result parser
    # ──────────────────────────────────────────────────────────────────────
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
                    is_remote=bool(row.get('is_remote', False)),
                )
                if not job.apply_url:
                    continue
                jobs.append(job)
            except Exception:
                continue
        return jobs

