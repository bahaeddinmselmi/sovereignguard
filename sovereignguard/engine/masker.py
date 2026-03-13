"""
SovereignGuard Core Masking Engine

The heart of the system. Orchestrates:
1. PII Detection (via recognizer registry)
2. Token Generation (unique, reversible placeholders)
3. Mapping Storage (session-scoped, encrypted)
4. Text Reconstruction (masked version for LLM)

SECURITY INVARIANTS (never violate these):
- Original PII values NEVER leave this module unmasked
- Mapping keys are one-way tokens (cannot derive PII from token)
- Each session has isolated mapping namespace
- All operations are logged to audit trail (without PII values)
"""

import re
import uuid
import logging
import asyncio
from typing import List
from dataclasses import dataclass

from sovereignguard.recognizers.registry import RecognizerRegistry
from sovereignguard.recognizers.base import RecognizerResult
from sovereignguard.engine.mapping import MappingStore
from sovereignguard.engine.semantic_restorer import SemanticRestorer
from sovereignguard.utils.tokenizer import generate_token
from sovereignguard.config import settings
from sovereignguard.audit.logger import audit_log
from sovereignguard.engine.restorer import TOKEN_PATTERN, FUZZY_PATTERN

logger = logging.getLogger(__name__)


@dataclass
class MaskingResult:
    """Result of a masking operation."""
    masked_text: str
    entity_count: int
    entity_types: List[str]
    session_id: str
    had_pii: bool


@dataclass
class RestorationResult:
    """Result of a restoration operation."""
    restored_text: str
    tokens_restored: int
    tokens_not_found: int
    session_id: str


