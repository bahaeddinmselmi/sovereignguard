"""
French Address Recognizer

Detects French street addresses including postal codes (5 digits),
departments, and common street type keywords.
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class FrenchAddressRecognizer(BaseRecognizer):

    ENTITY_TYPE = "FR_ADDRESS"

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "fr"

    @property
    def priority(self) -> int:
        return 60

    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []

        # French postal code + city:  75008 Paris, 13001 Marseille
        postal_pattern = r'\b(\d{5})\s+([A-ZÀ-Ü][a-zà-ÿ\-]+(?:\s+[a-zà-ÿ\-]+){0,3})\b'
        for match in re.finditer(postal_pattern, text, re.UNICODE):
            code = match.group(1)
            dept = int(code[:2])
            # Valid French department codes: 01-95, 97x (overseas)
            if 1 <= dept <= 95 or 971 <= int(code[:3]) <= 976:
                results.append(RecognizerResult(
                    entity_type=self.ENTITY_TYPE,
                    start=match.start(),
                    end=match.end(),
                    score=0.85,
                    text=match.group(),
                    locale=self.locale,
                ))

        # Street address: "12 rue de la Paix, 75002 Paris"
        street_pattern = (
            r'\d{1,4}[\s,]+(?:rue|avenue|boulevard|place|allée|impasse|chemin|route|passage|quai|cours)'
            r'[\s\w\-\',éèêëàâîïôùûü]{3,60}'
            r'(?:,\s*\d{5}\s*[A-Za-zéèêëàâîïôùûü\s\-]+)?'
        )
        for match in re.finditer(street_pattern, text, re.IGNORECASE | re.UNICODE):
            results.append(RecognizerResult(
                entity_type=self.ENTITY_TYPE,
                start=match.start(),
                end=match.end(),
                score=0.85,
                text=match.group(),
                locale=self.locale,
            ))

        return self._deduplicate(results)
