# backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.resume_routes import router as resume_router
from api.preferences_routes import router as preferences_router
from api.scan_routes import router as scan_router
from api.application_routes import router as application_router
import sentry_sdk
import os
from dotenv import load_dotenv

load_dotenv()

dsn = os.getenv("SENTRY_DSN")
if dsn and dsn.startswith("https://"):
    sentry_sdk.init(dsn=dsn, traces_sample_rate=0.5)

app = FastAPI(title="AIAgents API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_router)
app.include_router(preferences_router)
app.include_router(scan_router)
app.include_router(application_router)

@app.get("/health")
def health():
    return {"status": "running"}