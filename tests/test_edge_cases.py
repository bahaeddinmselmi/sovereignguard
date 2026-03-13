"""
Edge case tests for recognizers and the masking engine.
"""

import os
import pytest

os.environ.setdefault("TARGET_API_KEY", "test-key")

from sovereignguard.engine.masker import MaskingEngine
from sovereignguard.recognizers.universal.email import EmailRecognizer
from sovereignguard.recognizers.universal.credit_card import CreditCardRecognizer
from sovereignguard.recognizers.universal.iban import IBANRecognizer
from sovereignguard.recognizers.universal.ip_address import IPAddressRecognizer


class TestEdgeCases:

    def setup_method(self):
        self.engine = MaskingEngine()

    def test_empty_string(self):
        session_id = self.engine.new_session()
        result = self.engine.mask("", session_id)
        assert result.masked_text == ""
        assert result.had_pii is False
        self.engine.end_session(session_id)

    def test_single_character(self):
        session_id = self.engine.new_session()
        result = self.engine.mask("a", session_id)
        assert result.masked_text == "a"
        assert result.had_pii is False
        self.engine.end_session(session_id)

    def test_very_long_input(self):
        """Engine should handle large inputs without crashing."""
        session_id = self.engine.new_session()
        text = "A" * 100_000 + " user@example.com " + "B" * 100_000
        result = self.engine.mask(text, session_id)
        assert result.had_pii is True
        assert "user@example.com" not in result.masked_text
        self.engine.end_session(session_id)

    def test_unicode_text_no_crash(self):
        """Engine should handle Unicode text gracefully."""
        session_id = self.engine.new_session()
        text = "مرحبا 🎉 test@example.com こんにちは"
        result = self.engine.mask(text, session_id)
        assert result.had_pii is True
        assert "test@example.com" not in result.masked_text
        self.engine.end_session(session_id)

    def test_overlapping_detections(self):
        """When two recognizers detect overlapping regions, keep highest confidence."""
        session_id = self.engine.new_session()
        # This text could match phone and credit card patterns
        text = "number +216 98 765 432"
        result = self.engine.mask(text, session_id)
        assert result.had_pii is True
        self.engine.end_session(session_id)

    def test_multiple_sessions_isolated(self):
        """Tokens from one session should not be restorable in another."""
        session_a = self.engine.new_session()
        session_b = self.engine.new_session()

        masked_a = self.engine.mask("email: user@example.com", session_a)
        restored_b = self.engine.restore(masked_a.masked_text, session_b)

        # Token should not be found in session B
        assert restored_b.tokens_not_found >= 1
        assert "user@example.com" not in restored_b.restored_text

        self.engine.end_session(session_a)
        self.engine.end_session(session_b)

    def test_session_cleanup_prevents_restore(self):
        """After ending a session, restore should fail for that session's tokens."""
        session_id = self.engine.new_session()
        masked = self.engine.mask("email: user@example.com", session_id)
        self.engine.end_session(session_id)

        restored = self.engine.restore(masked.masked_text, session_id)
        assert restored.tokens_not_found >= 1

    def test_restore_preserves_non_token_text(self):
        """Non-token text should be preserved during restoration."""
        session_id = self.engine.new_session()
        text = "Hello world, no PII here"
        restored = self.engine.restore(text, session_id)
        assert restored.restored_text == text
        assert restored.tokens_restored == 0
        self.engine.end_session(session_id)


class TestEmailEdgeCases:

    def setup_method(self):
        self.recognizer = EmailRecognizer()

    def test_multiple_emails(self):
        text = "contact user@a.com or admin@b.org"
        results = self.recognizer.analyze(text)
        assert len(results) == 2

    def test_email_with_plus(self):
        text = "email: user+tag@example.com"
        results = self.recognizer.analyze(text)
        assert len(results) == 1

    def test_email_with_dots(self):
        text = "email: first.last@example.co.uk"
        results = self.recognizer.analyze(text)
        assert len(results) == 1


class TestIPAddressEdgeCases:

    def setup_method(self):
        self.recognizer = IPAddressRecognizer()

    def test_valid_ipv4(self):
        results = self.recognizer.analyze("Server at 192.168.1.100")
        assert len(results) == 1

    def test_no_false_positive_on_version_numbers(self):
        """Version numbers like 1.2.3 should not be detected as IPs."""
        results = self.recognizer.analyze("Python version 3.11.5")
        # Should not match as IP (only 3 octets)
        assert len(results) == 0


class TestMappingStoreTTL:

    def test_purge_expired_returns_count(self):
        """purge_expired should return the number of purged sessions."""
        engine = MaskingEngine()
        session_id = engine.new_session()
        engine.mask("email: user@example.com", session_id)

        # With a very high TTL, nothing should be purged
        purged = engine.mapping_store.purge_expired(999999)
        assert purged == 0

        engine.end_session(session_id)
