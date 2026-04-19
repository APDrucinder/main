import asyncio
import os
import sys
import uuid
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import delete, select, text

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database.connection import AsyncSessionLocal, Base, engine
from database.models import Application, Job, JobPreference, User
from workers.pipeline_task import execute_pipeline_task

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000123")
TEST_URLS = {
    "applied": "https://codex-verify.example/jobs/applied",
    "failed": "https://codex-verify.example/jobs/failed",
    "matched": "https://codex-verify.example/jobs/matched",
}


class FakeTask:
    def __init__(self):
        self.updates = []

    def update_state(self, state, meta):
        self.updates.append({"state": state, "meta": meta})


def fake_result(title: str, url: str, score: int, reason: str, matched_skills: list[str], missing_skills: list[str]):
    job = SimpleNamespace(
        title=title,
        company="Codex Verify Inc",
        location="Bangalore",
        description=f"{title} verification listing",
        salary_range="20-30 LPA",
        apply_url=url,
        source="verification",
        posted_date=datetime.utcnow(),
    )
    return SimpleNamespace(
        job=job,
        passed=True,
        score=score,
        reason=reason,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
    )


async def fake_pipeline_runner(**kwargs):
    resume = SimpleNamespace(
        name="Codex Verifier",
        email="codex-verifier@example.com",
        phone="+91-9999999999",
        skills=["python", "sqlalchemy", "playwright"],
        total_experience_years=4,
    )
    scored_results = [
        fake_result(
            title="Applied Role",
            url=TEST_URLS["applied"],
            score=95,
            reason="Excellent overlap with backend and automation requirements.",
            matched_skills=["python", "sqlalchemy"],
            missing_skills=["redis"],
        ),
        fake_result(
            title="Manual Apply Role",
            url=TEST_URLS["failed"],
            score=91,
            reason="Strong fit, but the automation path should fail in this verification.",
            matched_skills=["python", "playwright"],
            missing_skills=["graphql"],
        ),
        fake_result(
            title="Matched Only Role",
            url=TEST_URLS["matched"],
            score=72,
            reason="Good enough to save, but below the auto-apply threshold.",
            matched_skills=["python"],
            missing_skills=["kubernetes"],
        ),
    ]
    return SimpleNamespace(
        resume=resume,
        scored_results=scored_results,
        passed_results=scored_results,
        failed_results=[],
    )


def fake_auto_apply(job_url: str, user_id: str, job_id: uuid.UUID, user_data: dict):
    if job_url == TEST_URLS["applied"]:
        return SimpleNamespace(
            success=True,
            final_url=job_url,
            manual_apply_url=None,
            failure_reason=None,
        )

    if job_url == TEST_URLS["failed"]:
        return SimpleNamespace(
            success=False,
            final_url=job_url,
            manual_apply_url=job_url,
            failure_reason="Simulated auto-apply failure",
        )

    raise AssertionError(f"Auto-apply should not have been attempted for {job_url}")


async def ensure_schema_and_seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("ALTER TABLE applications ADD COLUMN IF NOT EXISTS manual_apply_url TEXT")
        )

    async with AsyncSessionLocal() as session:
        existing_user = await session.get(User, TEST_USER_ID)
        if existing_user is None:
            session.add(
                User(
                    id=TEST_USER_ID,
                    clerk_id="codex-verifier-clerk",
                    email="codex-verifier@example.com",
                    subscription_tier="pro",
                )
            )

        existing_pref = await session.execute(
            select(JobPreference).where(
                JobPreference.user_id == TEST_USER_ID,
                JobPreference.is_active == True,
            )
        )
        pref = existing_pref.scalar_one_or_none()
        if pref is None:
            session.add(
                JobPreference(
                    id=uuid.uuid4(),
                    user_id=TEST_USER_ID,
                    target_roles=["backend engineer"],
                    locations=["Bangalore"],
                    remote_ok=False,
                    auto_apply_threshold=80,
                    is_active=True,
                )
            )
        else:
            pref.target_roles = ["backend engineer"]
            pref.locations = ["Bangalore"]
            pref.remote_ok = False
            pref.auto_apply_threshold = 80
            pref.is_active = True

        await session.commit()


