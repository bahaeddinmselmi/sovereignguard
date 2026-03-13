"""
Moroccan Phone Number Recognizer

Formats supported:
+212 X XX XX XX XX
00212 X XX XX XX XX
0X XX XX XX XX (local 10-digit)

Mobile prefixes: 06, 07
Landline prefixes: 05
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class MoroccanPhoneRecognizer(BaseRecognizer):

    ENTITY_TYPE = "MA_PHONE"

    PATTERNS = [
        # International: +212 or 00212
        (r'(?:\+212|00212)[\s\-]?[5-7]\d{2}[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2}', 0.98),
        # Local 10-digit: 0X XX XX XX XX
        (r'\b0[5-7]\d{2}[\s.\-]?\d{2}[\s.\-]?\d{2}[\s.\-]?\d{2}\b', 0.88),
    ]

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "ma"

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
