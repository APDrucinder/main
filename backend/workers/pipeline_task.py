import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select

from workers.celery_app import celery_app          # was: from celery_app import celery  ← was broken
from agents.job_scraper import JobScraper
from agents.pre_filter import PreFilter
from agents.resume_parser import ResumeParser
from database.connection import AsyncSessionLocal
from database.models import Job, Application, JobPreference, User, Resume
from shared.logger import logger

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_ROLES     = ["software engineer", "python developer", "backend developer"]
DEFAULT_LOCATIONS = ["Bangalore", "Mumbai"]
DEFAULT_NUM_JOBS  = 10

# ── Feature flags ─────────────────────────────────────────────────────────────
# Override in Railway: AUTO_APPLY_ENABLED=false, AUTO_APPLY_DRY_RUN=true
import os
AUTO_APPLY_ENABLED: bool = os.getenv("AUTO_APPLY_ENABLED", "true").lower() == "true"
AUTO_APPLY_DRY_RUN: bool = os.getenv("AUTO_APPLY_DRY_RUN", "false").lower() == "true"


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_user_preferences(user_id: str) -> dict:
    """Fetch user's active JobPreference row. Returns defaults if none found."""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(JobPreference).where(
                    JobPreference.user_id == uuid.UUID(user_id),
                    JobPreference.is_active == True,
                )
            )
            prefs = result.scalar_one_or_none()
            if prefs:
                logger.info(
                    "Loaded user preferences",
                    user_id=user_id,
                    roles=prefs.target_roles,
                    locations=prefs.locations,
                    threshold=prefs.auto_apply_threshold,
                )
                return {
                    "roles":            prefs.target_roles or DEFAULT_ROLES,
                    "locations":        prefs.locations or DEFAULT_LOCATIONS,
                    "remote_ok":        prefs.remote_ok,
                    "threshold":        prefs.auto_apply_threshold,
                    "experience_years": prefs.experience_years or 0,
                }
            logger.warning("No preferences found, using defaults", user_id=user_id)
        except Exception as e:
            logger.error("Failed to fetch preferences", user_id=user_id, error=str(e))

        return {
            "roles":            DEFAULT_ROLES,
            "locations":        DEFAULT_LOCATIONS,
            "remote_ok":        False,
            "threshold":        75,
            "experience_years": 0,
        }


