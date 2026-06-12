"""
Structured logging configuration using Loguru.

=== WHY THIS FILE EXISTS ===
Logging is the #1 debugging tool in production. When your RAG system returns
a bad answer at 3am, logs are how you figure out what went wrong. This module
sets up structured, rotated, and filterable logging for the entire application.

=== HOW IT INTERACTS WITH OTHER MODULES ===
Every module imports the logger:
    from app.core.logging import logger
    logger.info("Processing document", filename="report.pdf", chunks=42)

The logger is configured ONCE at application startup (in main.py).

=== WHAT HAPPENS WITHOUT IT ===
- print() statements everywhere (can't filter, can't search, no timestamps)
- Python's built-in logging requires 5+ lines of boilerplate per module
- No log rotation — disk fills up in production
- No structured data — can't query logs programmatically

=== INDUSTRY ALTERNATIVES ===
- Python logging + structlog: More standard, more verbose setup
- OpenTelemetry: For distributed tracing across microservices
- ELK Stack (Elasticsearch + Logstash + Kibana): For log aggregation at scale
- Datadog / Splunk: Paid SaaS log management
"""

import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


# Project root for log file storage
_LOG_DIR = Path(settings.DATA_DIR).parent / "logs"


def setup_logging() -> None:
    """
    Configure application logging.

    This function should be called ONCE at application startup.
    It configures:
    1. Console output with colors and human-readable format
    2. File output with rotation and JSON format (production-friendly)
    3. Error-specific log file for quick debugging

    Design Decisions:
    - Loguru over stdlib logging: Loguru has a cleaner API, built-in rotation,
      structured logging, and beautiful console output — all with zero config.
    - Two log files: General logs for everything, error logs for quick triage.
    - 10MB rotation with 7-day retention: Prevents disk exhaustion while keeping
      enough history for debugging.
    - JSON format for file logs: Enables programmatic log analysis with tools
      like jq, Elasticsearch, or custom scripts.
    """
    # Remove default Loguru handler (avoid duplicate console output)
    logger.remove()

    # ── Console Handler ─────────────────────────────────────────────
    # Human-readable format for development
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
            "{exception}"
        ),
        colorize=True,
        backtrace=True,
        diagnose=settings.DEBUG,  # Show variable values in tracebacks (dev only)
    )

    # ── File Handler (General) ──────────────────────────────────────
    # Structured JSON logs for production analysis
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(_LOG_DIR / "rag_system.log"),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="10 MB",       # Rotate when file reaches 10MB
        retention="7 days",     # Keep logs for 7 days
        compression="zip",      # Compress rotated logs
        serialize=False,        # Set True for JSON format in production
    )

    # ── File Handler (Errors Only) ──────────────────────────────────
    # Separate error log for quick triage
    logger.add(
        str(_LOG_DIR / "errors.log"),
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}\n{exception}",
        rotation="10 MB",
        retention="30 days",    # Keep error logs longer
        compression="zip",
        backtrace=True,
        diagnose=True,          # Always show details for errors
    )

    logger.info(
        "Logging configured",
        log_level=settings.LOG_LEVEL,
        debug_mode=settings.DEBUG,
        log_dir=str(_LOG_DIR),
    )


def get_logger(name: str) -> "logger":
    """
    Get a contextualized logger for a specific module.

    Usage:
        logger = get_logger(__name__)
        logger.info("Something happened")

    Why contextualized loggers?
    - Each log line shows which module produced it
    - You can filter logs by module name
    - Matches the pattern used by Python's stdlib logging

    Args:
        name: Module name, typically __name__

    Returns:
        A Loguru logger instance bound with the module context.
    """
    return logger.bind(module=name)
