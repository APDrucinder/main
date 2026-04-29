"""
Daily Digest Agent
──────────────────
Queries each user's last 24h applications, summarises via Claude,
sends email via SendGrid, and WhatsApp via Twilio for Pro/Power users.
Scheduled via Celery Beat at 7pm every day.
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta

from shared.base_agent import BaseAgent
from shared.logger import logger
from database.connection import AsyncSessionLocal
from database.models import Application, Job, User
from sqlalchemy import select

# ─── Config ───────────────────────────────────────────────────
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM = os.getenv("SENDGRID_FROM_EMAIL", "digest@yourdomain.com")

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

PRO_TIERS = {"pro", "power"}


class DailyDigestAgent(BaseAgent):

    def __init__(self):
        super().__init__("daily_digest")
        self.sg = None
        if SENDGRID_API_KEY:
            try:
                import sendgrid

                self.sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
            except Exception as exc:
                logger.warning("SendGrid SDK unavailable, email digest disabled", error=str(exc))

        self.twilio = None
        if TWILIO_SID and TWILIO_TOKEN:
            try:
                from twilio.rest import Client as TwilioClient

                self.twilio = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
            except Exception as exc:
                logger.warning("Twilio SDK unavailable, WhatsApp digest disabled", error=str(exc))

    # ─── Main Runner ──────────────────────────────────────────

    async def run_digest_for_all_users(self):
        """Entry point — fetch all users, run digest for each."""
        logger.info("Daily digest starting")

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()

        logger.info("Users to process", count=len(users))

        for user in users:
            try:
                await self.run_digest_for_user(user)
            except Exception as e:
                logger.error(
                    "Digest failed for user",
                    user_id=str(user.id),
                    error=str(e)
                )

        logger.info("Daily digest complete")

    async def run_digest_for_user(self, user: User):
        """Full digest flow for a single user."""
        logger.info("Running digest", user_id=str(user.id), email=user.email)

        # Step 1: Fetch last 24h applications
        applications = await self._fetch_recent_applications(str(user.id))

        if not applications:
            logger.info("No applications in last 24h, skipping", user_id=str(user.id))
            return

        # Step 2: Build summary via Claude
        email_html, plain_text = await self._build_digest(user, applications)

        # Step 3: Send email
        self._send_email(user.email, email_html)

        # Step 4: WhatsApp for Pro/Power users
        if user.subscription_tier in PRO_TIERS:
            phone = getattr(user, "phone", None)
            if phone:
                self._send_whatsapp(phone, plain_text)
            else:
                logger.info(
                    "Pro user has no phone number, skipping WhatsApp",
                    user_id=str(user.id)
                )

    # ─── Database Query ───────────────────────────────────────

    async def _fetch_recent_applications(self, user_id: str) -> list:
        """Get all applications from last 24 hours for a user."""
        user_uuid = uuid.UUID(str(user_id))
        cutoff = datetime.utcnow() - timedelta(hours=24)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Application, Job)
                .join(Job, Application.job_id == Job.id)
                .where(Application.user_id == user_uuid)
                .where(Application.applied_at >= cutoff)
                .order_by(Application.match_score.desc())
            )
            rows = result.all()

        return rows  # list of (Application, Job) tuples

    # ─── LLM Summary ──────────────────────────────────────────

    async def _build_digest(self, user: User, applications: list) -> tuple[str, str]:
        """Ask Claude to summarise applications and format for email + WhatsApp."""

        # Build application list for prompt
        app_lines = []
        for i, (app, job) in enumerate(applications, 1):
            status_emoji = "✅" if app.status == "applied" else "⏳" if app.status == "matched" else "📋"
            app_lines.append(
                f"{i}. {status_emoji} {job.title} at {job.company} ({job.location})\n"
                f"   Match Score: {app.match_score}/100\n"
                f"   Matched Skills: {', '.join(app.matched_skills or [])}\n"
                f"   Missing Skills: {', '.join(app.missing_skills or [])}\n"
                f"   Reasoning: {app.reasoning}\n"
                f"   Status: {app.status}\n"
                f"   URL: {job.apply_url}"
            )

        apps_text = "\n\n".join(app_lines)

        prompt = f"""
You are writing a daily job application digest for a job seeker.
Write a clear, friendly, human-readable summary of their activity from the last 24 hours.

User: {user.email}
Total applications: {len(applications)}
Date: {datetime.utcnow().strftime("%B %d, %Y")}

Applications:
{apps_text}

Write two versions:

