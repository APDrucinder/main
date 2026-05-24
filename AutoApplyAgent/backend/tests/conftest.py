import os


os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("AUTH_REQUIRED", "true")
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("SESSION_SALT", "test-session-salt")
os.environ.setdefault("RUN_E2E_TESTS", "false")
