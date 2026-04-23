import asyncio
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from langfuse import Langfuse
import sentry_sdk

langfuse = Langfuse()

class ApplicationTimeoutError(Exception):
    pass

class ApplicationRetryableError(Exception):
    pass

async def apply_with_timeout(
    auto_apply_func,
    job,
    resume_path: str,
    timeout_seconds: int = 90
) -> dict:
    
    try:
        result = await asyncio.wait_for(
            auto_apply_func(job, resume_path),
            timeout=timeout_seconds
        )
        return result
        
    except asyncio.TimeoutError:
        print(f"Timeout after {timeout_seconds}s: "
              f"{job.title} at {job.company}")
        
        return {
            "success": False,
            "reason": "timeout",
            "job_url": job.apply_url,
            "manual_apply_url": job.apply_url
        }

async def apply_with_retry(
    auto_apply_func,
    job,
    resume_path: str,
    max_attempts: int = 2,
    timeout_seconds: int = 90
) -> dict:
    
    trace = langfuse.trace(
        name="auto_apply_with_retry",
        input={
            "job_title": job.title,
            "company": job.company,
            "url": job.apply_url
        }
    )
    
    last_result = None
    
    for attempt in range(1, max_attempts + 1):
        
        print(f"Attempt {attempt}/{max_attempts}: "
              f"{job.title} at {job.company}")
        
        try:
            result = await apply_with_timeout(
                auto_apply_func,
                job,
                resume_path,
                timeout_seconds
            )
            
            if result["success"]:
                trace.update(
                    output={"success": True,
                            "attempt": attempt}
                )
                return result
            
            # Don't retry these failure modes
            # — they won't succeed on retry
            non_retryable = [
                "external_apply",
                "captcha",
                "login_required",
                "unsupported_ats"
            ]
            
            if result.get("reason") in non_retryable:
                trace.update(
                    output={
                        "success": False,
                        "reason": result["reason"],
                        "retried": False
                    }
                )
                return result
            
            last_result = result
            
            if attempt < max_attempts:
                wait_time = attempt * 5
                # 5 seconds before retry
                print(f"Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            sentry_sdk.capture_exception(e)
            last_result = {
                "success": False,
                "reason": f"unexpected_error: {str(e)}",
                "job_url": job.apply_url,
                "manual_apply_url": job.apply_url
            }
            
            if attempt < max_attempts:
                await asyncio.sleep(5)
    
    # All attempts failed
    trace.update(
        output={
            "success": False,
            "reason": last_result.get("reason"),
            "attempts": max_attempts
        }
    )
    
    print(f"All {max_attempts} attempts failed: "
          f"{job.title}")
    
    return last_result


# Add this to pipeline.py
# Replace direct auto_apply call with this:

async def safe_apply(job, resume_path):
    from agents.auto_apply import auto_apply
    
    return await apply_with_retry(
        auto_apply_func=auto_apply,
        job=job,
        resume_path=resume_path,
        max_attempts=2,
        timeout_seconds=90
    )