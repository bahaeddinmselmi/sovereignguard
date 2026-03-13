"""
GDPR Audit Report Generator

Reads audit log entries and produces structured reports showing:
- What types of PII were processed
- When processing occurred
- Volume statistics
- NEVER reveals actual PII values
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from collections import Counter
from datetime import datetime

from sovereignguard.config import settings

logger = logging.getLogger(__name__)


def generate_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a GDPR-compliant audit report from the audit log.

    Args:
        start_date: ISO date string (e.g., "2024-01-01")
        end_date: ISO date string

    Returns:
        Report dict with statistics (no PII values)
    """
    log_path = Path(settings.AUDIT_LOG_PATH)

    if not log_path.exists():
        return {
            "status": "no_data",
            "message": "No audit log entries found.",
            "generated_at": datetime.utcnow().isoformat(),
        }

    start_ts = _parse_date(start_date) if start_date else 0
    end_ts = _parse_date(end_date, end_of_day=True) if end_date else float("inf")

    entries: List[Dict] = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = _to_unix_timestamp(entry.get("timestamp", 0))
                if start_ts <= ts <= end_ts:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue

    if not entries:
        return {
            "status": "no_data",
            "message": "No audit entries in the specified date range.",
            "generated_at": datetime.utcnow().isoformat(),
            "filters": {"start_date": start_date, "end_date": end_date},
        }

    # Aggregate statistics
    event_counts = Counter(e.get("event") for e in entries)
    entity_type_counts: Counter = Counter()
    total_entities_masked = 0
    total_tokens_restored = 0
    sessions_count = 0

    for entry in entries:
        if entry.get("event") == "TEXT_MASKED":
            total_entities_masked += entry.get("entity_count", 0)
            for et in entry.get("entity_types", []):
                entity_type_counts[et] += 1

        if entry.get("event") == "TEXT_RESTORED":
            total_tokens_restored += entry.get("tokens_restored", 0)

        if entry.get("event") == "SESSION_ENDED":
            sessions_count += 1

    return {
        "status": "ok",
        "generated_at": datetime.utcnow().isoformat(),
        "filters": {"start_date": start_date, "end_date": end_date},
        "summary": {
            "total_events": len(entries),
            "total_sessions": sessions_count,
            "total_entities_masked": total_entities_masked,
            "total_tokens_restored": total_tokens_restored,
        },
        "events_breakdown": dict(event_counts),
        "entity_types_detected": dict(entity_type_counts),
        "compliance_note": (
            "This report contains no PII values. "
            "All counts refer to token operations only."
        ),
    }


def _parse_date(date_str: str, end_of_day: bool = False) -> float:
    """Parse ISO date string to Unix timestamp."""
    dt = datetime.fromisoformat(date_str)
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return dt.timestamp()


def _to_unix_timestamp(value: Any) -> float:
    """Normalize timestamp values from audit logs into Unix seconds."""
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        # Handle RFC3339/ISO strings, including trailing Z.
        iso = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(iso).timestamp()
        except ValueError:
            return 0.0

    return 0.0
