import logging
import requests
import os
import sys
from urllib.parse import urlparse
from playwright.sync_api import Page

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database.storage import save_to_manual_queue
from shared.logger import logger
from ats_handlers import (
    WorkdayHandler,
    GreenhouseHandler,
    DarwinboxHandler,
    KekaHandler,
    ZohoHandler,
    NaukriHandler,
    IndeedHandler,
    LinkedInHandler
)


class AutoApplier:
    """
    Routes job URLs to the correct ATS handler based on domain matching.
    Uses Playwright Page object for browser automation.
    """

    def __init__(self, page: Page, user_data: dict, dry_run: bool = False):
        self.page = page
        self.user_data = user_data
        self.dry_run = dry_run
        
        self.routing_table = {
            "myworkdayjobs.com": WorkdayHandler,
            "greenhouse.io": GreenhouseHandler,
            "darwinbox.": DarwinboxHandler, 
            "keka.com": KekaHandler,
            "zoho.com/recruit": ZohoHandler,
            "naukri.com": NaukriHandler,
            "indeed.com": IndeedHandler,
            "linkedin.com": LinkedInHandler
        }

    def _resolve_external_redirects(self, url: str) -> str:
        """Unroll tracking URLs to find the actual ATS domain."""
        try:
            response = requests.head(url, allow_redirects=True, timeout=10)
            return response.url
        except requests.RequestException as e:
            logger.warning("Redirect resolution failed", url=url, error=str(e))
            return url 

    def process_job(self, job_url: str, user_id: str, job_id: str) -> bool:
        """Determines the ATS and executes the correct application strategy."""
        final_url = self._resolve_external_redirects(job_url)
        final_url_lower = final_url.lower()
        
        for domain_signature, handler_class in self.routing_table.items():
            if domain_signature in final_url_lower:
                logger.info(
                    "Routing to handler",
                    handler=handler_class.__name__,
                    url=final_url,
                    dry_run=self.dry_run,
                )
                handler = handler_class(
                    page=self.page,
                    user_data=self.user_data,
                    dry_run=self.dry_run,
                )
                
                self.page.goto(final_url, wait_until="domcontentloaded")
                
                return handler.execute_apply_flow()

        logger.warning("No ATS handler matched, saving to manual queue", url=final_url)
        self._save_to_manual_queue(user_id, job_id)
        return False

    def _save_to_manual_queue(self, user_id: str, job_id: str):
        """Saves the application attempt to the database with a manual status."""
        save_to_manual_queue(user_id, job_id)
        logger.info("Job flagged for manual queue", user_id=user_id, job_id=job_id)
