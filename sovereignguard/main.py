"""
SovereignGuard Gateway — Entry Point

Starts the FastAPI application with all middleware,
security headers, CORS, and route registration.

Middleware execution order (outermost → innermost):
  Request ID → Security Headers → Timing → Rate Limit → Auth → Request Size → CORS → Router
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sovereignguard.audit.logger import setup_audit_logging
from sovereignguard.audit.metrics import metrics
from sovereignguard.config import settings
from sovereignguard.middleware.auth import AuthenticationMiddleware
from sovereignguard.middleware.rate_limit import RateLimitMiddleware
from sovereignguard.middleware.request_id import RequestIDMiddleware, get_request_id
from sovereignguard.middleware.request_size import RequestSizeLimitMiddleware
from sovereignguard.proxy.router import router

# ─── Structured Logging Setup ──────────────────────────────────────────────────

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
        if settings.DEBUG
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.getLevelName(settings.LOG_LEVEL.value.upper())
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("sovereignguard")

# Also configure stdlib logging for third-party libs
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.value.upper()),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

# ─── Session Cleanup Task ──────────────────────────────────────────────────────

_cleanup_task = None


async def _session_cleanup_loop():
    """Periodically purge expired sessions from the mapping store."""
    from sovereignguard.engine.mapping import MappingStore

    store = MappingStore()
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        try:
            purged = store.purge_expired(settings.MAPPING_TTL_SECONDS)
            if purged > 0:
                logger.info("session_cleanup", purged_sessions=purged)
        except Exception as e:
            logger.error("session_cleanup_error", error=str(e))


# ─── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global _cleanup_task

    logger.info(
        "gateway_starting",
        target_api=settings.TARGET_API_URL,
        provider=settings.TARGET_PROVIDER.value,
        mapping_backend=settings.MAPPING_BACKEND.value,
        enabled_locales=settings.ENABLED_LOCALES,
        bypass_masking=settings.BYPASS_MASKING,
        auth_enabled=bool(settings.GATEWAY_API_KEYS),
        rate_limit_enabled=settings.RATE_LIMIT_ENABLED,
    )

    setup_audit_logging()

    # Start Prometheus metrics server
    if settings.METRICS_ENABLED:
        metrics.start_metrics_server(settings.METRICS_PORT)

    # Start session cleanup daemon
    _cleanup_task = asyncio.create_task(_session_cleanup_loop())

    yield

    # Shutdown
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass

    logger.info("gateway_shutdown")


# ─── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="SovereignGuard",
    description="Open source AI Privacy Gateway for GDPR-compliant LLM adoption",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
)

# ─── Middleware Stack (order matters — outermost runs first) ───────────────────

# Request ID must be outermost for correlation
app.add_middleware(RequestIDMiddleware)


# Security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store"
    return response


# Request timing
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = str(round(process_time, 2))
    response.headers["X-Powered-By"] = "SovereignGuard"
    return response


# Rate limiting
app.add_middleware(RateLimitMiddleware)

# Authentication (after rate limiting so brute-force is rate-limited)
app.add_middleware(AuthenticationMiddleware)

# Request size enforcement
app.add_middleware(RequestSizeLimitMiddleware)

# CORS — configurable via ALLOWED_ORIGINS
cors_origins = settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["POST", "GET", "DELETE"],
    allow_headers=["*"],
)


# ─── OpenAI-Compatible Error Handler ──────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = get_request_id()
    logger.error(
        "unhandled_exception",
        error=str(exc),
        request_id=req_id,
        path=request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal gateway error. Check logs for details.",
                "type": "server_error",
                "code": "internal_error",
            }
        },
    )


# ─── Routes ────────────────────────────────────────────────────────────────────

app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "sovereignguard.main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,
        reload=settings.DEBUG,
    )
