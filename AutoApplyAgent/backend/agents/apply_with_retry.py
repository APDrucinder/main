from __future__ import annotations

import asyncio

from shared.logger import logger

try:
    import sentry_sdk
except ImportError:  # pragma: no cover
    sentry_sdk = None

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover
    Langfuse = None

langfuse = Langfuse() if Langfuse else None


class ApplicationTimeoutError(Exception):
    pass


class ApplicationRetryableError(Exception):
    pass


async def apply_with_timeout(
    auto_apply_func,
    job,
    resume_path: str,
    timeout_seconds: int = 90,
) -> dict:
    try:
        return await asyncio.wait_for(auto_apply_func(job, resume_path), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(
            "Application attempt timed out",
            timeout_seconds=timeout_seconds,
            title=getattr(job, "title", "unknown"),
            company=getattr(job, "company", "unknown"),
        )
        return {
            "success": False,
            "reason": "timeout",
            "job_url": job.apply_url,
            "manual_apply_url": job.apply_url,
        }


async def apply_with_retry(
    auto_apply_func,
    job,
    resume_path: str,
    max_attempts: int = 2,
    timeout_seconds: int = 90,
) -> dict:
    trace = None
    if langfuse:
        trace = langfuse.trace(
            name="auto_apply_with_retry",
            input={"job_title": job.title, "company": job.company, "url": job.apply_url},
        )

    last_result = None

    for attempt in range(1, max_attempts + 1):
        logger.info(
            "Auto-apply attempt",
            attempt=attempt,
            max_attempts=max_attempts,
            title=job.title,
            company=job.company,
        )

        try:
            result = await apply_with_timeout(
                auto_apply_func,
                job,
                resume_path,
                timeout_seconds,
            )

            if result.get("success"):
                if trace:
                    trace.update(output={"success": True, "attempt": attempt})
                return result

            non_retryable = {
                "external_apply",
                "captcha",
                "login_required",
                "login_failed",
                "unsupported_ats",
                "unsupported_platform",
                "no_credentials",
            }

            result_code = result.get("status") or result.get("reason")
            if result_code in non_retryable:
                if trace:
                    trace.update(
                        output={
                            "success": False,
                            "reason": result_code,
                            "retried": False,
                        }
                    )
                return result

            last_result = result
            if attempt < max_attempts:
                wait_time = attempt * 5
                logger.info("Retrying auto-apply", wait_seconds=wait_time)
                await asyncio.sleep(wait_time)

        except Exception as exc:
            if sentry_sdk:
                sentry_sdk.capture_exception(exc)
            last_result = {
                "success": False,
                "reason": f"unexpected_error: {str(exc)}",
                "job_url": job.apply_url,
                "manual_apply_url": job.apply_url,
            }

            if attempt < max_attempts:
                await asyncio.sleep(5)

    if trace:
        trace.update(
            output={
                "success": False,
                "reason": (last_result or {}).get("reason"),
                "attempts": max_attempts,
            }
        )

    logger.warning(
        "All auto-apply retries failed",
        title=getattr(job, "title", "unknown"),
        attempts=max_attempts,
    )

    return last_result or {
        "success": False,
        "reason": "unknown_failure",
        "job_url": job.apply_url,
        "manual_apply_url": job.apply_url,
    }


async def safe_apply(job, resume_path):
    from agents.auto_apply import auto_apply

    return await apply_with_retry(
        auto_apply_func=auto_apply,
        job=job,
        resume_path=resume_path,
        max_attempts=2,
        timeout_seconds=90,
    )
