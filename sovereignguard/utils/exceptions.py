"""
Custom exceptions for SovereignGuard.
"""


class SovereignGuardError(Exception):
    """Base exception for all SovereignGuard errors."""
    pass


class MaskingError(SovereignGuardError):
    """Raised when PII masking fails."""
    pass


class RestorationError(SovereignGuardError):
    """Raised when PII restoration fails."""
    pass


class SessionNotFoundError(SovereignGuardError):
    """Raised when a mapping session does not exist."""
    pass


class SessionExpiredError(SovereignGuardError):
    """Raised when a mapping session has expired (TTL exceeded)."""
    pass


class RecognizerError(SovereignGuardError):
    """Raised when a recognizer fails during analysis."""
    pass


class EncryptionError(SovereignGuardError):
    """Raised when encryption or decryption operations fail."""
    pass


class ConfigurationError(SovereignGuardError):
    """Raised for invalid configuration values."""
    pass


class TargetAPIError(SovereignGuardError):
    """Raised when the target LLM API returns an error."""

    def __init__(self, status_code: int, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Target API error {status_code}: {detail}")
