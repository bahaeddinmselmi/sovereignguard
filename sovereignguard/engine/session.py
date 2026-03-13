"""
Per-request session management for SovereignGuard.

Each API request gets an isolated session with its own PII mapping namespace.
Sessions are created at request start and destroyed at request end.
"""

import uuid
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """Represents a single request/response masking session."""
    session_id: str
    created_at: float = field(default_factory=time.time)
    entity_count: int = 0
    is_active: bool = True

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


class SessionManager:
    """Manages active masking sessions."""

    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def create(self) -> Session:
        session_id = str(uuid.uuid4())
        session = Session(session_id=session_id)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def close(self, session_id: str):
        session = self._sessions.pop(session_id, None)
        if session:
            session.is_active = False

    @property
    def active_count(self) -> int:
        return len(self._sessions)
