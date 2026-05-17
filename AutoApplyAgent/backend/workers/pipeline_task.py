import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select

from workers.celery_app import celery_app
from agents.job_scraper import JobScraper
from agents.job_scorer import JobScorer
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
AUTO_APPLY_HEADLESS: bool = os.getenv("AUTO_APPLY_HEADLESS", "true").lower() == "true"
AUTO_APPLY_MAX_PER_RUN: int = int(os.getenv("AUTO_APPLY_MAX_PER_RUN", "3"))
AUTO_APPLY_MAX_CONSECUTIVE_FAILURES: int = int(os.getenv("AUTO_APPLY_MAX_CONSECUTIVE_FAILURES", "2"))
AUTO_APPLY_MIN_THRESHOLD: int = int(os.getenv("AUTO_APPLY_MIN_THRESHOLD", "75"))


def _parse_user_uuid(user_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(user_id))
    except ValueError as exc:
        raise ValueError(f"user_id must be a valid UUID: {user_id}") from exc


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_user_preferences(user_id: str) -> dict:
    """Fetch user's active JobPreference row. Returns defaults if none found."""
    user_uuid = _parse_user_uuid(user_id)
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(JobPreference).where(
                    JobPreference.user_id == user_uuid,
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
                    "threshold":        max(prefs.auto_apply_threshold, AUTO_APPLY_MIN_THRESHOLD),
                    "experience_years": prefs.experience_years or 0,
                }
            logger.warning("No preferences found, using defaults", user_id=user_id)
        except Exception as e:
            logger.error("Failed to fetch preferences", user_id=user_id, error=str(e))

        return {
            "roles":            DEFAULT_ROLES,
            "locations":        DEFAULT_LOCATIONS,
            "remote_ok":        False,
            "threshold":        AUTO_APPLY_MIN_THRESHOLD,
            "experience_years": 0,
        }


async def fetch_resume_file_url(user_id: str) -> str | None:
    """
    Returns the Supabase file_url for the user's most recently uploaded resume.
    The bot downloads this URL to get the PDF for file upload fields.
    Returns None if the user has no resume uploaded yet.
    """
    user_uuid = _parse_user_uuid(user_id)
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Resume)
                .where(Resume.user_id == user_uuid)
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
    user_uuid = _parse_user_uuid(user_id)
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(User).where(User.id == user_uuid)
            )
            user_row = result.scalar_one_or_none()
            if not user_row:
                # Backward compatibility: older environments may pass clerk_id.
                legacy_result = await session.execute(
                    select(User).where(User.clerk_id == user_id)
                )
                user_row = legacy_result.scalar_one_or_none()
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


async def save_scored_results_to_db(user_id: str, scored_results: list, threshold: float):
    """
    Upserts Job rows and Application rows from LLM-scored results only.
    Each item in scored_results is a ScoredResult dataclass with:
      .job   — JobPosting
      .score — int (LLM match score 0–100)
      .reason — str (LLM reasoning)
      .matched_skills — list[str]
      .missing_skills — list[str]
      .should_apply  — bool (score >= threshold)
      .auto_apply_status   — str | None (stamped by _stamp_results)
      .auto_apply_platform — str | None (stamped by _stamp_results)

    Status values written to DB:
      applied           — bot submitted successfully
      manual_required   — CAPTCHA blocked, user should apply manually
      needs_credentials — platform needs login, user hasn't stored creds
      failed            — bot failed (timeout, form error, redirect, etc.)
      matched           — above threshold, auto-apply not attempted
      below_threshold   — scored but below user's threshold
    """
    user_uuid = _parse_user_uuid(user_id)
    async with AsyncSessionLocal() as session:
        try:
            for r in scored_results:
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
                        Application.user_id == user_uuid,
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
                    user_id=user_uuid,
                    job_id=job_row.id,
                    match_score=r.score,
                    matched_skills=getattr(r, "matched_skills", []),
                    missing_skills=getattr(r, "missing_skills", []),
                    reasoning=getattr(r, "reason", getattr(r, "reasoning", "")),
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
            logger.info("DB save complete", count=len(scored_results))

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

    bot           = AutoApplyBot(headless=AUTO_APPLY_HEADLESS, debug=False)
    apply_results = []
    consecutive_failures = 0

    for r in passed_results[:AUTO_APPLY_MAX_PER_RUN]:
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
            "status":   result.status.value,
            "reason":   result.reason if not success else None,
        })

        if success:
            consecutive_failures = 0
            continue

        if result.status in {ApplyStatus.LOGIN_FAILED, ApplyStatus.NO_CREDENTIALS}:
            logger.warning(
                "Stopping auto-apply run because platform session is invalid",
                platform=result.platform,
                status=result.status.value,
                reason=result.reason,
            )
            break

        consecutive_failures += 1
        if consecutive_failures >= AUTO_APPLY_MAX_CONSECUTIVE_FAILURES:
            logger.warning(
                "Stopping auto-apply run after consecutive failures",
                failures=consecutive_failures,
                max_failures=AUTO_APPLY_MAX_CONSECUTIVE_FAILURES,
            )
            break

    return apply_results


def _stamp_results(scored_results: list, apply_map: dict) -> None:
    """Stamps auto_apply_status and auto_apply_platform onto each ScoredResult."""
    for r in scored_results:
        outcome = apply_map.get(r.job.apply_url)
        if outcome:
            r.auto_apply_status   = "applied" if outcome["success"] else outcome["status"]
            r.auto_apply_platform = outcome.get("platform")
        else:
            r.auto_apply_status   = None
            r.auto_apply_platform = None