1. EMAIL VERSION (HTML): 
   - Start with a short friendly opening line
   - Show each application as a clean card with: role, company, score, matched skills, missing skills, status
   - Use simple HTML — <h2>, <p>, <ul>, <li>, <strong>, <a href>
   - End with a motivational closing line
   - Highlight any applications that need attention (manual_queue status)
   - Format scores visually — e.g. "87/100 ⭐" 

2. WHATSAPP VERSION (plain text, max 300 words):
   - Ultra concise
   - Just the highlights: how many applied, top 3 matches, any flagged items
   - Friendly tone, use emojis

Separate the two versions with exactly this line:
---WHATSAPP---
"""

        response = await self._call_llm(
            prompt=prompt,
            max_tokens=8000,
            trace_name="daily_digest"
        )

        # Split into email and whatsapp parts
        if "---WHATSAPP---" in response:
            parts = response.split("---WHATSAPP---")
            email_content = parts[0].strip()
            whatsapp_content = parts[1].strip()
        else:
            email_content = response
            whatsapp_content = f"📊 Daily Digest: {len(applications)} applications sent today. Check your email for details."

        # Wrap email in full HTML template
        email_html = self._wrap_email_html(email_content, user.email, len(applications))

        return email_html, whatsapp_content

    # ─── Email ────────────────────────────────────────────────

    def _wrap_email_html(self, content: str, email: str, count: int) -> str:
        """Wrap LLM content in a clean email template."""
        date_str = datetime.utcnow().strftime("%B %d, %Y")
        return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
    .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
    .header {{ background: #1a1a2e; color: white; padding: 32px; text-align: center; }}
    .header h1 {{ margin: 0; font-size: 24px; }}
    .header p {{ margin: 8px 0 0; color: #aaa; font-size: 14px; }}
    .body {{ padding: 32px; }}
    .stat {{ display: inline-block; background: #f0f4ff; border-radius: 8px; padding: 12px 20px; margin: 4px; text-align: center; }}
    .stat .number {{ font-size: 28px; font-weight: bold; color: #4361ee; }}
    .stat .label {{ font-size: 12px; color: #666; }}
    .footer {{ background: #f9f9f9; padding: 20px; text-align: center; color: #999; font-size: 12px; border-top: 1px solid #eee; }}
    a {{ color: #4361ee; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>📊 Your Daily Job Digest</h1>
      <p>{date_str} • {count} applications</p>
    </div>
    <div class="body">
      <div style="text-align:center; margin-bottom: 24px;">
        <div class="stat">
          <div class="number">{count}</div>
          <div class="label">Applications</div>
        </div>
      </div>
      {content}
    </div>
    <div class="footer">
      You're receiving this because you use our auto-apply service.<br>
      <a href="#">Manage preferences</a> · <a href="#">Unsubscribe</a>
    </div>
  </div>
</body>
</html>
"""

    def _send_email(self, to_email: str, html_content: str) -> None:
        """Send digest email via SendGrid."""
        if not self.sg:
            logger.warning("SendGrid not configured, skipping digest email", to=to_email)
            return
        try:
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email=SENDGRID_FROM,
                to_emails=to_email,
                subject=f"📊 Your Daily Job Digest — {datetime.utcnow().strftime('%b %d')}",
                html_content=html_content
            )

            response = self.sg.send(message)
            logger.info(
                "Email sent",
                to=to_email,
                status=response.status_code
            )
        except Exception as e:
            logger.error("Email send failed", to=to_email, error=str(e))

    # ─── WhatsApp ─────────────────────────────────────────────

    def _send_whatsapp(self, phone: str, message: str) -> None:
        """Send WhatsApp digest via Twilio for Pro/Power users."""
        if not self.twilio:
            logger.warning("Twilio not configured, skipping WhatsApp")
            return

        try:
            # Ensure phone is in correct format
            if not phone.startswith("whatsapp:"):
                to_number = f"whatsapp:+{phone.strip().lstrip('+')}"
            else:
                to_number = phone

            self.twilio.messages.create(
                body=message,
                from_=TWILIO_WHATSAPP_FROM,
                to=to_number
            )
            logger.info("WhatsApp sent", to=phone)
        except Exception as e:
            logger.error("WhatsApp send failed", to=phone, error=str(e))


# ─── Celery Task ──────────────────────────────────────────────

def run_daily_digest():
    """Synchronous wrapper for Celery to call."""
    agent = DailyDigestAgent()
    asyncio.run(agent.run_digest_for_all_users())
