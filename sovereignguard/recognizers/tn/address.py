"""
Tunisian Address Recognizer

Detects Tunisian street addresses including governorates, postal codes,
and common Tunisian city/neighborhood patterns.
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class TunisianAddressRecognizer(BaseRecognizer):

    ENTITY_TYPE = "TN_ADDRESS"

    # All 24 Tunisian governorates
    GOVERNORATES = [
        "Tunis", "Ariana", "Ben Arous", "Manouba",
        "Nabeul", "Zaghouan", "Bizerte", "Béja",
        "Jendouba", "Le Kef", "Siliana", "Sousse",
        "Monastir", "Mahdia", "Sfax", "Kairouan",
        "Kasserine", "Sidi Bouzid", "Gabès", "Médenine",
        "Tataouine", "Gafsa", "Tozeur", "Kébili",
    ]

    # Common Tunisian locality keywords (French + Arabic)
    LOCALITY_KEYWORDS = [
        r'\bdelegation\b', r'\bimmeuble\b', r'\bappt\b', r'\bappartement\b',
        r'\bcite\b', r'\bcit[eé]\b', r'\blot\b', r'\blotissement\b',
        r'\broute\s+de\b', r'\bzone\s+industrielle\b',
        r'حي', r'نهج', r'شارع', r'طريق', r'عمارة', r'شقة', r'ولاية',
    ]

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "tn"

    @property
    def priority(self) -> int:
        return 60

    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []

        # Tunisian postal code pattern: 4 digits, usually 1000-9999
        postal_pattern = r'\b(\d{4})\s+(' + '|'.join(re.escape(g) for g in self.GOVERNORATES) + r')\b'
        for match in re.finditer(postal_pattern, text, re.IGNORECASE):
            code = match.group(1)
            if 1000 <= int(code) <= 9999:
                score = 0.90

                # Boost if nearby address keywords appear
                context_start = max(0, match.start() - 60)
                context_end = min(len(text), match.end() + 60)
                local_context = text[context_start:context_end]
                if any(re.search(kw, local_context, re.IGNORECASE | re.UNICODE)
                       for kw in self.LOCALITY_KEYWORDS):
                    score = 0.95

                results.append(RecognizerResult(
                    entity_type=self.ENTITY_TYPE,
                    start=match.start(),
                    end=match.end(),
                    score=score,
                    text=match.group(),
                    locale=self.locale,
                ))

        # Street address pattern: "rue/avenue/boulevard ... , <postal_code> <city>"
        street_pattern = (
            r'(?:rue|avenue|av\.|boulevard|blvd|impasse|lotissement|cité|résidence|حي|شارع|نهج)'
            r'[\s\w\-\',éèêëàâîïôùûü]{3,60}'
            r'(?:,\s*\d{4}\s*[A-Za-zéèêëàâîïôùûü\s]+)?'
        )
        for match in re.finditer(street_pattern, text, re.IGNORECASE | re.UNICODE):
            fragment = match.group()
            score = 0.80

            # More complete addresses with numeric street/building cues are stronger.
            if re.search(r'\b\d{1,4}\b', fragment):
                score += 0.06
            if any(re.search(kw, fragment, re.IGNORECASE | re.UNICODE)
                   for kw in self.LOCALITY_KEYWORDS):
                score += 0.06

            results.append(RecognizerResult(
                entity_type=self.ENTITY_TYPE,
                start=match.start(),
                end=match.end(),
                score=min(0.95, score),
                text=fragment,
                locale=self.locale,
            ))

        return self._deduplicate(results)
