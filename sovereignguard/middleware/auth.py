"""
Authentication Middleware

Protects gateway endpoints with API key authentication.
Clients must provide a valid API key in the Authorization header.

Public endpoints (health, docs) are excluded from authentication.
"""

import hmac
import logging
from typing import List

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from sovereignguard.config import settings

logger = logging.getLogger(__name__)

# Endpoints that don't require authentication
PUBLIC_PATHS: List[str] = [
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
]


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    API key authentication middleware.

    Validates the Authorization header against configured gateway keys.
    Uses constant-time comparison to prevent timing attacks.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public endpoints
        if any(path.startswith(p) for p in PUBLIC_PATHS):
            return await call_next(request)

        # Skip auth if no gateway keys configured (development mode)
        if not settings.GATEWAY_API_KEYS:
            return await call_next(request)

        # Extract API key from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "Missing or invalid Authorization header. Use 'Bearer <api_key>'.",
                        "type": "authentication_error",
                        "code": "invalid_api_key",
                    }
                },
            )

        provided_key = auth_header[7:]  # Strip "Bearer "

        # Constant-time comparison against all valid keys
        is_valid = any(
            hmac.compare_digest(provided_key, valid_key)
            for valid_key in settings.GATEWAY_API_KEYS
        )

        if not is_valid:
            logger.warning(
                f"Authentication failed from {request.client.host if request.client else 'unknown'}"
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "Invalid API key.",
                        "type": "authentication_error",
                        "code": "invalid_api_key",
                    }
                },
            )

        return await call_next(request)
