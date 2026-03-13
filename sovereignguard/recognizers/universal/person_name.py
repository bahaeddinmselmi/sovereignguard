"""
Universal Person Name Recognizer

Detects common person names using contextual pattern matching.
Looks for names preceded by titles, salutations, or name-indicating
keywords like "name:", "from:", "client:", etc.

This is a heuristic recognizer — it uses contextual clues rather than
full NLP, keeping the dependency footprint light.
"""

import re
from typing import List

from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class PersonNameRecognizer(BaseRecognizer):

    @property
    def entity_types(self) -> List[str]:
        return ["PERSON_NAME"]

    @property
    def locale(self) -> str:
        return "universal"

    @property
    def priority(self) -> int:
        return 40  # Lower priority — let locale-specific recognizers take precedence

    # Common titles and salutations (multi-language)
    _TITLES = (
        r"(?:Mr|Mrs|Ms|Miss|Dr|Prof|Eng|Mme|Mlle|M\.|Maître|"
        r"Si|Sra|Sidi|Lalla|Hajj|Hajja)"
    )

    # Context keywords that precede a name
    _NAME_CONTEXTS = (
        r"(?:name|nom|اسم|client|customer|employee|patient|"
        r"contact|debtor|creditor|borrower|user|subscriber|"
        r"applicant|candidate|owner|beneficiary|signataire|"
        r"signed by|from|to|dear|cher|chère|attn)"
    )

    # Name pattern: 2-4 capitalized words (Unicode-aware for Arabic/French names)
    _NAME_PATTERN = r"([A-ZÀ-ÿ][a-zà-ÿ]+(?:\s+(?:ben|el|al|de|du|van|von|di|le|la|ibn|bint|ould|ait|ou)?(?:\s+)?[A-ZÀ-ÿ][a-zà-ÿ]+){1,3})"

    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []

        # Pattern 1: Title + Name (highest confidence)
        title_pattern = re.compile(
            rf"\b{self._TITLES}\.?\s+{self._NAME_PATTERN}",
            re.IGNORECASE | re.UNICODE,
        )
        for match in title_pattern.finditer(text):
            name_match = re.search(self._NAME_PATTERN, match.group())
            if name_match:
                abs_start = match.start() + name_match.start()
                abs_end = match.start() + name_match.end()
                results.append(RecognizerResult(
                    entity_type="PERSON_NAME",
                    start=abs_start,
                    end=abs_end,
                    score=0.85,
                    text=name_match.group(),
                    locale=self.locale,
                ))

        # Pattern 2: Context keyword + Name (medium confidence)
        context_pattern = re.compile(
            rf"\b{self._NAME_CONTEXTS}\s*[:=\-]?\s*{self._NAME_PATTERN}",
            re.IGNORECASE | re.UNICODE,
        )
        for match in context_pattern.finditer(text):
            name_match = re.search(self._NAME_PATTERN, match.group())
            if name_match:
                abs_start = match.start() + name_match.start()
                abs_end = match.start() + name_match.end()
                # Skip if already captured by title pattern
                if not any(
                    r.start == abs_start and r.end == abs_end
                    for r in results
                ):
                    results.append(RecognizerResult(
                        entity_type="PERSON_NAME",
                        start=abs_start,
                        end=abs_end,
                        score=0.75,
                        text=name_match.group(),
                        locale=self.locale,
                    ))

        return self._deduplicate(results)
