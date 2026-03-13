"""
Tunisian Matricule Fiscale (Tax Registration Number) Recognizer

Format: 7 digits + 1 letter + 3 alphanumeric
Example: 1234567A/P/000
The letter indicates legal form: A=SARL, B=SA, P=Personne Physique, etc.
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class TunisianMatriculeFiscaleRecognizer(BaseRecognizer):

    ENTITY_TYPE = "TN_MATRICULE_FISCALE"

    CONTEXT_KEYWORDS = [
        r'\bMF\b',
        r'matricule\s+fiscale?',
        r'identifiant\s+fiscal',
        r'معرف\s+جبائي',  # Arabic
        r'رقم\s+الأداء',  # Arabic: tax number
    ]

    # Pattern: 7 digits / 1 letter / 1 letter / 3 digits
    PATTERNS = [
        (r'\b\d{7}[A-Z]/[A-Z]/\d{3}\b', 0.98),       # Full format with slashes
        (r'\b\d{7}[A-Z][A-Z]\d{3}\b', 0.85),          # Compact format
        (r'\b\d{7}[A-Z]\b', 0.70),                     # Partial (7 digits + letter)
    ]

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "tn"

    @property
    def priority(self) -> int:
        return 85

    def analyze(self, text: str) -> List[RecognizerResult]:
        has_context = any(
            re.search(kw, text, re.IGNORECASE | re.UNICODE)
            for kw in self.CONTEXT_KEYWORDS
        )

        results = []
        for pattern, base_score in self.PATTERNS:
            score = min(0.99, base_score + (0.05 if has_context else 0))
            for match in re.finditer(pattern, text, re.IGNORECASE):
                results.append(RecognizerResult(
                    entity_type=self.ENTITY_TYPE,
                    start=match.start(),
                    end=match.end(),
                    score=score,
                    text=match.group(),
                    locale=self.locale
                ))

        return self._deduplicate(results)
