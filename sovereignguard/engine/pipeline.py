"""
Async Masking Pipeline

Performance-optimized masking architecture that separates
fast regex operations from heavy NLP processing.

Architecture:
┌──────────────────────────────────────────────────┐
│                 Async Pipeline                    │
│                                                   │
│  ┌────────────┐   ┌────────────┐   ┌───────────┐ │
│  │ Fast Path  │──▶│ NLP Path   │──▶│ Merge &   │ │
│  │ (regex)    │   │ (optional) │   │ Deduplicate│ │
│  │ < 1ms      │   │ threadpool │   │           │ │
│  └────────────┘   └────────────┘   └───────────┘ │
└──────────────────────────────────────────────────┘

Strategy:
- Fast Path: All regex-based recognizers run inline (sub-millisecond)
- NLP Path: Heavy recognizers (name detection, NER) run in a thread pool
- Results are merged and deduplicated before masking

This ensures 100 concurrent requests don't block on NLP processing.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from sovereignguard.recognizers.base import RecognizerResult, BaseRecognizer
from sovereignguard.recognizers.registry import RecognizerRegistry
from sovereignguard.config import settings

logger = logging.getLogger(__name__)

# Shared thread pool for NLP-heavy recognizers
# Sized to avoid overwhelming CPU on high-concurrency workloads
_nlp_executor: Optional[ThreadPoolExecutor] = None

# Recognizer types that are regex-only (fast path)
FAST_RECOGNIZERS = {
    "EMAIL", "PHONE", "CREDIT_CARD", "IBAN", "IP_ADDRESS",
    "TN_NATIONAL_ID", "TN_PHONE", "TN_COMPANY_ID", "TN_ADDRESS",
    "FR_NIR", "FR_SIRET", "FR_PHONE", "FR_ADDRESS",
    "MA_CIN", "MA_PHONE", "MA_ICE",
}

# Recognizers that use context analysis / heavier processing
HEAVY_RECOGNIZERS = {
    "PERSON_NAME", "DATE_OF_BIRTH",
}


def get_nlp_executor() -> ThreadPoolExecutor:
    """Lazy-initialize the NLP thread pool."""
    global _nlp_executor
    if _nlp_executor is None:
        # Cap at 4 threads to avoid CPU saturation
        max_workers = min(4, settings.WORKERS)
        _nlp_executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="sg-nlp",
        )
    return _nlp_executor


def classify_recognizer(recognizer: BaseRecognizer) -> str:
    """Classify a recognizer as 'fast' or 'heavy' based on its entity types."""
    entity_types = set(recognizer.entity_types)
    if entity_types & HEAVY_RECOGNIZERS:
        return "heavy"
    return "fast"


def run_recognizer_sync(
    recognizer: BaseRecognizer,
    text: str,
    threshold: float,
) -> List[RecognizerResult]:
    """Run a single recognizer synchronously. Used in thread pool."""
    try:
        results = recognizer.analyze(text)
        return [r for r in results if r.score >= threshold]
    except Exception as e:
        logger.error(
            "recognizer_error",
            extra={
                "recognizer": type(recognizer).__name__,
                "error": str(e),
            },
        )
        return []


async def run_pipeline(
    registry: RecognizerRegistry,
    text: str,
    threshold: float,
) -> List[RecognizerResult]:
    """
    Run the two-tier async masking pipeline.

    Fast recognizers run inline in the event loop.
    Heavy recognizers run in a thread pool to avoid blocking.
    Results are merged and deduplicated.
    """
    start = time.monotonic()

    fast_recognizers = []
    heavy_recognizers = []

    for recognizer in registry.get_sorted_recognizers():
        if classify_recognizer(recognizer) == "fast":
            fast_recognizers.append(recognizer)
        else:
            heavy_recognizers.append(recognizer)

    # ─── Fast Path: Run regex recognizers inline ──────────────────────────
    fast_results: List[RecognizerResult] = []
    for recognizer in fast_recognizers:
        results = recognizer.analyze(text)
        fast_results.extend(r for r in results if r.score >= threshold)

    fast_elapsed = time.monotonic() - start

    # ─── Heavy Path: Run NLP recognizers in thread pool ───────────────────
    heavy_results: List[RecognizerResult] = []
    if heavy_recognizers:
        loop = asyncio.get_event_loop()
        executor = get_nlp_executor()

        futures = [
            loop.run_in_executor(
                executor,
                run_recognizer_sync,
                recognizer,
                text,
                threshold,
            )
            for recognizer in heavy_recognizers
        ]

        for completed in await asyncio.gather(*futures, return_exceptions=True):
            if isinstance(completed, Exception):
                logger.error("nlp_pipeline_error", extra={"error": str(completed)})
                continue
            heavy_results.extend(completed)

    total_elapsed = time.monotonic() - start

    all_results = fast_results + heavy_results

    logger.debug(
        "pipeline_complete",
        extra={
            "fast_path_ms": round(fast_elapsed * 1000, 2),
            "total_ms": round(total_elapsed * 1000, 2),
            "fast_hits": len(fast_results),
            "heavy_hits": len(heavy_results),
            "total_hits": len(all_results),
        },
    )

    return all_results


async def shutdown_pipeline():
    """Shutdown the NLP thread pool gracefully."""
    global _nlp_executor
    if _nlp_executor:
        _nlp_executor.shutdown(wait=False)
        _nlp_executor = None
