"""
Base recognizer class. All country-specific and universal recognizers
must inherit from this class and implement the required interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
import re


@dataclass
class RecognizerResult:
    """Represents a detected PII entity in text."""
    entity_type: str        # e.g., "TN_NATIONAL_ID", "EMAIL", "FR_NIR"
    start: int              # Start character position in original text
    end: int                # End character position in original text
    score: float            # Confidence score 0.0 to 1.0
    text: str               # The actual PII value detected
    locale: str             # e.g., "tn", "fr", "universal"

    def __repr__(self):
        preview = self.text[:3] + "***" if len(self.text) > 3 else "***"
        return f"RecognizerResult({self.entity_type}, score={self.score:.2f}, preview='{preview}')"


class BaseRecognizer(ABC):
    """
    Abstract base class for all SovereignGuard PII recognizers.

    To add a new recognizer:
    1. Inherit from this class
    2. Implement entity_types, locale, and analyze()
    3. Register in recognizers/registry.py
    4. Add tests in tests/test_recognizers.py

    See docs/adding-recognizers.md for full guide.
    """

    @property
    @abstractmethod
    def entity_types(self) -> List[str]:
        """List of entity types this recognizer can detect."""
        pass

    @property
    @abstractmethod
    def locale(self) -> str:
        """
        ISO locale code for this recognizer.
        Use 'universal' for patterns that work across all locales.
        """
        pass

    @property
    def priority(self) -> int:
        """
        Higher priority recognizers run first.
        Use >50 for locale-specific, <50 for universal.
        Prevents universal patterns from conflicting with specific ones.
        """
        return 50

    @abstractmethod
    def analyze(self, text: str) -> List[RecognizerResult]:
        """
        Analyze text and return list of detected PII entities.

        IMPORTANT: Never modify the input text. Return positions
        relative to the original unchanged input string.
        """
        pass

    def _regex_analyze(
        self,
        text: str,
        patterns: List[tuple],  # List of (pattern, entity_type, score)
    ) -> List[RecognizerResult]:
        """
        Helper method for regex-based recognizers.
        Handles overlapping match deduplication automatically.
        """
        results = []
        for pattern, entity_type, score in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                results.append(RecognizerResult(
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    score=score,
                    text=match.group(),
                    locale=self.locale
                ))
        return self._deduplicate(results)

    def _deduplicate(self, results: List[RecognizerResult]) -> List[RecognizerResult]:
        """Remove overlapping results, keeping highest confidence."""
        if not results:
            return results

        sorted_results = sorted(results, key=lambda x: (x.start, -x.score))
        deduplicated = [sorted_results[0]]

        for current in sorted_results[1:]:
            last = deduplicated[-1]
            # If current overlaps with last, keep higher score
            if current.start < last.end:
                if current.score > last.score:
                    deduplicated[-1] = current
            else:
                deduplicated.append(current)

        return deduplicated
