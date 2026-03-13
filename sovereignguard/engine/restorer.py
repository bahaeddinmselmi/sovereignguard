"""
De-anonymization (restoration) module.

This module provides a standalone restore_text function that delegates
to the core MaskingEngine.restore() logic to avoid code duplication.

Use MaskingEngine.restore() directly when you have an engine instance.
Use restore_text() for standalone usage when you only have a MappingStore.
"""

import re
import logging
from typing import Optional
from dataclasses import dataclass

from sovereignguard.engine.mapping import MappingStore

logger = logging.getLogger(__name__)


@dataclass
class RestorationResult:
    """Result of a restoration operation."""
    restored_text: str
    tokens_restored: int
    tokens_not_found: int
    session_id: str


# Shared regex patterns used by both masker.py and this module
TOKEN_PATTERN = re.compile(
    r'\{\{SG_[A-Z_]+_[a-f0-9]{6,12}\}\}',
    re.IGNORECASE,
)

FUZZY_PATTERN = re.compile(
    r'[\{\[<]\{?\s*SG[_\s]+([A-Z_]+)[_\s]+([a-f0-9]{6,12})\s*\}?[\}\]>]',
    re.IGNORECASE,
)


def restore_text(
    text: str,
    session_id: str,
    mapping_store: MappingStore,
) -> RestorationResult:
    """
    Restore masked tokens in text back to original PII values.

    Handles:
    - Exact token matches: {{SG_EMAIL_a3f9b2}} → original
    - Common LLM reformatting of tokens (added spaces, changed brackets)
    """
    found_tokens = set(TOKEN_PATTERN.findall(text))
    restored_text = text
    tokens_restored = 0
    tokens_not_found = 0

    # First pass: exact matches
    for token in found_tokens:
        original_value = mapping_store.retrieve(session_id, token)
        if original_value:
            restored_text = restored_text.replace(token, original_value)
            tokens_restored += 1
        else:
            tokens_not_found += 1
            logger.warning(
                f"Token not found in session mapping: {token[:20]}... "
                f"Session may have expired or token is invalid."
            )

    # Second pass: fuzzy matching for LLM-reformatted tokens
    for match in FUZZY_PATTERN.finditer(restored_text):
        entity_type = match.group(1)
        token_suffix = match.group(2)
        reconstructed = f"{{{{SG_{entity_type}_{token_suffix}}}}}"

        original_value = mapping_store.retrieve(session_id, reconstructed)
        if original_value:
            restored_text = restored_text.replace(match.group(), original_value)
            tokens_restored += 1

    return RestorationResult(
        restored_text=restored_text,
        tokens_restored=tokens_restored,
        tokens_not_found=tokens_not_found,
        session_id=session_id,
    )
