"""
Moroccan CIN (Carte d'Identité Nationale) Recognizer

Format: 1-2 letters + 5-6 digits
Examples: AB123456, B123456, BE123456
Letters correspond to regional prefixes.
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class MoroccanCINRecognizer(BaseRecognizer):

    ENTITY_TYPE = "MA_CIN"

    CONTEXT_KEYWORDS = [
        r'\bCIN\b',
        r'\bCNIE\b',
        r'carte\s+d\'identit[eé]',
        r'carte\s+nationale',
        r'بطاقة\s+التعريف\s+الوطنية',
        r'رقم\s+البطاقة',
        r'national\s*id',
    ]

    # Moroccan CIN: 1–2 uppercase letters followed by 5–6 digits
    PATTERN = r'\b([A-Z]{1,2}\d{5,6})\b'

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "ma"

    @property
    def priority(self) -> int:
        return 75

    def analyze(self, text: str) -> List[RecognizerResult]:
        has_context = any(
            re.search(kw, text, re.IGNORECASE | re.UNICODE)
            for kw in self.CONTEXT_KEYWORDS
        )

        results = []
        for match in re.finditer(self.PATTERN, text):
            score = 0.92 if has_context else 0.72
            results.append(RecognizerResult(
                entity_type=self.ENTITY_TYPE,
                start=match.start(),
                end=match.end(),
                score=score,
                text=match.group(),
                locale=self.locale,
            ))

        return self._deduplicate(results)
