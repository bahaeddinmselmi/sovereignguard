"""
Immutable Audit Logger — Tamper-Evident Cryptographic Log Chain

Each log entry is cryptographically chained to the previous one
using SHA-256 hashing, creating a blockchain-like audit trail.

If any entry is tampered with, the chain breaks and verification fails.

Structure of each entry:
{
    "sequence": 42,
    "timestamp": "2025-12-25T10:30:00.000Z",
    "event": "TEXT_MASKED",
    "data": {...},
    "prev_hash": "a3f9b2c1...",   ← hash of previous entry
    "entry_hash": "d4e5f6a7..."   ← hash of this entry (without entry_hash)
}

Verification:
    For each entry N:
        1. Remove entry_hash from the entry
        2. Compute SHA-256 of the remaining JSON
        3. Verify it equals entry_hash
        4. Verify prev_hash equals entry[N-1].entry_hash
"""

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sovereignguard.config import settings

logger = logging.getLogger(__name__)


class ImmutableAuditLogger:
    """
    Cryptographically chained audit logger.

    Each log entry contains a hash of the previous entry,
    making the entire log tamper-evident. Modifying any entry
    causes a chain break detectable by verify_chain().
    """

    def __init__(self, log_path: Optional[str] = None):
        self._log_path = Path(log_path or settings.AUDIT_LOG_PATH)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._sequence = 0
        self._prev_hash = "GENESIS"  # First entry's prev_hash
        self._initialized = False

    def initialize(self):
        """Load existing chain state from the log file."""
        if self._initialized:
            return

        if self._log_path.exists():
            try:
                with open(self._log_path, "r", encoding="utf-8") as f:
                    last_entry = None
                    for line in f:
                        line = line.strip()
                        if line:
                            last_entry = json.loads(line)
                            self._sequence = last_entry.get("sequence", 0)

                    if last_entry:
                        self._prev_hash = last_entry.get("entry_hash", "GENESIS")
                        self._sequence += 1

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Could not resume chain from existing log: {e}")
                # Start fresh chain but don't truncate existing file
                self._sequence = 0
                self._prev_hash = "GENESIS"

        self._initialized = True

    def log(self, event: str, **data: Any):
        """
        Write a tamper-evident audit entry.

        Args:
            event: Event type (TEXT_MASKED, TEXT_RESTORED, etc.)
            **data: Event-specific data (NEVER include raw PII)
        """
        if not settings.AUDIT_LOGGING_ENABLED:
            return

        if not self._initialized:
            self.initialize()

        with self._lock:
            entry = {
                "sequence": self._sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event,
                "data": data,
                "prev_hash": self._prev_hash,
            }

            # Compute hash of this entry (without entry_hash field)
            entry_hash = self._compute_hash(entry)
            entry["entry_hash"] = entry_hash

            # Write atomically
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
                f.flush()
                os.fsync(f.fileno())

            # Update chain state
            self._prev_hash = entry_hash
            self._sequence += 1

    @staticmethod
    def _compute_hash(entry: Dict) -> str:
        """Compute SHA-256 hash of a log entry (excluding entry_hash)."""
        canonical = json.dumps(entry, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def verify_chain(self, log_path: Optional[str] = None) -> Dict:
        """
        Verify the integrity of the audit log chain.

        Returns a verification report:
        {
            "valid": True/False,
            "entries_checked": 100,
            "first_broken_at": None or sequence_number,
            "errors": []
        }
        """
        path = Path(log_path) if log_path else self._log_path
        report = {
            "valid": True,
            "entries_checked": 0,
            "first_broken_at": None,
            "errors": [],
        }

        if not path.exists():
            report["errors"].append("Log file does not exist")
            report["valid"] = False
            return report

        prev_hash = "GENESIS"

        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as e:
                    report["valid"] = False
                    report["errors"].append(f"Line {line_num}: invalid JSON — {e}")
                    if report["first_broken_at"] is None:
                        report["first_broken_at"] = line_num
                    continue

                report["entries_checked"] += 1
                stored_hash = entry.pop("entry_hash", None)

                # Verify this entry's hash
                computed_hash = self._compute_hash(entry)
                if computed_hash != stored_hash:
                    report["valid"] = False
                    report["errors"].append(
                        f"Sequence {entry.get('sequence')}: "
                        f"hash mismatch (entry tampered)"
                    )
                    if report["first_broken_at"] is None:
                        report["first_broken_at"] = entry.get("sequence")

                # Verify chain link
                if entry.get("prev_hash") != prev_hash:
                    report["valid"] = False
                    report["errors"].append(
                        f"Sequence {entry.get('sequence')}: "
                        f"chain break (prev_hash mismatch)"
                    )
                    if report["first_broken_at"] is None:
                        report["first_broken_at"] = entry.get("sequence")

                prev_hash = stored_hash

        return report


# Module-level singleton
_immutable_logger: Optional[ImmutableAuditLogger] = None


def get_immutable_logger() -> ImmutableAuditLogger:
    """Get the global immutable audit logger instance."""
    global _immutable_logger
    if _immutable_logger is None:
        _immutable_logger = ImmutableAuditLogger()
    return _immutable_logger


def immutable_audit_log(event: str, **data: Any):
    """Convenience function for writing immutable audit entries."""
    get_immutable_logger().log(event, **data)
