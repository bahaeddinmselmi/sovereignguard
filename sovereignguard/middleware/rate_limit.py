"""
Rate Limiting Middleware

Sliding window rate limiter using in-memory storage.
Limits requests per client IP to prevent abuse and DoS attacks.
"""

import time
import logging
from collections import defaultdict
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from sovereignguard.config import settings

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """Thread-safe sliding window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """
        Check if a request is allowed for the given key.
        Returns (allowed, remaining_requests).
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            # Remove expired entries
            self._requests[key] = [
                ts for ts in self._requests[key] if ts > window_start
            ]

            current_count = len(self._requests[key])

            if current_count >= self.max_requests:
                return False, 0

            self._requests[key].append(now)
            return True, self.max_requests - current_count - 1


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP rate limiting middleware.

    Adds standard rate limit headers to responses:
    - X-RateLimit-Limit: Maximum requests per window
    - X-RateLimit-Remaining: Remaining requests in window
    - Retry-After: Seconds until rate limit resets (on 429)
    """

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self.limiter = SlidingWindowRateLimiter(
            max_requests=settings.RATE_LIMIT_RPM,
            window_seconds=60,
        )

    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        allowed, remaining = self.limiter.is_allowed(client_ip)

        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": "Rate limit exceeded. Please retry after 60 seconds.",
                        "type": "rate_limit_error",
                        "code": "rate_limit_exceeded",
                    }
                },
            )
            response.headers["Retry-After"] = "60"
            response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_RPM)
            response.headers["X-RateLimit-Remaining"] = "0"
            return response

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_RPM)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
