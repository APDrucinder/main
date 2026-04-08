import sentry_sdk
from fastapi import FastAPI
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# --- COMMENT THIS ENTIRE BLOCK OUT FOR NOW ---
# dsn = os.getenv("SENTRY_DSN")
# if dsn:
#     sentry_sdk.init(
#         dsn=dsn,
#         traces_sample_rate=0.5
#     )
# ---------------------------------------------

# Keep the rest of your app routes below...
from fastapi.middleware.cors import CORSMiddleware
from api.resume_routes import router as resume_router
from api.preferences_routes import router as prefs_router

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_router)
app.include_router(prefs_router)

@app.get("/health")
def health():
    return {"status": "running"}