"""
Generic Phone Number Recognizer (Universal)
Detects international phone numbers with E.164 or common formats.
Country-specific recognizers should take priority over this one.
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class GenericPhoneRecognizer(BaseRecognizer):

    ENTITY_TYPE = "PHONE"

    PATTERNS = [
        # International with +: +1 234 567 8901
        (r'\+\d{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{2,4}[\s\-]?\d{2,4}[\s\-]?\d{0,4}', 0.85),
        # Parenthesized area code: (123) 456-7890
        (r'\(\d{2,4}\)[\s\-]?\d{3,4}[\s\-]?\d{3,4}', 0.80),
    ]

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "universal"

    @property
    def priority(self) -> int:
        return 30  # Lower than locale-specific phone recognizers

    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []
        for pattern, score in self.PATTERNS:
            for match in re.finditer(pattern, text):
                phone = match.group().strip()
                # Filter out numbers that are too short to be real phones
                digits_only = re.sub(r'\D', '', phone)
                if len(digits_only) < 7 or len(digits_only) > 15:
                    continue
                results.append(RecognizerResult(
                    entity_type=self.ENTITY_TYPE,
                    start=match.start(),
                    end=match.end(),
                    score=score,
                    text=phone,
                    locale=self.locale,
                ))
        return self._deduplicate(results)