async def cleanup_verification_rows():
    async with AsyncSessionLocal() as session:
        jobs_result = await session.execute(
            select(Job.id).where(Job.apply_url.in_(list(TEST_URLS.values())))
        )
        job_ids = list(jobs_result.scalars().all())

        if job_ids:
            await session.execute(
                delete(Application).where(
                    Application.user_id == TEST_USER_ID,
                    Application.job_id.in_(job_ids),
                )
            )

        await session.execute(
            delete(Job).where(Job.apply_url.in_(list(TEST_URLS.values())))
        )
        await session.commit()


async def fetch_saved_rows():
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(Application, Job)
            .join(Job, Application.job_id == Job.id)
            .where(
                Application.user_id == TEST_USER_ID,
                Job.apply_url.in_(list(TEST_URLS.values())),
            )
            .order_by(Job.apply_url.asc())
        )
        return rows.all()


def assert_saved_rows(rows):
    assert len(rows) == 3, f"Expected 3 application rows, found {len(rows)}"

    by_url = {
        job.apply_url: {
            "status": application.status,
            "manual_apply_url": application.manual_apply_url,
            "match_score": application.match_score,
            "matched_skills": application.matched_skills,
            "missing_skills": application.missing_skills,
            "reasoning": application.reasoning,
        }
        for application, job in rows
    }

    assert by_url[TEST_URLS["applied"]]["status"] == "applied"
    assert by_url[TEST_URLS["applied"]]["manual_apply_url"] is None

    assert by_url[TEST_URLS["failed"]]["status"] == "failed"
    assert by_url[TEST_URLS["failed"]]["manual_apply_url"] == TEST_URLS["failed"]

    assert by_url[TEST_URLS["matched"]]["status"] == "matched"
    assert by_url[TEST_URLS["matched"]]["manual_apply_url"] is None


async def count_jobs():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Job).where(Job.apply_url.in_(list(TEST_URLS.values())))
        )
        return len(result.scalars().all())


async def run_verification():
    import workers.pipeline_task as pipeline_task_module

    pipeline_task_module.AUTO_APPLY_ENABLED = True
    pipeline_task_module.AUTO_APPLY_DRY_RUN = True

    task = FakeTask()
    first_run = await execute_pipeline_task(
        task,
        str(TEST_USER_ID),
        resume_path=os.path.join(BACKEND_DIR, "Dhruv_Resume.pdf"),
        locations=["Bangalore"],
        pipeline_runner=fake_pipeline_runner,
        auto_apply_callable=fake_auto_apply,
    )
    second_run = await execute_pipeline_task(
        task,
        str(TEST_USER_ID),
        resume_path=os.path.join(BACKEND_DIR, "Dhruv_Resume.pdf"),
        locations=["Bangalore"],
        pipeline_runner=fake_pipeline_runner,
        auto_apply_callable=fake_auto_apply,
    )
    return task, first_run, second_run


async def main():
    await ensure_schema_and_seed()
    await cleanup_verification_rows()

    task, first_run, second_run = await run_verification()

    rows = await fetch_saved_rows()
    assert_saved_rows(rows)
    job_count = await count_jobs()

    assert job_count == 3, f"Expected 3 distinct jobs after two runs, found {job_count}"

    print("Verification task updates:", len(task.updates))
    print("First run summary:", first_run)
    print("Second run summary:", second_run)
    print("Saved rows:")
    for application, job in rows:
        print(
            {
                "title": job.title,
                "status": application.status,
                "match_score": application.match_score,
                "manual_apply_url": application.manual_apply_url,
                "matched_skills": application.matched_skills,
                "missing_skills": application.missing_skills,
            }
        )


if __name__ == "__main__":
    asyncio.run(main())
