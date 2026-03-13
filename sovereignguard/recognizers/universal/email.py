"""
Email Address Recognizer (Universal)
Detects email addresses in text using RFC 5322 compatible patterns.
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class EmailRecognizer(BaseRecognizer):

    ENTITY_TYPE = "EMAIL"

    PATTERN = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "universal"

    @property
    def priority(self) -> int:
        return 40

    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []
        for match in re.finditer(self.PATTERN, text):
            results.append(RecognizerResult(
                entity_type=self.ENTITY_TYPE,
                start=match.start(),
                end=match.end(),
                score=0.95,
                text=match.group(),
                locale=self.locale,
            ))
        return self._deduplicate(results)
