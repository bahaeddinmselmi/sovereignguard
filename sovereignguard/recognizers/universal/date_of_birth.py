"""
Universal Date of Birth Recognizer

Detects dates that appear in a PII context (birth date, DOB, date de naissance).
Differentiates between general dates and dates that are personally identifiable
by requiring contextual keywords nearby.

Supports formats:
- DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
- YYYY-MM-DD (ISO)
- MM/DD/YYYY (US)
- Textual: "15 January 1990", "15 janvier 1990"
"""

import re
from typing import List

from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class DateOfBirthRecognizer(BaseRecognizer):

    @property
    def entity_types(self) -> List[str]:
        return ["DATE_OF_BIRTH"]

    @property
    def locale(self) -> str:
        return "universal"

    @property
    def priority(self) -> int:
        return 45

    # Context keywords that indicate a date is a DOB
    _DOB_CONTEXT = (
        r"(?:date\s+(?:of\s+)?birth|birth\s*date|dob|d\.o\.b|"
        r"born\s+(?:on)?|née?\s+le|date\s+de\s+naissance|"
        r"تاريخ\s*الميلاد|تاريخ\s*الولادة|"
        r"fecha\s+de\s+nacimiento|data\s+di\s+nascita|"
        r"geburtsdatum|birthday)"
    )

    # Date patterns
    _DATE_DMY = r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})"
    _DATE_ISO = r"(\d{4}[/\-]\d{1,2}[/\-]\d{1,2})"

    _MONTHS_TEXT = (
        r"(?:january|february|march|april|may|june|july|august|september|october|november|december|"
        r"janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)"
    )
    _DATE_TEXT = rf"(\d{{1,2}}\s+{_MONTHS_TEXT}\s+\d{{2,4}})"
    _DATE_TEXT_ALT = rf"({_MONTHS_TEXT}\s+\d{{1,2}},?\s+\d{{2,4}})"

    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []

        # All date patterns combined
        date_patterns = [
            self._DATE_DMY,
            self._DATE_ISO,
            self._DATE_TEXT,
            self._DATE_TEXT_ALT,
        ]

        # Look for DOB context keyword within 50 chars before/after a date
        for dp in date_patterns:
            for date_match in re.finditer(dp, text, re.IGNORECASE):
                # Check for context within surrounding window
                window_start = max(0, date_match.start() - 50)
                window_end = min(len(text), date_match.end() + 50)
                window = text[window_start:window_end]

                if re.search(self._DOB_CONTEXT, window, re.IGNORECASE):
                    results.append(RecognizerResult(
                        entity_type="DATE_OF_BIRTH",
                        start=date_match.start(),
                        end=date_match.end(),
                        score=0.85,
                        text=date_match.group(),
                        locale=self.locale,
                    ))

        return self._deduplicate(results)
