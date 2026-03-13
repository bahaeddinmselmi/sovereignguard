"""
Tunisian Phone Number Recognizer

Formats supported:
+216 XX XXX XXX
00216 XX XXX XXX
216 XX XXX XXX
0X XX XX XX XX (local format)

Mobile prefixes: 2x, 4x, 5x, 9x
Landline prefixes: 7x (Tunis), 3x (South), other regions
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class TunisianPhoneRecognizer(BaseRecognizer):

    ENTITY_TYPE = "TN_PHONE"

    PATTERNS = [
        # International format: +216 or 00216
        (r'(?:\+216|00216)[\s\-]?[2-9]\d[\s\-]?\d{3}[\s\-]?\d{3}', 0.98),
        # With country code no plus: 216 XX XXX XXX
        (r'\b216[\s\-]?[2-9]\d[\s\-]?\d{3}[\s\-]?\d{3}\b', 0.90),
        # Local 8-digit format: starts with valid prefix
        (r'\b(?:[2459]\d|7[0-9]|3[0-9])[\s\-]?\d{3}[\s\-]?\d{3}\b', 0.75),
    ]

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "tn"

    @property
    def priority(self) -> int:
        return 80

    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []
        for pattern, score in self.PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                results.append(RecognizerResult(
                    entity_type=self.ENTITY_TYPE,
                    start=match.start(),
                    end=match.end(),
                    score=score,
                    text=match.group(),
                    locale=self.locale
                ))
        return self._deduplicate(results)
