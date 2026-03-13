"""
Tunisian Person Name Recognizer (Context-Aware)

Extends universal name detection with Tunisian/Arabic/French naming contexts:
- Monsieur/Madame/السيد/السيدة + Name
- ibn/bin/ben family name connectors
- Arabic prefixes: عبد, أبو

This recognizer is intentionally conservative to reduce false positives.
"""

import re
from typing import List

from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class TunisianPersonNameRecognizer(BaseRecognizer):
    ENTITY_TYPE = "PERSON_NAME"

    CONTEXT_PREFIXES = [
        r"\bM(?:r|me|onsieur|adame)\.?\s+",
        r"\bMme\.?\s+",
        r"\bDr\.?\s+",
        r"\bPr\.?\s+",
        r"\bالسيد\s+",
        r"\bالسيدة\s+",
        r"\bالاستاذ\s+",
        r"\bالدكتور\s+",
    ]

    # Name cores: Latin and Arabic scripts with Tunisian connectors.
    LATIN_NAME = r"[A-Z][a-z]{2,}(?:\s+(?:Ben|ben|Bin|bin|Ibn|ibn)\s+[A-Z][a-z]{2,})?(?:\s+[A-Z][a-z]{2,})?"
    ARABIC_NAME = r"[\u0621-\u064A]{2,}(?:\s+(?:بن|ابن|بن\s+علي|عبد)\s+[\u0621-\u064A]{2,})?(?:\s+[\u0621-\u064A]{2,})?"

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "tn"

    @property
    def priority(self) -> int:
        return 70

    def analyze(self, text: str) -> List[RecognizerResult]:
        results: List[RecognizerResult] = []

        patterns = []
        for prefix in self.CONTEXT_PREFIXES:
            patterns.append(rf"{prefix}({self.LATIN_NAME}|{self.ARABIC_NAME})")

        # Also detect standalone "Ben X" patterns with lower confidence.
        patterns.append(r"\b(Ben\s+[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b")

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.UNICODE):
                captured = match.group(1) if match.lastindex else match.group(0)
                start = match.start(1) if match.lastindex else match.start()
                end = match.end(1) if match.lastindex else match.end()

                score = 0.84 if any(
                    re.search(p, match.group(0), re.IGNORECASE | re.UNICODE)
                    for p in self.CONTEXT_PREFIXES
                ) else 0.72

                # Penalize very short captures to reduce false positives.
                if len(captured.strip()) < 5:
                    score -= 0.15

                results.append(
                    RecognizerResult(
                        entity_type=self.ENTITY_TYPE,
                        start=start,
                        end=end,
                        score=max(0.55, min(0.92, score)),
                        text=captured,
                        locale=self.locale,
                    )
                )

        return self._deduplicate(results)