class ScoredResult:
    """
    Unified result object wrapping LLM-scored job data for DB saving.
    Combines JobPosting + MatchScore into a single object that
    save_scored_results_to_db, _stamp_results, and run_auto_apply can all read.
    """
    __slots__ = (
        "job", "score", "reason", "matched_skills", "missing_skills",
        "should_apply", "auto_apply_status", "auto_apply_platform",
    )

    def __init__(self, job, match_score):
        self.job            = job
        self.score          = match_score.score
        self.reason         = match_score.reasoning
        self.matched_skills = match_score.matched_skills
        self.missing_skills = match_score.missing_skills
        self.should_apply   = match_score.should_apply
        self.auto_apply_status   = None
        self.auto_apply_platform = None


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
    parser = ResumeParser()
    resume_file_url = asyncio.run(fetch_resume_file_url(user_id))
    resume_source = resume_path or resume_file_url
    if not resume_source:
        raise ValueError(
            "No resume provided. Upload a resume first or pass resume_path to the task."
        )

    resume_obj = asyncio.run(parser.parse(resume_source))
    resume_obj.file_url = resume_file_url or resume_source

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
    filter_results = asyncio.run(
        pre_filter.filter_all(jobs, resume_obj.skills, pref_remote=prefs["remote_ok"])
    )
    passed_filter = sorted(
        [r for r in filter_results if r.passed], key=lambda r: r.score, reverse=True
    )
    logger.info("Pre-filter done", passed=len(passed_filter), total=len(filter_results))

    if not passed_filter:
        logger.warning("No jobs passed pre-filter", user_id=user_id)
        return {"status": "complete", "total_passed": 0, "jobs": []}

    # ── Step 4: LLM Scoring ───────────────────────────────────────────
    self.update_state(state="STARTED", meta={"step": "scoring_jobs"})
    scorer = JobScorer(apply_threshold=threshold)
    raw_scored = asyncio.run(
        scorer.score_batch(
            resume=resume_obj,
            jobs=[r.job for r in passed_filter],
            max_jobs=15,
        )
    )
    # Wrap into ScoredResult objects for uniform DB saving
    scored_results = [ScoredResult(job, match_score) for job, match_score in raw_scored]
    passed_scored  = [r for r in scored_results if r.should_apply]
    logger.info(
        "LLM scoring done",
        scored=len(scored_results),
        above_threshold=len(passed_scored),
    )

    # ── Step 5: Auto-apply ────────────────────────────────────────────
    apply_results: list[dict] = []
    resume_for_apply = resume_file_url or resume_path
    if AUTO_APPLY_ENABLED and passed_scored and not AUTO_APPLY_DRY_RUN:
        self.update_state(state="STARTED", meta={"step": "auto_applying"})
        user_data   = build_user_data(resume_obj, prefs)
        credentials = asyncio.run(fetch_platform_credentials(user_id))
        apply_results = asyncio.run(
            run_auto_apply(passed_scored, user_id, user_data, resume_for_apply, credentials, threshold)
        )
    elif AUTO_APPLY_DRY_RUN:
        logger.info("DRY RUN — skipping browser submissions", user_id=user_id)

    # ── Stamp + save (LLM-scored results only) ────────────────────────
    self.update_state(state="STARTED", meta={"step": "saving_to_database"})
    _stamp_results(scored_results, {a["url"]: a for a in apply_results})
    asyncio.run(save_scored_results_to_db(user_id, scored_results, threshold))

    applied_count = len([a for a in apply_results if a["success"]])
    logger.info(
        "Pipeline complete",
        user_id=user_id,
        total_scored=len(scored_results),
        auto_applied=applied_count,
    )
    return {
        "status":       "complete",
        "total_scored": len(scored_results),
        "total_passed": len(passed_scored),
        "auto_applied": applied_count,
        "jobs": [
            {
                "title":    r.job.title,
                "company":  r.job.company,
                "location": r.job.location,
                "score":    r.score,
                "reason":   r.reason,
                "url":      r.job.apply_url,
                "status":   r.auto_apply_status,
                "platform": r.auto_apply_platform,
            }
            for r in scored_results
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
    _parse_user_uuid(user_id)
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
        parser = ResumeParser()
        resume_file_url = await fetch_resume_file_url(user_id)
        resume_source = resume_path or resume_file_url
        if not resume_source:
            raise ValueError(
                "No resume provided. Upload a resume first or pass resume_path to the task."
            )
        resume_obj = await parser.parse(resume_source)
        resume_obj.file_url = resume_file_url or resume_source

        scraper = JobScraper()
        jobs    = scraper.scrape_all(
            roles=effective_roles,
            locations=effective_locations,
            num_per_search=DEFAULT_NUM_JOBS,
        )

        pre_filter   = PreFilter()
        filter_res   = await pre_filter.filter_all(
            jobs, resume_obj.skills, pref_remote=prefs["remote_ok"]
        )
        passed_filter = sorted(
            [r for r in filter_res if r.passed], key=lambda r: r.score, reverse=True
        )

        # LLM scoring on pre-filtered jobs
        scorer     = JobScorer(apply_threshold=threshold)
        raw_scored = await scorer.score_batch(
            resume=resume_obj,
            jobs=[r.job for r in passed_filter],
            max_jobs=15,
        )
        scored_results = [ScoredResult(job, match_score) for job, match_score in raw_scored]
        passed_scored  = [r for r in scored_results if r.should_apply]

        pipeline_result = type("R", (), {
            "resume":         resume_obj,
            "scored_results": scored_results,
            "passed_results": passed_scored,
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
    await save_scored_results_to_db(user_id, pipeline_result.scored_results, threshold)

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
