"""
French NIR (Numéro d'Inscription au Répertoire) Recognizer

The NIR is the French social security number.
Format: 15 digits — sex (1) + year (2) + month (2) + department (2) +
commune (3) + order (3) + control key (2)
Example: 1 85 05 78 006 084 36
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class FrenchNIRRecognizer(BaseRecognizer):

    ENTITY_TYPE = "FR_NIR"

    CONTEXT_KEYWORDS = [
        r'\bNIR\b',
        r'num[eé]ro\s+de\s+s[eé]curit[eé]\s+sociale',
        r's[eé]curit[eé]\s+sociale',
        r'num[eé]ro\s+INSEE',
        r'\bINSEE\b',
        r'immatriculation',
    ]

    # NIR pattern: 1 or 2 for sex, then 14 more digits with optional spaces/dots
    PATTERNS = [
        # Formatted with spaces
        (r'\b[12]\s?\d{2}\s?\d{2}\s?\d{2,3}\s?\d{3}\s?\d{3}\s?\d{2}\b', 0.90),
        # Compact 15 digits
        (r'\b[12]\d{14}\b', 0.80),
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
        has_context = any(
            re.search(kw, text, re.IGNORECASE | re.UNICODE)
            for kw in self.CONTEXT_KEYWORDS
        )

        results = []
        for pattern, base_score in self.PATTERNS:
            score = min(0.99, base_score + (0.08 if has_context else 0))
            for match in re.finditer(pattern, text):
                value = match.group()
                digits = re.sub(r'\s', '', value)

                # Basic format validation
                if len(digits) != 15:
                    continue

                # Check sex digit
                if digits[0] not in ('1', '2'):
                    continue

                # Check month (01-12 or 20-42 for overseas)
                month = int(digits[3:5])
                if month < 1 or (month > 12 and month < 20) or month > 42:
                    continue

                # Control key validation (mod 97)
                try:
                    base_number = int(digits[:13])
                    key = int(digits[13:15])
                    if (97 - (base_number % 97)) == key:
                        score = min(0.99, score + 0.05)
                except ValueError:
                    pass

                results.append(RecognizerResult(
                    entity_type=self.ENTITY_TYPE,
                    start=match.start(),
                    end=match.end(),
                    score=score,
                    text=value,
                    locale=self.locale,
                ))

        return self._deduplicate(results)
