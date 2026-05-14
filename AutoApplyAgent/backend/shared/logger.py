"""
Centralized logging configuration using loguru.
Import `logger` from this module everywhere instead of using print() or stdlib logging.

Usage:
    from shared.logger import logger
    logger.info("Scraping jobs", role="python developer", location="Bangalore")
"""

import sys
import os
from loguru import logger

# Remove default loguru handler
logger.remove()

# Determine environment
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"

if IS_PRODUCTION:
    # Production: structured JSON logs for log aggregators (Datadog, CloudWatch, etc.)
    logger.add(
        sys.stdout,
        format="{message}",
        serialize=True,  # JSON output
        level="INFO",
        backtrace=False,
        diagnose=False,  # Don't leak local variables in production tracebacks
    )
else:
    # Development: human-readable colorized output
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>",
        level="DEBUG",
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

# File log: always write structured logs to file for post-mortem debugging
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger.add(
    os.path.join(LOG_DIR, "agent_{time:YYYY-MM-DD}.log"),
    rotation="50 MB",
    retention="30 days",
    compression="gz",
    serialize=True,
    level="DEBUG",
)
