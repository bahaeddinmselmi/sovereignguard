"""
Credit Card Number Recognizer (Universal)
Detects major credit card formats and validates with Luhn algorithm.
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class CreditCardRecognizer(BaseRecognizer):

    ENTITY_TYPE = "CREDIT_CARD"

    # Common card patterns (Visa, MasterCard, Amex, etc.)
    PATTERN = r'\b(?:\d[ \-]?){13,19}\b'

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "universal"

    @property
    def priority(self) -> int:
        return 45

    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []
        for match in re.finditer(self.PATTERN, text):
            candidate = match.group().strip()
            digits = re.sub(r'[\s\-]', '', candidate)

            # Must be 13–19 digits
            if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
                continue

            # Luhn check
            if not self._luhn_check(digits):
                continue

            # Determine score from prefix
            score = 0.95 if self._matches_known_prefix(digits) else 0.80

            results.append(RecognizerResult(
                entity_type=self.ENTITY_TYPE,
                start=match.start(),
                end=match.end(),
                score=score,
                text=candidate,
                locale=self.locale,
            ))
        return self._deduplicate(results)

    @staticmethod
    def _luhn_check(number: str) -> bool:
        total = 0
        reverse_digits = number[::-1]
        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return total % 10 == 0

    @staticmethod
    def _matches_known_prefix(digits: str) -> bool:
        """Check if number matches known card brand prefixes."""
        if digits.startswith('4') and len(digits) in (13, 16, 19):
            return True  # Visa
        if digits[:2] in ('51', '52', '53', '54', '55'):
            return True  # MasterCard
        if digits[:2] in ('34', '37') and len(digits) == 15:
            return True  # Amex
        if digits[:4] in ('6011', '6221', '6229') or digits[:2] == '65':
            return True  # Discover
        return False
