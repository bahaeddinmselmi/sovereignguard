"""
French Phone Number Recognizer

Formats supported:
+33 X XX XX XX XX
0033 X XX XX XX XX
0X XX XX XX XX (local 10-digit)

Mobile prefixes: 06, 07
Landline prefixes: 01-05, 09
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class FrenchPhoneRecognizer(BaseRecognizer):

    ENTITY_TYPE = "FR_PHONE"

    PATTERNS = [
        # International: +33 or 0033
        (r'(?:\+33|0033)[\s\-]?[1-9](?:[\s.\-]?\d{2}){4}', 0.98),
        # Local 10-digit: 0X XX XX XX XX
        (r'\b0[1-9](?:[\s.\-]?\d{2}){4}\b', 0.88),
    ]

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "fr"

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
                    locale=self.locale,
                ))
        return self._deduplicate(results)
