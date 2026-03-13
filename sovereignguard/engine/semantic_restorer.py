"""
Semantic Re-mapping Engine

Handles the critical challenge of LLM token reformatting:
When we send "Contact {{SG_NAME_a3f9b2}} at {{SG_PHONE_c4d5e6}}"
the LLM might respond with:
  - "I contacted the person named {{SG_NAME_a3f9b2}} using their number."
    (token preserved but context changed — handled by exact match)
  - "I reached out to SG_NAME_a3f9b2 via phone."
    (brackets stripped — handled by fuzzy match)
  - "I reached out to {{ SG NAME a3f9b2 }} via phone."
    (spacing/formatting altered — handled by normalized match)
  - "The person's name token is SG-NAME-a3f9b2"
    (completely reformatted — handled by semantic extraction)

Strategy:
1. Exact match (fastest) — find {{SG_TYPE_hex}} verbatim
2. Fuzzy bracket match — various bracket/spacing variations
3. Normalized extraction — find SG_ + entity_type + hex regardless of formatting
4. Semantic validation — verify all sent tokens were restored, flag missing ones
"""

import re
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from sovereignguard.engine.mapping import MappingStore

logger = logging.getLogger(__name__)


@dataclass
class SemanticRestorationResult:
    """Enhanced restoration result with completeness tracking."""
    restored_text: str
    tokens_restored: int
    tokens_not_found: int
    tokens_sent: int
    restoration_completeness: float  # 0.0 to 1.0
    session_id: str
    strategies_used: List[str] = field(default_factory=list)
    unreplaced_tokens: List[str] = field(default_factory=list)


# ─── Pattern Tiers ────────────────────────────────────────────────────────────

# Tier 1: Exact standard format
EXACT_PATTERN = re.compile(
    r'\{\{SG_([A-Z_]+)_([a-f0-9]{6,12})\}\}',
    re.IGNORECASE,
)

# Tier 2: Fuzzy — brackets may be changed, extra spaces added
FUZZY_PATTERNS = [
    # Various bracket styles with optional extra spaces
    re.compile(
        r'[\{\[<\(]\{?\s*SG[_\s]+([A-Z_]+)[_\s]+([a-f0-9]{6,12})\s*\}?[\}\]>\)]',
        re.IGNORECASE,
    ),
    # Markdown code formatting: `SG_TYPE_hex`
    re.compile(
        r'`\s*SG[_\s]+([A-Z_]+)[_\s]+([a-f0-9]{6,12})\s*`',
        re.IGNORECASE,
    ),
    # Quoted: "SG_TYPE_hex" or 'SG_TYPE_hex'
    re.compile(
        r'["\']SG[_\s]+([A-Z_]+)[_\s]+([a-f0-9]{6,12})["\']',
        re.IGNORECASE,
    ),
]

# Tier 3: Bare — LLM stripped all formatting, just the token identifier
BARE_PATTERN = re.compile(
    r'\bSG[_\-\s]+([A-Z][A-Z_\-\s]+?)[_\-\s]+([a-f0-9]{6,12})\b',
    re.IGNORECASE,
)


class SemanticRestorer:
    """
    Multi-tier token restoration engine.

    Uses progressively more aggressive matching strategies to recover
    tokens that LLMs may have reformatted in their responses.
    """

    def __init__(self, mapping_store: MappingStore):
        self.mapping_store = mapping_store

    def restore(
        self,
        text: str,
        session_id: str,
        tokens_sent: Optional[Set[str]] = None,
    ) -> SemanticRestorationResult:
        """
        Restore tokens using multi-tier matching.

        Args:
            text: The LLM response text containing tokens
            session_id: The session ID for token lookup
            tokens_sent: Set of tokens that were sent to the LLM
                         (used for completeness verification)
        """
        restored_text = text
        total_restored = 0
        total_not_found = 0
        strategies_used = []
        restored_token_ids: Set[str] = set()

        # ─── Tier 1: Exact Match ──────────────────────────────────────────
        for match in EXACT_PATTERN.finditer(restored_text):
            token = match.group()
            original = self.mapping_store.retrieve(session_id, token)
            if original:
                restored_text = restored_text.replace(token, original)
                total_restored += 1
                restored_token_ids.add(token)
                if "exact" not in strategies_used:
                    strategies_used.append("exact")
            else:
                total_not_found += 1

        # ─── Tier 2: Fuzzy Bracket Match ──────────────────────────────────
        for pattern in FUZZY_PATTERNS:
            for match in pattern.finditer(restored_text):
                entity_type = self._normalize_entity_type(match.group(1))
                hex_suffix = match.group(2)
                canonical = f"{{{{SG_{entity_type}_{hex_suffix}}}}}"

                if canonical in restored_token_ids:
                    continue

                original = self.mapping_store.retrieve(session_id, canonical)
                if original:
                    restored_text = restored_text.replace(
                        match.group(), original
                    )
                    total_restored += 1
                    restored_token_ids.add(canonical)
                    if "fuzzy_bracket" not in strategies_used:
                        strategies_used.append("fuzzy_bracket")

        # ─── Tier 3: Bare Token Match ─────────────────────────────────────
        for match in BARE_PATTERN.finditer(restored_text):
            entity_type = self._normalize_entity_type(match.group(1))
            hex_suffix = match.group(2)
            canonical = f"{{{{SG_{entity_type}_{hex_suffix}}}}}"

            if canonical in restored_token_ids:
                continue

            original = self.mapping_store.retrieve(session_id, canonical)
            if original:
                restored_text = restored_text.replace(
                    match.group(), original
                )
                total_restored += 1
                restored_token_ids.add(canonical)
                if "bare_extraction" not in strategies_used:
                    strategies_used.append("bare_extraction")

        # ─── Completeness Verification ────────────────────────────────────
        sent_count = len(tokens_sent) if tokens_sent else 0
        unreplaced = []

        if tokens_sent:
            unreplaced = [t for t in tokens_sent if t not in restored_token_ids]
            if unreplaced:
                logger.warning(
                    "semantic_restore_incomplete",
                    extra={
                        "session_id": session_id,
                        "missing_count": len(unreplaced),
                        "total_sent": sent_count,
                        "strategies_used": strategies_used,
                    },
                )

        completeness = (
            total_restored / sent_count if sent_count > 0 else 1.0
        )

        return SemanticRestorationResult(
            restored_text=restored_text,
            tokens_restored=total_restored,
            tokens_not_found=total_not_found,
            tokens_sent=sent_count,
            restoration_completeness=completeness,
            session_id=session_id,
            strategies_used=strategies_used,
            unreplaced_tokens=unreplaced,
        )

    @staticmethod
    def _normalize_entity_type(raw: str) -> str:
        """Normalize entity type from messy LLM output to canonical form."""
        return re.sub(r'[\s\-]+', '_', raw.strip()).upper()
