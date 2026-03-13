"""
IBAN (International Bank Account Number) Recognizer (Universal)
Detects IBAN numbers using structural validation and country-specific lengths.
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


# Expected IBAN lengths by country code
IBAN_LENGTHS = {
    "AL": 28, "AD": 24, "AT": 20, "AZ": 28, "BH": 22, "BY": 28,
    "BE": 16, "BA": 20, "BR": 29, "BG": 22, "CR": 22, "HR": 21,
    "CY": 28, "CZ": 24, "DK": 18, "DO": 28, "TL": 23, "EG": 29,
    "SV": 28, "EE": 20, "FO": 18, "FI": 18, "FR": 27, "GE": 22,
    "DE": 22, "GI": 23, "GR": 27, "GL": 18, "GT": 28, "HU": 28,
    "IS": 26, "IQ": 23, "IE": 22, "IL": 23, "IT": 27, "JO": 30,
    "KZ": 20, "XK": 20, "KW": 30, "LV": 21, "LB": 28, "LY": 25,
    "LI": 21, "LT": 20, "LU": 20, "MK": 19, "MT": 31, "MR": 27,
    "MU": 30, "MC": 27, "MD": 24, "ME": 22, "NL": 18, "NO": 15,
    "PK": 24, "PS": 29, "PL": 28, "PT": 25, "QA": 29, "RO": 24,
    "LC": 32, "SM": 27, "ST": 25, "SA": 24, "RS": 22, "SC": 31,
    "SK": 24, "SI": 19, "ES": 24, "SD": 18, "SE": 24, "CH": 21,
    "TN": 24, "TR": 26, "UA": 29, "AE": 23, "GB": 22, "VA": 22,
    "VG": 24, "MA": 28,
}


class IBANRecognizer(BaseRecognizer):

    ENTITY_TYPE = "IBAN"

    # IBAN: 2 upper letters, 2 digits, then 10-30 alphanumerics (with optional spaces/dashes)
    PATTERN = r'\b[A-Z]{2}\d{2}[\s\-]?[\dA-Z]{4}[\s\-]?(?:[\dA-Z]{4}[\s\-]?){1,7}[\dA-Z]{1,4}\b'

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
            candidate = match.group()
            clean = re.sub(r'[\s\-]', '', candidate)

            country_code = clean[:2].upper()
            expected_len = IBAN_LENGTHS.get(country_code)

            if expected_len is None:
                continue
            if len(clean) != expected_len:
                continue

            score = 0.95 if self._mod97_check(clean) else 0.70

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
    def _mod97_check(iban: str) -> bool:
        """ISO 13616 mod-97 check digit validation."""
        rearranged = iban[4:] + iban[:4]
        numeric = ""
        for ch in rearranged:
            if ch.isdigit():
                numeric += ch
            else:
                numeric += str(ord(ch.upper()) - 55)
        return int(numeric) % 97 == 1
