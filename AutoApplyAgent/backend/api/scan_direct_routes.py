"""
Direct scan endpoint — runs the pipeline in-process (no Celery/Redis required).
Used for local development and single-server deployments.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import get_current_user_id
from shared.logger import logger
from workers.pipeline_task import (
    ScoredResult,
    _stamp_results,
    build_user_data,
    fetch_platform_credentials,
    fetch_resume_file_url,
    fetch_user_preferences,
    run_auto_apply,
    save_scored_results_to_db,
)
import os

AUTO_APPLY_ENABLED: bool = os.getenv("AUTO_APPLY_ENABLED", "true").lower() == "true"
AUTO_APPLY_DRY_RUN: bool = os.getenv("AUTO_APPLY_DRY_RUN", "false").lower() == "true"

router = APIRouter(prefix="/scan", tags=["scan-direct"])

# ── In-memory scan store ──────────────────────────────────────
_scans: dict[str, dict] = {}


class DirectScanRequest(BaseModel):
    locations: list[str] | None = Field(default=None)
    resume_path: str | None = Field(default=None)


@router.post("/run")
async def run_scan_direct(
    payload: DirectScanRequest | None = None,
    current_user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Start a pipeline scan directly (no Celery)."""
    scan_id = str(uuid.uuid4())
    locations = payload.locations if payload else None
    resume_path = payload.resume_path if payload else None

    _scans[scan_id] = {
        "status": "running",
        "step": "starting",
        "user_id": str(current_user_id),
        "result": None,
        "error": None,
    }

    asyncio.create_task(
        _execute_scan(scan_id, str(current_user_id), locations, resume_path)
    )

    return {
        "scan_id": scan_id,
        "status": "running",
        "message": "Scan started. Poll /scan/run/{scan_id}/status for updates.",
    }


@router.get("/run/{scan_id}/status")
async def get_scan_run_status(scan_id: str):
    """Poll the status of a direct scan."""
    scan = _scans.get(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    return {
        "scan_id": scan_id,
        "status": scan["status"],
        "step": scan["step"],
        "result": scan["result"],
        "error": scan["error"],
    }


async def _execute_scan(
    scan_id: str,
    user_id: str,
    locations: list[str] | None,
    resume_path: str | None,
):
    """Run the full pipeline (parse → scrape → pre-filter → LLM score → auto-apply → DB save)."""
    from agents.job_scraper import JobScraper
    from agents.job_scorer import JobScorer
    from agents.pre_filter import PreFilter
    from agents.resume_parser import ResumeParser

    scan = _scans[scan_id]

    try:
        # ── Load preferences + resume URL from DB ────────────────────
        scan["step"] = "loading_preferences"
        prefs = await fetch_user_preferences(user_id)
        effective_locations = locations or prefs["locations"]
        threshold = prefs["threshold"]
        resume_file_url = await fetch_resume_file_url(user_id)
        actual_resume = resume_path or resume_file_url
        if not actual_resume:
            raise RuntimeError("Upload a resume before starting the agent.")

        # ── Parse resume ──────────────────────────────────────────────
        scan["step"] = "parsing_resume"
        parser = ResumeParser()
        resume_obj = await parser.parse(actual_resume)
        resume_obj.file_url = resume_file_url or actual_resume
        logger.info("Resume parsed", name=resume_obj.name, skills=len(resume_obj.skills))

        # ── Scrape ─────────────────────────────────────────────────
        scan["step"] = "scraping_jobs"
        scraper = JobScraper()
        jobs = scraper.scrape_all(
            roles=prefs["roles"],
            locations=effective_locations,
            num_per_search=10,
        )
        logger.info("Scraping done", total=len(jobs))

        if not jobs:
            scan["status"] = "completed"
            scan["step"] = "done"
            scan["result"] = {"jobs_scraped": 0, "scored": []}
            return

        # ── Pre-filter ──────────────────────────────────────────────
        scan["step"] = "filtering_jobs"
        pre_filter = PreFilter()
        filter_results = await pre_filter.filter_all(
            jobs, resume_obj.skills, pref_remote=prefs["remote_ok"]
        )
        passed_filter = sorted(
            [r for r in filter_results if r.passed], key=lambda r: r.score, reverse=True
        )
        logger.info("Pre-filter done", passed=len(passed_filter), total=len(filter_results))

        if not passed_filter:
            scan["status"] = "completed"
            scan["step"] = "done"
            scan["result"] = {"jobs_scraped": len(jobs), "passed_filter": 0, "scored": []}
            return

        # ── LLM Scoring ─────────────────────────────────────────────
        scan["step"] = "scoring_jobs"
        scorer = JobScorer(apply_threshold=threshold)
        raw_scored = await scorer.score_batch(
            resume=resume_obj,
            jobs=[r.job for r in passed_filter],
            max_jobs=15,
        )
        scored_results = [ScoredResult(job, match_score) for job, match_score in raw_scored]
        passed_scored  = [r for r in scored_results if r.should_apply]
        logger.info("LLM scoring done", scored=len(scored_results), above_threshold=len(passed_scored))

        # ── Auto-apply ──────────────────────────────────────────────
        apply_results: list[dict] = []
        if AUTO_APPLY_ENABLED and passed_scored and not AUTO_APPLY_DRY_RUN:
            scan["step"] = "auto_applying"
            user_data   = build_user_data(resume_obj, prefs)
            credentials = await fetch_platform_credentials(user_id)
            apply_results = await run_auto_apply(
                passed_scored, user_id, user_data,
                actual_resume, credentials, threshold,
            )

        # ── Stamp + save to DB ───────────────────────────────────────
        scan["step"] = "saving_to_database"
        _stamp_results(scored_results, {a["url"]: a for a in apply_results})
        await save_scored_results_to_db(user_id, scored_results, threshold)

        applied_count = len([a for a in apply_results if a["success"]])
        scan["status"] = "completed"
        scan["step"]   = "done"
        scan["result"] = {
            "jobs_scraped":    len(jobs),
            "passed_filter":   len(passed_filter),
            "total_scored":    len(scored_results),
            "above_threshold": len(passed_scored),
            "auto_applied":    applied_count,
            "jobs": [
                {
                    "title":    r.job.title,
                    "company":  r.job.company,
                    "location": r.job.location,
                    "score":    r.score,
                    "reason":   r.reason,
                    "url":      r.job.apply_url,
                    "status":   r.auto_apply_status,
                }
                for r in scored_results
            ],
        }
        logger.info("Direct scan completed", scan_id=scan_id, user_id=user_id,
                    scored=len(scored_results), applied=applied_count)

    except Exception as exc:
        scan["status"] = "failed"
        scan["step"]   = "error"
        scan["error"]  = str(exc)
        logger.error("Direct scan failed", scan_id=scan_id, error=str(exc))
