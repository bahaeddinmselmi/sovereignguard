"""
Tunisian National ID (Carte d'Identité Nationale - CIN) Recognizer

Format: 8 digits exactly
Examples: 12345678, 08765432
Context clues: "CIN", "Carte d'identité", "N° national", "رقم بطاقة"

Confidence scoring:
- 8 digits with CIN context keyword nearby: 0.95
- 8 digits standalone (ambiguous): 0.65
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class TunisianNationalIDRecognizer(BaseRecognizer):

    ENTITY_TYPE = "TN_NATIONAL_ID"

    # Context keywords that increase confidence
    CONTEXT_KEYWORDS = [
        r'\bCIN\b',
        r'carte\s+d\'identit[eé]',
        r'identit[eé]\s+nationale',
        r'num[eé]ro\s+national',
        r'رقم\s+بطاقة',          # Arabic: card number
        r'بطاقة\s+التعريف',      # Arabic: ID card
        r'مواطن',                # Arabic: citizen
        r'n°\s*national',
        r'national\s*id',
    ]

    # Core pattern: exactly 8 digits, not part of longer number
    CORE_PATTERN = r'(?<!\d)(\d{8})(?!\d)'

    # Low-quality / suspicious patterns that reduce confidence
    SUSPICIOUS_PATTERNS = [
        r'^(\d)\1{7}$',           # 11111111, 22222222
        r'^00000000$',
    ]

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "tn"

    @property
    def priority(self) -> int:
        return 75  # Higher than universal recognizers

    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []

        # Check for context keywords in surrounding text
        has_context = any(
            re.search(kw, text, re.IGNORECASE | re.UNICODE)
            for kw in self.CONTEXT_KEYWORDS
        )

        base_score = 0.90 if has_context else 0.65

        # Find all 8-digit sequences
        for match in re.finditer(self.CORE_PATTERN, text):
            value = match.group()

            # Adjust confidence based on value characteristics
            score = base_score
            if value.startswith('0'):
                score -= 0.10  # Less common but valid

            # Boost if surrounded by CIN-related context within 50 chars
            start_context = max(0, match.start() - 50)
            end_context = min(len(text), match.end() + 50)
            local_context = text[start_context:end_context]

            local_has_context = any(
                re.search(kw, local_context, re.IGNORECASE | re.UNICODE)
                for kw in self.CONTEXT_KEYWORDS
            )

            if local_has_context:
                score = min(0.98, score + 0.15)

            # Penalize clearly synthetic/test values
            if any(re.match(p, value) for p in self.SUSPICIOUS_PATTERNS):
                score = max(0.40, score - 0.30)

            # Slight boost for realistic ranges (first digit often non-zero)
            if value[0] != '0':
                score = min(0.99, score + 0.03)

            results.append(RecognizerResult(
                entity_type=self.ENTITY_TYPE,
                start=match.start(),
                end=match.end(),
                score=score,
                text=match.group(),
                locale=self.locale
            ))

        return self._deduplicate(results)
