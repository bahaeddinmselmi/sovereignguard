"""
Circuit Breaker — Fail-Closed Safety Mechanism

If the masking or encryption subsystem fails repeatedly, the circuit
breaker OPENS and rejects all requests to prevent raw PII leakage.

States:
    CLOSED  → Normal operation. Failures are counted.
    OPEN    → Requests are rejected. No data leaves the gateway.
    HALF_OPEN → One test request is allowed through to check recovery.

This is a SECURITY circuit breaker, not a performance one.
When it opens, data does NOT flow — this prevents PII from being
sent to external providers when internal systems are broken.

Safety invariant: If masking fails, no data is sent externally.
"""

import logging
import threading
import time
from enum import Enum
from typing import Optional

from sovereignguard.config import settings
from sovereignguard.utils.exceptions import SovereignGuardError

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Rejecting all requests (fail-closed)
    HALF_OPEN = "half_open" # Testing if system recovered


class CircuitBreakerError(SovereignGuardError):
    """Raised when the circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Security-focused circuit breaker for PII masking pipeline.

    Unlike performance circuit breakers that "fail open" to maintain
    availability, this one "fails CLOSED" — when it trips, NO data
    leaves the gateway, because sending unmasked PII is worse than
    downtime.
    """

    def __init__(
        self,
        name: str = "masking",
        failure_threshold: Optional[int] = None,
        reset_timeout: Optional[int] = None,
    ):
        self.name = name
        self.failure_threshold = (
            failure_threshold or settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        )
        self.reset_timeout = (
            reset_timeout or settings.CIRCUIT_BREAKER_RESET_TIMEOUT
        )

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._last_state_change: float = time.time()
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for automatic half-open transition."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.time() - self._last_state_change
                if elapsed >= self.reset_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    def check(self):
        """
        Check if the circuit allows a request through.
        Raises CircuitBreakerError if the circuit is open.
        """
        if not settings.CIRCUIT_BREAKER_ENABLED:
            return

        current_state = self.state

        if current_state == CircuitState.OPEN:
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Masking subsystem has failed {self.failure_threshold} times. "
                f"All requests blocked to prevent PII leakage. "
                f"Will retry in {self.reset_timeout}s."
            )

        if current_state == CircuitState.HALF_OPEN:
            logger.info(
                f"circuit_breaker_half_open",
                extra={"breaker": self.name, "message": "Allowing test request"},
            )

    def record_success(self):
        """Record a successful masking operation."""
        if not settings.CIRCUIT_BREAKER_ENABLED:
            return

        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.CLOSED)
                logger.info(
                    "circuit_breaker_recovered",
                    extra={"breaker": self.name},
                )
            self._failure_count = 0

    def record_failure(self, error: Optional[Exception] = None):
        """Record a masking failure. May trip the circuit breaker."""
        if not settings.CIRCUIT_BREAKER_ENABLED:
            return

        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Failed during recovery test — reopen
                self._transition_to(CircuitState.OPEN)
                logger.error(
                    "circuit_breaker_reopened",
                    extra={
                        "breaker": self.name,
                        "error": str(error) if error else "unknown",
                    },
                )
            elif self._failure_count >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                logger.critical(
                    "circuit_breaker_tripped",
                    extra={
                        "breaker": self.name,
                        "failures": self._failure_count,
                        "message": "All external requests BLOCKED to prevent PII leakage",
                    },
                )

    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0

        logger.info(
            "circuit_breaker_transition",
            extra={
                "breaker": self.name,
                "from": old_state.value,
                "to": new_state.value,
            },
        )

    def get_status(self) -> dict:
        """Get circuit breaker status for admin endpoints."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "reset_timeout_seconds": self.reset_timeout,
            "last_failure": self._last_failure_time or None,
        }

    def force_close(self):
        """Manually close the circuit breaker (admin recovery action)."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            logger.warning(
                "circuit_breaker_force_closed",
                extra={"breaker": self.name},
            )

    def force_open(self):
        """Manually open the circuit breaker (emergency stop)."""
        with self._lock:
            self._transition_to(CircuitState.OPEN)
            logger.warning(
                "circuit_breaker_force_opened",
                extra={"breaker": self.name},
            )
