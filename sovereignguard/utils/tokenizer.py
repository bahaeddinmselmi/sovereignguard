"""
Token Generation for PII Masking

Generates unique, non-reversible tokens for each PII entity.
Token format: {{SG_ENTITY_TYPE_randomhex}}
Example: {{SG_TN_NATIONAL_ID_a3f9b2c1}}

Properties:
- Tokens contain entity type for context preservation
- Random suffix prevents brute-force recovery
- Consistent length for predictable text expansion
- Human-readable enough for debugging (never in production logs)
"""

import os
import hashlib
from sovereignguard.config import settings


def generate_token(entity_type: str) -> str:
    """
    Generate a unique masked token for a PII entity.

    Args:
        entity_type: The type of PII (e.g., "TN_NATIONAL_ID", "EMAIL")

    Returns:
        Token string like {{SG_TN_NATIONAL_ID_a3f9b2c1}}
    """
    # 6 bytes = 12 hex chars. Collision probability negligible for session scope.
    random_suffix = os.urandom(6).hex()

    # Clean entity type for token use (no special chars)
    clean_type = entity_type.upper().replace(" ", "_").replace("-", "_")

    return f"{settings.TOKEN_PREFIX}{clean_type}_{random_suffix}{settings.TOKEN_SUFFIX}"


def generate_deterministic_token(entity_type: str, value: str, session_id: str) -> str:
    """
    Generate a deterministic token for deduplication.
    Same value in same session always gets same token.

    Uses HMAC-style generation: token depends on (session, entity_type, value)
    but cannot be reversed without all three inputs.
    """
    combined = f"{session_id}:{entity_type}:{value}"
    hash_hex = hashlib.sha256(combined.encode()).hexdigest()[:8]
    clean_type = entity_type.upper().replace(" ", "_").replace("-", "_")
    return f"{settings.TOKEN_PREFIX}{clean_type}_{hash_hex}{settings.TOKEN_SUFFIX}"
