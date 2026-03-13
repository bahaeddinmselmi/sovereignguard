"""
Smart Router — Sovereignty-Aware Request Routing

When data is "too sensitive" for external providers, the router
automatically redirects requests to a local LLM (e.g., Ollama/Llama 3)
instead of sending them to OpenAI/Anthropic.

Decision Logic:
┌─────────────────────────────────────────────────────────────┐
│  Incoming Request                                           │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────────┐                                           │
│  │ PII Scanner  │                                           │
│  │ (pre-mask)   │                                           │
│  └──────┬───────┘                                           │
│         │                                                   │
│    ┌────▼────────────┐                                      │
│    │ Sensitivity      │                                     │
│    │ Calculator       │                                     │
│    │                  │                                      │
│    │ score < threshold│──▶ External LLM (masked)           │
│    │                  │                                      │
│    │ score ≥ threshold│──▶ Local LLM (unmasked, sovereign) │
│    └──────────────────┘                                     │
└─────────────────────────────────────────────────────────────┘

Sensitivity scoring:
- National IDs: +0.40 (critical government data)
- Credit cards: +0.35 (financial data)
- Person names + IDs: +0.20 (correlated identity)
- Emails alone: +0.10 (low sensitivity)
- Multiple entity types combined: multiplier applied
"""

import logging
from enum import Enum
from typing import Dict, List, Tuple

from sovereignguard.recognizers.base import RecognizerResult
from sovereignguard.config import settings

logger = logging.getLogger(__name__)


class RoutingDestination(str, Enum):
    EXTERNAL = "external"  # Masked → external LLM provider
    LOCAL = "local"        # Unmasked → local LLM (full sovereignty)


# Sensitivity weights per entity type
SENSITIVITY_WEIGHTS: Dict[str, float] = {
    # Critical government / identity data
    "TN_NATIONAL_ID": 0.40,
    "FR_NIR": 0.40,
    "MA_CIN": 0.40,
    "PERSON_NAME": 0.15,
    "DATE_OF_BIRTH": 0.20,

    # Financial data
    "CREDIT_CARD": 0.35,
    "IBAN": 0.30,
    "TN_COMPANY_ID": 0.15,
    "FR_SIRET": 0.15,
    "MA_ICE": 0.15,

    # Contact data
    "EMAIL": 0.10,
    "PHONE": 0.10,
    "TN_PHONE": 0.10,
    "FR_PHONE": 0.10,
    "MA_PHONE": 0.10,

    # Location data
    "TN_ADDRESS": 0.15,
    "FR_ADDRESS": 0.15,
    "IP_ADDRESS": 0.08,
}

# Correlation multiplier: when multiple identity-linked types appear together,
# the re-identification risk is higher than the sum of parts
CORRELATION_GROUPS = [
    {"types": {"PERSON_NAME", "TN_NATIONAL_ID"}, "multiplier": 1.5},
    {"types": {"PERSON_NAME", "FR_NIR"}, "multiplier": 1.5},
    {"types": {"PERSON_NAME", "MA_CIN"}, "multiplier": 1.5},
    {"types": {"PERSON_NAME", "EMAIL", "PHONE"}, "multiplier": 1.3},
    {"types": {"PERSON_NAME", "DATE_OF_BIRTH"}, "multiplier": 1.4},
    {"types": {"CREDIT_CARD", "PERSON_NAME"}, "multiplier": 1.4},
]


def calculate_sensitivity(
    detections: List[RecognizerResult],
) -> Tuple[float, List[str]]:
    """
    Calculate a sensitivity score from 0.0 to 1.0 for a set of detections.

    Returns (score, reasons) tuple.
    """
    if not detections:
        return 0.0, []

    entity_types = set()
    base_score = 0.0
    reasons = []

    for detection in detections:
        entity_types.add(detection.entity_type)
        weight = SENSITIVITY_WEIGHTS.get(detection.entity_type, 0.10)
        base_score += weight

    # Apply correlation multipliers
    for group in CORRELATION_GROUPS:
        if group["types"].issubset(entity_types):
            multiplier = group["multiplier"]
            base_score *= multiplier
            types_str = " + ".join(sorted(group["types"]))
            reasons.append(
                f"Correlated identity data ({types_str}): {multiplier}x multiplier"
            )

    # Diversity bonus: many different PII types = higher risk
    if len(entity_types) >= 4:
        base_score *= 1.2
        reasons.append(f"High PII diversity ({len(entity_types)} types): 1.2x multiplier")

    # Clamp to [0.0, 1.0]
    score = min(1.0, base_score)

    if score >= settings.SENSITIVITY_THRESHOLD:
        reasons.append(f"Score {score:.2f} ≥ threshold {settings.SENSITIVITY_THRESHOLD}")

    return score, reasons


class SmartRouter:
    """Routes requests based on sensitivity analysis."""

    def __init__(self):
        self.local_available = bool(
            settings.LOCAL_FALLBACK_ENABLED and settings.LOCAL_LLM_URL
        )

    def decide(
        self, detections: List[RecognizerResult]
    ) -> Tuple[RoutingDestination, float, List[str]]:
        """
        Decide whether to route to external or local LLM.

        Returns (destination, sensitivity_score, reasons).
        """
        score, reasons = calculate_sensitivity(detections)

        if score >= settings.SENSITIVITY_THRESHOLD and self.local_available:
            destination = RoutingDestination.LOCAL
            reasons.append("→ Routing to LOCAL LLM (data sovereignty)")
            logger.info(
                "smart_router_local",
                extra={
                    "sensitivity_score": score,
                    "entity_types": [d.entity_type for d in detections],
                },
            )
        else:
            destination = RoutingDestination.EXTERNAL
            if score >= settings.SENSITIVITY_THRESHOLD and not self.local_available:
                reasons.append(
                    "→ High sensitivity but no local LLM configured, using external (masked)"
                )
                logger.warning(
                    "smart_router_no_local_fallback",
                    extra={"sensitivity_score": score},
                )

        return destination, score, reasons

    def get_local_url(self) -> str:
        """Get the URL for the local LLM endpoint."""
        return settings.LOCAL_LLM_URL or "http://localhost:11434"

    def get_local_model(self) -> str:
        """Get the model name for the local LLM."""
        return settings.LOCAL_LLM_MODEL
