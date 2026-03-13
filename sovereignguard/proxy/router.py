"""
FastAPI Proxy Router — OpenAI-Compatible API

This is the drop-in replacement layer. It mirrors the OpenAI API structure
exactly so developers can switch endpoints with zero code changes.

Architecture:
Request → Auth → Rate Limit → Size Check → Mask → Forward → Restore → Response
"""

import re
import httpx
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from sovereignguard.proxy.handler import RequestHandler
from sovereignguard.config import settings
from sovereignguard.audit.metrics import metrics

logger = logging.getLogger(__name__)
router = APIRouter()
handler = RequestHandler()


@router.get("/health")
async def health_check():
    """Public gateway health endpoint. Returns minimal status info."""
    return {
        "status": "healthy",
        "gateway": "SovereignGuard",
        "version": "0.2.0",
    }


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Main chat completions endpoint.
    Masks PII in messages, forwards to target LLM, restores PII in response.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if "messages" not in body:
        raise HTTPException(status_code=400, detail="'messages' field required")

    session_id = handler.engine.new_session()
    metrics.request_started()

    try:
        masked_body = await handler.mask_request_body(body, session_id)

        is_streaming = body.get("stream", False)

        if is_streaming:
            return StreamingResponse(
                handler.stream_with_restoration(masked_body, session_id, request),
                media_type="text/event-stream",
            )

        llm_response = await handler.forward_request(
            endpoint="/v1/chat/completions",
            body=masked_body,
            headers=dict(request.headers),
        )

        restored_response = await handler.restore_response_body(
            llm_response, session_id
        )

        metrics.request_completed(success=True)
        return JSONResponse(content=restored_response)

    except Exception as e:
        metrics.request_completed(success=False)
        logger.error(f"Request processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        handler.engine.end_session(session_id)


@router.post("/v1/completions")
async def completions(request: Request):
    """Legacy completions endpoint."""
    body = await request.json()
    session_id = handler.engine.new_session()

    try:
        if "prompt" in body and isinstance(body["prompt"], str):
            mask_result = handler.engine.mask(body["prompt"], session_id)
            body["prompt"] = mask_result.masked_text

        llm_response = await handler.forward_request(
            endpoint="/v1/completions",
            body=body,
            headers=dict(request.headers),
        )

        if "choices" in llm_response:
            for choice in llm_response["choices"]:
                if "text" in choice:
                    restore_result = handler.engine.restore(
                        choice["text"], session_id
                    )
                    choice["text"] = restore_result.restored_text

        return JSONResponse(content=llm_response)

    finally:
        handler.engine.end_session(session_id)


@router.post("/v1/embeddings")
async def embeddings(request: Request):
    """
    Embeddings endpoint — pass-through with optional masking.
    Input text is masked; embedding vectors are safe to send externally.
    """
    body = await request.json()
    session_id = handler.engine.new_session()

    try:
        if "input" in body and isinstance(body["input"], str):
            mask_result = handler.engine.mask(body["input"], session_id)
            body["input"] = mask_result.masked_text

        response = await handler.forward_request(
            endpoint="/v1/embeddings",
            body=body,
            headers=dict(request.headers),
        )
        return JSONResponse(content=response)

    finally:
        handler.engine.end_session(session_id)


@router.get("/v1/models")
async def list_models(request: Request):
    """Pass-through to target API — no PII involved in model listing."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.TARGET_API_URL}/v1/models",
            headers={"Authorization": f"Bearer {settings.TARGET_API_KEY}"},
        )
        return JSONResponse(content=response.json())


# ─── Audit Endpoint (protected by auth middleware) ─────────────────────────────

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@router.get("/audit/report")
async def audit_report(start_date: str = None, end_date: str = None):
    """
    Generate GDPR-compliant audit report.
    Shows what types of PII were processed, when, and volume.
    Never shows actual PII values.
    Protected by the gateway authentication middleware.
    """
    # Validate date parameters
    for label, value in [("start_date", start_date), ("end_date", end_date)]:
        if value is not None and not _ISO_DATE_RE.match(value):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {label} format. Use YYYY-MM-DD.",
            )

    from sovereignguard.audit.report import generate_report

    report = generate_report(start_date=start_date, end_date=end_date)
    return JSONResponse(content=report)


# ─── Admin Endpoints ───────────────────────────────────────────────────────────

@router.get("/admin/stats")
async def admin_stats():
    """Live gateway statistics. Protected by auth middleware."""
    return JSONResponse(content={
        "recognizers_loaded": handler.engine.registry.count(),
        "masking_enabled": not settings.BYPASS_MASKING,
        "mapping_backend": settings.MAPPING_BACKEND.value,
        "provider": settings.TARGET_PROVIDER.value,
        "enabled_locales": settings.ENABLED_LOCALES,
        "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
        "rate_limit_rpm": settings.RATE_LIMIT_RPM,
    })


@router.delete("/admin/sessions/{session_id}")
async def admin_delete_session(session_id: str):
    """Force-destroy a specific masking session."""
    handler.engine.end_session(session_id)
    return JSONResponse(content={"status": "destroyed", "session_id": session_id})
