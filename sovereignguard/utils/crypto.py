"""
Encryption utilities for SovereignGuard.

Provides AES-256-GCM encryption for PII values stored in mapping backends.
Each value is encrypted with a unique nonce for semantic security.
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# Module-level key, initialized lazily
_encryption_key: bytes | None = None


def _get_key() -> bytes:
    """Get or generate the encryption key."""
    global _encryption_key
    if _encryption_key is not None:
        return _encryption_key

    from sovereignguard.config import settings

    if settings.ENCRYPTION_KEY:
        _encryption_key = base64.b64decode(settings.ENCRYPTION_KEY)
    else:
        # Auto-generate a session-scoped key (not persisted)
        _encryption_key = AESGCM.generate_key(bit_length=256)

    return _encryption_key


def encrypt_value(plaintext: str) -> bytes:
    """
    Encrypt a PII value using AES-256-GCM.

    Returns nonce + ciphertext as a single bytes object.
    Each call uses a unique 12-byte nonce.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ciphertext


def decrypt_value(encrypted: bytes) -> str:
    """
    Decrypt a PII value previously encrypted with encrypt_value.

    Expects nonce (first 12 bytes) + ciphertext.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
