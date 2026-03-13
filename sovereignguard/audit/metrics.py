"""
Prometheus metrics for SovereignGuard gateway.
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server

    REQUESTS_TOTAL = Counter(
        "sovereignguard_requests_total",
        "Total number of proxy requests",
        ["status"],
    )
    ENTITIES_MASKED = Counter(
        "sovereignguard_entities_masked_total",
        "Total PII entities masked",
        ["entity_type"],
    )
    TOKENS_RESTORED = Counter(
        "sovereignguard_tokens_restored_total",
        "Total tokens restored in responses",
    )
    REQUEST_DURATION = Histogram(
        "sovereignguard_request_duration_seconds",
        "Request processing time",
    )
    ACTIVE_SESSIONS = Gauge(
        "sovereignguard_active_sessions",
        "Currently active masking sessions",
    )

    _prometheus_available = True

except ImportError:
    _prometheus_available = False
    logger.debug("prometheus_client not installed; metrics disabled.")


class MetricsCollector:
    """Collects gateway metrics. Degrades gracefully without prometheus."""

    def __init__(self):
        self._request_start: Optional[float] = None

    def request_started(self):
        self._request_start = time.time()
        if _prometheus_available:
            ACTIVE_SESSIONS.inc()

    def request_completed(self, success: bool = True):
        status = "success" if success else "error"
        if _prometheus_available:
            REQUESTS_TOTAL.labels(status=status).inc()
            ACTIVE_SESSIONS.dec()
            if self._request_start:
                REQUEST_DURATION.observe(time.time() - self._request_start)
        self._request_start = None

    def entities_masked(self, entity_type: str, count: int = 1):
        if _prometheus_available:
            ENTITIES_MASKED.labels(entity_type=entity_type).inc(count)

    def tokens_restored(self, count: int = 1):
        if _prometheus_available:
            TOKENS_RESTORED.inc(count)

    def start_metrics_server(self, port: int):
        if _prometheus_available:
            start_http_server(port)
            logger.info(f"Prometheus metrics server started on port {port}")
        else:
            logger.warning("Cannot start metrics server: prometheus_client not installed")


metrics = MetricsCollector()