async def fetch_resume_file_url(user_id: str) -> str | None:
    """
    Returns the Supabase file_url for the user's most recently uploaded resume.
    The bot downloads this URL to get the PDF for file upload fields.
    Returns None if the user has no resume uploaded yet.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Resume)
                .where(Resume.user_id == uuid.UUID(user_id))
                .order_by(Resume.uploaded_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return row.file_url if row else None
        except Exception as e:
            logger.warning("Could not fetch resume file_url", user_id=user_id, error=str(e))
            return None


async def fetch_platform_credentials(user_id: str):
    """
    Loads stored ATS credentials from users.platform_credentials (JSONB column).
    Returns PlatformCredentials object, or None if user hasn't connected any accounts.

    Handlers that require login (Workday, Internshala) will return NO_CREDENTIALS
    status and skip cleanly when this returns None.
    """
    from agents.auto_apply import PlatformCredentials
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(User).where(User.clerk_id == user_id)
            )
            user_row = result.scalar_one_or_none()
            if not user_row:
                return None
            raw = getattr(user_row, "platform_credentials", None)
            if not raw:
                return None
            return PlatformCredentials(**raw)
        except Exception as e:
            logger.warning(
                "Could not load platform credentials — login-required platforms will be skipped",
                user_id=user_id,
                error=str(e),
            )
            return None


async def save_results_to_db(user_id: str, results: list, threshold: float):
    """
    Upserts Job rows, inserts Application rows (skips duplicates).
    Status is determined by auto_apply_status stamped onto each result.

    Status values written to DB:
      applied           — bot submitted successfully
      manual_required   — CAPTCHA blocked, user should apply manually
      needs_credentials — platform needs login, user hasn't stored creds
      failed            — bot failed (timeout, form error, redirect, etc.)
      matched           — above threshold, auto-apply not attempted
      below_threshold   — scored but below user's threshold
    """
    async with AsyncSessionLocal() as session:
        try:
            for r in results:
                # ── Upsert job row ──────────────────────────────────────
                existing = await session.execute(
                    select(Job).where(Job.apply_url == r.job.apply_url)
                )
                job_row = existing.scalar_one_or_none()

                if job_row is None:
                    job_row = Job(
                        id=uuid.uuid4(),
                        title=r.job.title,
                        company=r.job.company,
                        location=r.job.location,
                        description=r.job.description,
                        salary_range=r.job.salary_range,
                        apply_url=r.job.apply_url,
                        source=r.job.source,
                        posted_date=r.job.posted_date,
                    )
                    session.add(job_row)
                    await session.flush()
                    logger.info("Inserted job", title=job_row.title, company=job_row.company)

                # ── Skip duplicate application rows ─────────────────────
                existing_app = await session.execute(
                    select(Application).where(
                        Application.user_id == uuid.UUID(user_id),
                        Application.job_id == job_row.id,
                    )
                )
                if existing_app.scalar_one_or_none() is not None:
                    logger.debug("Application already exists, skipping", title=job_row.title)
                    continue

                # ── Map auto_apply_status → DB status ───────────────────
                auto_status   = getattr(r, "auto_apply_status", None)
                auto_platform = getattr(r, "auto_apply_platform", None)

                if auto_status == "applied":
                    status = "applied"
                elif auto_status in ("captcha",):
                    status = "manual_required"
                elif auto_status in ("no_credentials", "login_failed"):
                    status = "needs_credentials"
                elif auto_status is not None:
                    status = "failed"
                elif r.score >= threshold:
                    status = "matched"
                else:
                    status = "below_threshold"

                application = Application(
                    id=uuid.uuid4(),
                    user_id=uuid.UUID(user_id),
                    job_id=job_row.id,
                    match_score=r.score,
                    matched_skills=getattr(r, "matched_skills", []),
                    missing_skills=getattr(r, "missing_skills", []),
                    reasoning=r.reason,
                    status=status,
                    platform=auto_platform,
                    applied_at=datetime.utcnow(),
                )
                session.add(application)
                logger.info(
                    "Saved application",
                    score=r.score,
                    title=job_row.title,
                    status=status,
                    platform=auto_platform,
                )

            await session.commit()
            logger.info("DB save complete", count=len(results))

        except Exception as e:
            await session.rollback()
            logger.error("DB save failed", error=str(e))
            raise


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def build_user_data(resume_obj, prefs: dict) -> dict:
    """
    Builds the user_data dict that AutoApplyBot handlers read from.
    All fields default to empty string so handlers can safely call .get().
    """
    name   = resume_obj.name or ""
    parts  = name.split(" ", 1)
    return {
        "name":                name,
        "first_name":          parts[0],
        "last_name":           parts[1] if len(parts) > 1 else "",
        "email":               resume_obj.email or "",
        "phone":               resume_obj.phone or "",
        "location":            resume_obj.location or "",
        "city":                (resume_obj.location or "").split(",")[0].strip(),
        "years_of_experience": prefs.get("experience_years", 0),
        "linkedin_url":        resume_obj.linkedin_url or "",
        "portfolio_url":       resume_obj.portfolio_url or "",
        "current_company":     resume_obj.current_company or "",
        "cover_letter":        "",   # per-job generation added in Pro tier
        "skills":              resume_obj.skills or [],
    }


async def run_auto_apply(
    passed_results: list,
    user_id: str,
    user_data: dict,
    resume_file_url: str | None,
    credentials,
    threshold: float,
) -> list[dict]:
    """
    Drives AutoApplyBot across all passed results above threshold.
    Returns list of outcome dicts — never raises.
    """
    from agents.auto_apply import AutoApplyBot, ApplyStatus

    if not resume_file_url:
        logger.error(
            "Cannot auto-apply — no Supabase file_url for resume. "
            "User must upload resume via the API first.",
            user_id=user_id,
        )
        return []

    bot           = AutoApplyBot(headless=True, debug=False)
    apply_results = []

    for r in passed_results:
        if r.score < threshold:
            logger.info(
                "Skipping — below threshold",
                score=r.score, threshold=threshold, title=r.job.title,
            )
            continue

        logger.info(
            "Auto-applying",
            title=r.job.title, company=r.job.company,
            score=r.score, url=r.job.apply_url,
        )

        try:
            result = await bot.apply(
                job_url=r.job.apply_url,
                user_data=user_data,
                resume_url=resume_file_url,
                credentials=credentials,
            )
        except Exception as exc:
            logger.error("AutoApplyBot raised unexpectedly", url=r.job.apply_url, error=str(exc))
            apply_results.append({
                "url": r.job.apply_url, "platform": "unknown",
                "success": False, "status": "unknown_failure", "reason": str(exc),
            })
            continue

        success = result.status == ApplyStatus.SUCCESS
        logger.info(
            "Apply result",
            title=r.job.title, platform=result.platform,
            status=result.status, reason=result.reason,
        )
        apply_results.append({
            "url":      r.job.apply_url,
            "platform": result.platform,
            "success":  success,
            "status":   result.status,
            "reason":   result.reason if not success else None,
        })

    return apply_results


def _stamp_results(scored_results: list, apply_map: dict) -> None:
    """Stamps auto_apply_status and auto_apply_platform onto each result object."""
    for r in scored_results:
        outcome = apply_map.get(r.job.apply_url)
        if outcome:
            r.auto_apply_status   = "applied" if outcome["success"] else outcome["status"]
            r.auto_apply_platform = outcome.get("platform")
        else:
            r.auto_apply_status   = None
            r.auto_apply_platform = None


# ─────────────────────────────────────────────────────────────────────────────
# Celery task  —  called by scan API via run_pipeline_task.delay(...)
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True)
def run_pipeline_task(self, user_id: str, resume_path: str, locations: list = None):
    """
    Main Celery entry point. The scan API calls:
        run_pipeline_task.delay(user_id, resume_path, locations)

    Everything async is driven via asyncio.run() from this sync context.
    """

    # ── Step 0: Preferences ───────────────────────────────────────────
    self.update_state(state="STARTED", meta={"step": "loading_preferences"})
    prefs               = asyncio.run(fetch_user_preferences(user_id))
    effective_locations = locations or prefs["locations"]
    effective_roles     = prefs["roles"]
    threshold           = prefs["threshold"]

    logger.info(
        "Pipeline starting",
        user_id=user_id,
        roles=effective_roles,
        locations=effective_locations,
        auto_apply=AUTO_APPLY_ENABLED,
        dry_run=AUTO_APPLY_DRY_RUN,
    )

    # ── Step 1: Parse resume ──────────────────────────────────────────
    self.update_state(state="STARTED", meta={"step": "parsing_resume"})
    parser     = ResumeParser()
    resume_obj = asyncio.run(parser.parse(resume_path))

    # Fetch Supabase URL separately — resume_path is the local/tmp file path
    # used by the parser; file_url is the permanent Supabase URL for the bot
    resume_file_url    = asyncio.run(fetch_resume_file_url(user_id))
    resume_obj.file_url = resume_file_url

    if not resume_file_url:
        logger.warning(
            "No Supabase file_url found — auto-apply will be skipped. "
            "Ensure resume upload endpoint saves file_url to resumes table.",
            user_id=user_id,
        )

    logger.info("Resume parsed", name=resume_obj.name, skills=len(resume_obj.skills))

    # ── Step 2: Scrape ────────────────────────────────────────────────
    self.update_state(state="STARTED", meta={"step": "scraping_jobs"})
    scraper = JobScraper()
    jobs    = scraper.scrape_all(
        roles=effective_roles,
        locations=effective_locations,
        num_per_search=DEFAULT_NUM_JOBS,
    )
    if not jobs:
        logger.warning("No jobs scraped", user_id=user_id)
        return {"status": "complete", "total_passed": 0, "jobs": []}

    # ── Step 3: Pre-filter ────────────────────────────────────────────
    self.update_state(state="STARTED", meta={"step": "filtering_jobs"})
    pre_filter = PreFilter()
    results    = asyncio.run(
        pre_filter.filter_all(jobs, resume_obj.skills, pref_remote=prefs["remote_ok"])
    )
    passed = sorted([r for r in results if r.passed], key=lambda r: r.score, reverse=True)
    logger.info("Pre-filter done", passed=len(passed), total=len(results))

    # ── Step 4: Auto-apply ────────────────────────────────────────────
    apply_results: list[dict] = []
    if AUTO_APPLY_ENABLED and passed and not AUTO_APPLY_DRY_RUN:
        self.update_state(state="STARTED", meta={"step": "auto_applying"})
        user_data   = build_user_data(resume_obj, prefs)
        credentials = asyncio.run(fetch_platform_credentials(user_id))
        apply_results = asyncio.run(
            run_auto_apply(passed, user_id, user_data, resume_file_url, credentials, threshold)
        )
    elif AUTO_APPLY_DRY_RUN:
        logger.info("DRY RUN — skipping browser submissions", user_id=user_id)

    # ── Stamp + save ──────────────────────────────────────────────────
    self.update_state(state="STARTED", meta={"step": "saving_to_database"})
    _stamp_results(results, {a["url"]: a for a in apply_results})
    asyncio.run(save_results_to_db(user_id, results, threshold))

    applied_count = len([a for a in apply_results if a["success"]])
    logger.info(
        "Pipeline complete",
        user_id=user_id,
        total_passed=len(passed),
        auto_applied=applied_count,
    )
    return {
        "status":       "complete",
        "total_passed": len(passed),
        "auto_applied": applied_count,
        "jobs": [
            {
                "title":    r.job.title,
                "company":  r.job.company,
                "location": r.job.location,
                "score":    r.score,
                "reason":   r.reason,
                "url":      r.job.apply_url,
                "status":   getattr(r, "auto_apply_status", None),
                "platform": getattr(r, "auto_apply_platform", None),
            }
            for r in passed
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Async entry point  —  for tests and direct invocation
# ─────────────────────────────────────────────────────────────────────────────

async def execute_pipeline_task(
    task,
    user_id: str,
    *,
    resume_path: str,
    locations: list = None,
    pipeline_runner=None,
    auto_apply_callable=None,
) -> dict:
    """
    Async version used by tests and verification scripts.
    Accepts injectable pipeline_runner and auto_apply_callable for mocking.
    """

    task.update_state(state="STARTED", meta={"step": "loading_preferences"})
    prefs               = await fetch_user_preferences(user_id)
    effective_locations = locations or prefs["locations"]
    effective_roles     = prefs["roles"]
    threshold           = prefs["threshold"]

    # ── Run pipeline (real or injected) ──────────────────────────────
    task.update_state(state="STARTED", meta={"step": "running_pipeline"})
    if pipeline_runner is not None:
        pipeline_result = await pipeline_runner(
            user_id=user_id,
            resume_path=resume_path,
            roles=effective_roles,
            locations=effective_locations,
            prefs=prefs,
        )
    else:
        parser     = ResumeParser()
        resume_obj = await parser.parse(resume_path)

        resume_file_url     = await fetch_resume_file_url(user_id)
        resume_obj.file_url = resume_file_url

        scraper = JobScraper()
        jobs    = scraper.scrape_all(
            roles=effective_roles,
            locations=effective_locations,
            num_per_search=DEFAULT_NUM_JOBS,
        )

        pre_filter = PreFilter()
        results    = await pre_filter.filter_all(
            jobs, resume_obj.skills, pref_remote=prefs["remote_ok"]
        )
        passed = sorted([r for r in results if r.passed], key=lambda r: r.score, reverse=True)

        pipeline_result = type("R", (), {
            "resume":         resume_obj,
            "scored_results": results,
            "passed_results": passed,
        })()

    passed_results  = pipeline_result.passed_results
    resume_obj      = pipeline_result.resume
    resume_file_url = getattr(resume_obj, "file_url", None)

   
    apply_results: list[dict] = []
    if AUTO_APPLY_ENABLED and passed_results:
        task.update_state(state="STARTED", meta={"step": "auto_applying"})
        user_data   = build_user_data(resume_obj, prefs)
        credentials = await fetch_platform_credentials(user_id)

        if auto_apply_callable is not None:
            # Test/mock path
            for r in passed_results:
                if r.score < threshold:
                    continue
                result = auto_apply_callable(
                    job_url=r.job.apply_url,
                    user_id=user_id,
                    job_id=str(uuid.uuid4()),
                    user_data=user_data,
                )
                apply_results.append({
                    "url":      r.job.apply_url,
                    "platform": getattr(result, "platform", "unknown"),
                    "success":  getattr(result, "success", False),
                    "status":   getattr(result, "status", "unknown"),
                    "reason":   getattr(result, "failure_reason", None),
                })
        elif not AUTO_APPLY_DRY_RUN:
            apply_results = await run_auto_apply(
                passed_results, user_id, user_data, resume_file_url, credentials, threshold
            )

   
    task.update_state(state="STARTED", meta={"step": "saving_to_database"})
    _stamp_results(pipeline_result.scored_results, {a["url"]: a for a in apply_results})
    await save_results_to_db(user_id, pipeline_result.scored_results, threshold)

    applied_count = len([a for a in apply_results if a["success"]])
    logger.info(
        "execute_pipeline_task complete",
        user_id=user_id,
        total_scored=len(pipeline_result.scored_results),
        total_applied=applied_count,
    )
    return {
        "status":        "complete",
        "total_scored":  len(pipeline_result.scored_results),
        "total_applied": applied_count,
        "apply_results": apply_results,
    }