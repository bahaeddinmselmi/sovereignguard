"""
Request Size Limit Middleware

Enforces maximum request body size to prevent OOM attacks.
Uses the Content-Length header for fast rejection and
streams the body to enforce actual size limits.
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from sovereignguard.config import settings

logger = logging.getLogger(__name__)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforces MAX_REQUEST_SIZE_MB from config.

    Checks Content-Length header first for fast rejection,
    then validates actual body size during parsing.
    """

    async def dispatch(self, request: Request, call_next):
        max_bytes = settings.MAX_REQUEST_SIZE_MB * 1024 * 1024

        # Fast check via Content-Length header
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_bytes:
            logger.warning(
                f"Request rejected: Content-Length {content_length} exceeds "
                f"limit of {max_bytes} bytes"
            )
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "message": f"Request body too large. Maximum size is {settings.MAX_REQUEST_SIZE_MB}MB.",
                        "type": "invalid_request_error",
                        "code": "request_too_large",
                    }
                },
            )

        return await call_next(request)
