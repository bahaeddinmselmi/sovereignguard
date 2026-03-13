"""
Raw proxy pass-through for non-text endpoints.
Forwards requests to the target LLM API without masking.
"""

import httpx
import logging
from fastapi import Request
from fastapi.responses import Response

from sovereignguard.config import settings

logger = logging.getLogger(__name__)


async def passthrough_request(request: Request, path: str) -> Response:
    """
    Forward a request to the target API without any PII processing.
    Used for endpoints that don't contain user text (models, status, etc.).
    """
    async with httpx.AsyncClient() as client:
        target_url = f"{settings.TARGET_API_URL}/{path}"

        headers = {
            "Authorization": f"Bearer {settings.TARGET_API_KEY}",
            "Content-Type": request.headers.get("content-type", "application/json"),
        }

        body = await request.body()

        response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body if body else None,
        )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
        )
