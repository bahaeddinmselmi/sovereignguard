"""
IP Address Recognizer (Universal)
Detects IPv4 and IPv6 addresses.
"""

import re
from typing import List
from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class IPAddressRecognizer(BaseRecognizer):

    ENTITY_TYPE = "IP_ADDRESS"

    IPV4_PATTERN = (
        r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}'
        r'(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'
    )

    # Simplified IPv6 — full and compressed forms
    IPV6_PATTERN = (
        r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'
        r'|'
        r'\b(?:[0-9a-fA-F]{1,4}:){1,7}:\b'
        r'|'
        r'\b::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}\b'
    )

    # Common non-PII IPs to exclude
    EXCLUDED_IPS = {"0.0.0.0", "127.0.0.1", "255.255.255.255", "::1"}

    @property
    def entity_types(self) -> List[str]:
        return [self.ENTITY_TYPE]

    @property
    def locale(self) -> str:
        return "universal"

    @property
    def priority(self) -> int:
        return 35

    def analyze(self, text: str) -> List[RecognizerResult]:
        results = []

        # IPv4
        for match in re.finditer(self.IPV4_PATTERN, text):
            ip = match.group()
            if ip in self.EXCLUDED_IPS:
                continue
            results.append(RecognizerResult(
                entity_type=self.ENTITY_TYPE,
                start=match.start(),
                end=match.end(),
                score=0.90,
                text=ip,
                locale=self.locale,
            ))

        # IPv6
        for match in re.finditer(self.IPV6_PATTERN, text):
            ip = match.group()
            if ip in self.EXCLUDED_IPS:
                continue
            results.append(RecognizerResult(
                entity_type=self.ENTITY_TYPE,
                start=match.start(),
                end=match.end(),
                score=0.85,
                text=ip,
                locale=self.locale,
            ))

        return self._deduplicate(results)
