"""
Structured audit logging for SovereignGuard.

All masking/restoration events are logged to a JSONL file for
GDPR audit trail purposes. CRITICAL: Never log actual PII values.
Only log entity types, counts, and token references.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from sovereignguard.config import settings

logger = logging.getLogger(__name__)

_audit_logger: logging.Logger | None = None


def setup_audit_logging():
    """Initialize the audit log file handler."""
    global _audit_logger

    if not settings.AUDIT_LOGGING_ENABLED:
        return

    log_path = Path(settings.AUDIT_LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _audit_logger = logging.getLogger("sovereignguard.audit")
    _audit_logger.setLevel(logging.INFO)
    _audit_logger.propagate = False

    handler = logging.FileHandler(str(log_path), encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    _audit_logger.addHandler(handler)

    logger.info(f"Audit logging initialized: {log_path}")


def audit_log(event: str, **kwargs: Any):
    """
    Write a structured audit log entry.

    Args:
        event: Event type (e.g., "TEXT_MASKED", "SESSION_ENDED")
        **kwargs: Additional fields (NEVER include PII values)
    """
    if not settings.AUDIT_LOGGING_ENABLED:
        return

    entry = {
        "timestamp": time.time(),
        "event": event,
        **kwargs,
    }

    if _audit_logger:
        _audit_logger.info(json.dumps(entry, default=str))
    else:
        # Fallback to standard logger during early startup
        logger.info(f"AUDIT: {json.dumps(entry, default=str)}")
