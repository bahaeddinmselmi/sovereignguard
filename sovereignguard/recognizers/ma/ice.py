"""
Moroccan ICE (Identifiant Commun de l'Entreprise) Recognizer

Format: 15 digits
The ICE is assigned by the CRI (Centre Régional d'Investissement)
and is mandatory for all Moroccan businesses since 2018.
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class MoroccanICERecognizer(BaseRecognizer):

    ENTITY_TYPE = "MA_ICE"

    CONTEXT_KEYWORDS = [
        r'\bICE\b',
        r'identifiant\s+commun',
        r'identifiant\s+d\'entreprise',
        r'المعرف\s+المشترك\s+للمقاولة',
        r'رقم\s+المقاولة',
    ]

    # ICE: exactly 15 digits
    PATTERN = r'\b(\d{15})\b'

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "ma"

    @property
    def priority(self) -> int:
        return 85

    def analyze(self, text: str) -> List[RecognizerResult]:
        has_context = any(
            re.search(kw, text, re.IGNORECASE | re.UNICODE)
            for kw in self.CONTEXT_KEYWORDS
        )

        results = []
        for match in re.finditer(self.PATTERN, text):
            # Without context, a 15-digit number is ambiguous
            score = 0.95 if has_context else 0.55
            results.append(RecognizerResult(
                entity_type=self.ENTITY_TYPE,
                start=match.start(),
                end=match.end(),
                score=score,
                text=match.group(),
                locale=self.locale,
            ))

        return self._deduplicate(results)
