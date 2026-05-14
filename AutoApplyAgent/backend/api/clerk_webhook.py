from fastapi import APIRouter, Request, HTTPException
from svix.webhooks import Webhook
import os
import uuid
from sqlalchemy import select

from database.connection import AsyncSessionLocal
from database.models import User

router = APIRouter()

@router.post("/webhooks/clerk")
async def clerk_webhook(request: Request):
    payload = await request.body()
    headers = dict(request.headers)
    
    webhook_secret = os.getenv("CLERK_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Missing CLERK_WEBHOOK_SECRET in environment")

    wh = Webhook(webhook_secret)
    
    try:
        event = wh.verify(payload, headers)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    if event.get("type") == "user.created":
        data = event.get("data", {})
        email_addresses = data.get("email_addresses", [])
        email = email_addresses[0].get("email_address") if email_addresses else None
        clerk_id = data.get("id")
        
        if not email or not clerk_id:
            raise HTTPException(status_code=400, detail="Missing required user data (email or clerk_id)")

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.clerk_id == clerk_id))
            user = result.scalar_one_or_none()
            
            if not user:
                user = User(
                    id=uuid.uuid4(),
                    clerk_id=clerk_id,
                    email=email,
                    subscription_tier="free"
                )
                db.add(user)
                await db.commit()
    
    return {"status": "ok"}