class MaskingEngine:
    """
    Core PII masking and restoration engine.

    Usage:
        engine = MaskingEngine()
        session_id = engine.new_session()

        # Before sending to LLM
        masked = engine.mask(text, session_id)

        # After receiving from LLM
        restored = engine.restore(llm_response, session_id)

        # Cleanup
        engine.end_session(session_id)
    """

    def __init__(self):
        self.registry = RecognizerRegistry()
        self.mapping_store = MappingStore()
        self.semantic_restorer = SemanticRestorer(self.mapping_store)
        # Track tokens sent per session for completeness verification
        self._session_tokens: dict[str, set[str]] = {}
        self._load_recognizers()

    def _load_recognizers(self):
        """Load all recognizers based on enabled locales in config."""
        self.registry.load_for_locales(settings.ENABLED_LOCALES)
        logger.info(
            f"Loaded {len(self.registry.recognizers)} recognizers "
            f"for locales: {settings.ENABLED_LOCALES}"
        )

    def new_session(self) -> str:
        """Create a new isolated masking session. Returns session_id."""
        session_id = str(uuid.uuid4())
        self.mapping_store.create_session(session_id)
        self._session_tokens[session_id] = set()
        return session_id

    def end_session(self, session_id: str):
        """
        Destroy all PII mappings for this session.
        Call this after request/response cycle is complete.
        """
        self.mapping_store.destroy_session(session_id)
        self._session_tokens.pop(session_id, None)
        audit_log("SESSION_ENDED", session_id=session_id)

    def mask(self, text: str, session_id: str) -> MaskingResult:
        """
        Detect and mask all PII in text.

        Replaces each PII entity with a unique token like {{SG_EMAIL_a3f9b2}}.
        Stores original→token mapping in session store.
        """
        if settings.BYPASS_MASKING:
            logger.warning("BYPASS_MASKING is enabled — PII NOT masked!")
            return MaskingResult(
                masked_text=text,
                entity_count=0,
                entity_types=[],
                session_id=session_id,
                had_pii=False,
            )

        # Run all recognizers
        all_results: List[RecognizerResult] = []
        for recognizer in self.registry.get_sorted_recognizers():
            results = recognizer.analyze(text)
            filtered = [
                r for r in results
                if r.score >= settings.CONFIDENCE_THRESHOLD
            ]
            all_results.extend(filtered)

        # Resolve overlapping detections (keep highest confidence)
        resolved = self._resolve_overlaps(all_results)

        if not resolved:
            return MaskingResult(
                masked_text=text,
                entity_count=0,
                entity_types=[],
                session_id=session_id,
                had_pii=False,
            )

        # Replace PII with tokens (process in reverse order to preserve positions)
        masked_text = text
        sorted_results = sorted(resolved, key=lambda x: x.start, reverse=True)

        for result in sorted_results:
            # Check if we already have a token for this exact value
            existing_token = self.mapping_store.get_token_for_value(
                session_id, result.text, result.entity_type
            )

            if existing_token:
                token = existing_token
            else:
                token = generate_token(result.entity_type)
                self.mapping_store.store(
                    session_id=session_id,
                    token=token,
                    original_value=result.text,
                    entity_type=result.entity_type,
                )

            # Track tokens sent for completeness verification
            if session_id in self._session_tokens:
                self._session_tokens[session_id].add(token)

            masked_text = (
                masked_text[:result.start]
                + token
                + masked_text[result.end:]
            )

        entity_types = list(set(r.entity_type for r in resolved))

        audit_log(
            "TEXT_MASKED",
            session_id=session_id,
            entity_count=len(resolved),
            entity_types=entity_types,
        )

        return MaskingResult(
            masked_text=masked_text,
            entity_count=len(resolved),
            entity_types=entity_types,
            session_id=session_id,
            had_pii=True,
        )

    async def mask_async(self, text: str, session_id: str) -> MaskingResult:
        """
        Async version of mask() using the two-tier pipeline.

        Fast regex recognizers run inline; heavy NLP recognizers
        run in a thread pool to avoid blocking the event loop.
        """
        if settings.BYPASS_MASKING:
            return MaskingResult(
                masked_text=text, entity_count=0, entity_types=[],
                session_id=session_id, had_pii=False,
            )

        from sovereignguard.engine.pipeline import run_pipeline

        all_results = await run_pipeline(
            self.registry, text, settings.CONFIDENCE_THRESHOLD
        )

        return self._apply_masking(text, all_results, session_id)

    def _apply_masking(
        self, text: str, all_results: List[RecognizerResult], session_id: str
    ) -> MaskingResult:
        """Shared logic: resolve overlaps, generate tokens, build masked text."""
        resolved = self._resolve_overlaps(all_results)

        if not resolved:
            return MaskingResult(
                masked_text=text, entity_count=0, entity_types=[],
                session_id=session_id, had_pii=False,
            )

        masked_text = text
        sorted_results = sorted(resolved, key=lambda x: x.start, reverse=True)

        for result in sorted_results:
            existing_token = self.mapping_store.get_token_for_value(
                session_id, result.text, result.entity_type
            )
            if existing_token:
                token = existing_token
            else:
                token = generate_token(result.entity_type)
                self.mapping_store.store(
                    session_id=session_id, token=token,
                    original_value=result.text, entity_type=result.entity_type,
                )

            if session_id in self._session_tokens:
                self._session_tokens[session_id].add(token)

            masked_text = masked_text[:result.start] + token + masked_text[result.end:]

        entity_types = list(set(r.entity_type for r in resolved))

        audit_log(
            "TEXT_MASKED", session_id=session_id,
            entity_count=len(resolved), entity_types=entity_types,
        )

        return MaskingResult(
            masked_text=masked_text, entity_count=len(resolved),
            entity_types=entity_types, session_id=session_id, had_pii=True,
        )

    def restore(self, text: str, session_id: str) -> RestorationResult:
        """
        Restore masked tokens back to original PII values.

        Uses the multi-tier SemanticRestorer that handles:
        - Exact token matches: {{SG_EMAIL_a3f9b2}} → original
        - Fuzzy bracket variations: [SG EMAIL a3f9b2] → original
        - Bare token references: SG_EMAIL_a3f9b2 → original
        - Completeness verification: warns if tokens sent but not found
        """
        tokens_sent = self._session_tokens.get(session_id)

        result = self.semantic_restorer.restore(
            text=text,
            session_id=session_id,
            tokens_sent=tokens_sent,
        )

        audit_log(
            "TEXT_RESTORED",
            session_id=session_id,
            tokens_restored=result.tokens_restored,
            tokens_not_found=result.tokens_not_found,
            strategies_used=result.strategies_used,
            restoration_completeness=result.restoration_completeness,
        )

        return RestorationResult(
            restored_text=result.restored_text,
            tokens_restored=result.tokens_restored,
            tokens_not_found=result.tokens_not_found,
            session_id=session_id,
        )

    def _resolve_overlaps(
        self,
        results: List[RecognizerResult],
    ) -> List[RecognizerResult]:
        """
        When multiple recognizers detect overlapping regions,
        keep the detection with highest confidence score.
        Locale-specific recognizers get a priority boost.
        """
        if not results:
            return []

        # Apply priority boost for locale-specific recognizers
        for result in results:
            if result.locale != "universal":
                result.score = min(1.0, result.score + 0.05)

        # Sort by position, then by score descending
        sorted_results = sorted(
            results,
            key=lambda x: (x.start, -x.score),
        )

        resolved = [sorted_results[0]]
        for current in sorted_results[1:]:
            last = resolved[-1]
            if current.start >= last.end:  # No overlap
                resolved.append(current)
            elif current.score > last.score:  # Overlap, current wins
                resolved[-1] = current

        return resolved
