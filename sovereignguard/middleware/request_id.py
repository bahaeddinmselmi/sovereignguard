"""
Request ID Correlation Middleware

Generates a unique request ID for each incoming request and propagates
it through logs and response headers for end-to-end tracing.
"""

import uuid
import logging
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Context variable for request ID — accessible from any async code
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Assigns a unique X-Request-ID to each request.

    If the client provides an X-Request-ID header, it is used.
    Otherwise, a new UUID is generated.

    The request ID is:
    - Stored in a ContextVar for use in logging
    - Added to the response headers
    - Forwarded to the target LLM API
    """

    async def dispatch(self, request: Request, call_next):
        # Use client-provided ID or generate one
        req_id = request.headers.get("x-request-id", str(uuid.uuid4()))

        # Store in context for structured logging
        token = request_id_var.set(req_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_var.reset(token)
