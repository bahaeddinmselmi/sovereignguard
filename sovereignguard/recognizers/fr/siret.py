"""
French SIRET/SIREN Recognizer

SIREN: 9 digits — unique company identifier
SIRET: 14 digits — SIREN + 5-digit NIC (establishment code)
Both are validated with the Luhn algorithm.
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class FrenchSIRETRecognizer(BaseRecognizer):

    ENTITY_TYPE_SIRET = "FR_SIRET"
    ENTITY_TYPE_SIREN = "FR_SIREN"

    CONTEXT_KEYWORDS = [
        r'\bSIRET\b',
        r'\bSIREN\b',
        r'registre\s+du\s+commerce',
        r'\bRCS\b',
        r'immatriculation',
        r'num[eé]ro\s+d\'entreprise',
    ]

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE_SIRET, self.ENTITY_TYPE_SIREN]

    @property
    def locale(self) -> str:
        return "fr"

    @property
    def priority(self) -> int:
        return 75

    def analyze(self, text: str) -> List[RecognizerResult]:
        has_context = any(
            re.search(kw, text, re.IGNORECASE)
            for kw in self.CONTEXT_KEYWORDS
        )

        results = []

        # SIRET: 14 digits, optionally formatted with spaces
        for match in re.finditer(r'\b(\d{3}[\s]?\d{3}[\s]?\d{3}[\s]?\d{5})\b', text):
            digits = re.sub(r'\s', '', match.group())
            if len(digits) == 14 and self._luhn_check(digits):
                score = 0.95 if has_context else 0.80
                results.append(RecognizerResult(
                    entity_type=self.ENTITY_TYPE_SIRET,
                    start=match.start(),
                    end=match.end(),
                    score=score,
                    text=match.group(),
                    locale=self.locale,
                ))

        # SIREN: 9 digits
        for match in re.finditer(r'\b(\d{3}[\s]?\d{3}[\s]?\d{3})\b', text):
            digits = re.sub(r'\s', '', match.group())
            if len(digits) == 9 and self._luhn_check(digits):
                # Only count as SIREN if not already part of a SIRET
                is_part_of_siret = any(
                    r.start <= match.start() and r.end >= match.end()
                    for r in results
                )
                if not is_part_of_siret:
                    score = 0.90 if has_context else 0.70
                    results.append(RecognizerResult(
                        entity_type=self.ENTITY_TYPE_SIREN,
                        start=match.start(),
                        end=match.end(),
                        score=score,
                        text=match.group(),
                        locale=self.locale,
                    ))

        return self._deduplicate(results)

    @staticmethod
    def _luhn_check(number: str) -> bool:
        total = 0
        for i, digit in enumerate(reversed(number)):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return total % 10 == 0
