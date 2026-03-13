"""
PII Mapping Store

Manages the token ↔ original_value mappings.
Supports multiple backends:
- Memory: Fast, session-scoped, no persistence (default for development)
- Encrypted Local: AES-256 SQLite, survives restarts (recommended for production)
- Redis: For multi-instance/distributed deployments

SECURITY: This module handles the most sensitive data in the system.
Original PII values are stored encrypted at rest in all persistent backends.
In-memory backend holds plaintext in RAM only — never written to disk.
"""

import os
import time
import json
import sqlite3
import hashlib
import threading
from base64 import b64decode, b64encode
from typing import Dict, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sovereignguard.config import settings, MappingBackend
from sovereignguard.utils.crypto import encrypt_value, decrypt_value


@dataclass
class MappingEntry:
    token: str
    encrypted_value: bytes
    entity_type: str
    created_at: float = field(default_factory=time.time)
    access_count: int = 0


class BaseMappingBackend(ABC):
    @abstractmethod
    def create_session(self, session_id: str): pass

    @abstractmethod
    def store(self, session_id: str, token: str, original_value: str, entity_type: str): pass

    @abstractmethod
    def retrieve(self, session_id: str, token: str) -> Optional[str]: pass

    @abstractmethod
    def get_token_for_value(self, session_id: str, value: str, entity_type: str) -> Optional[str]: pass

    @abstractmethod
    def destroy_session(self, session_id: str): pass


class InMemoryBackend(BaseMappingBackend):
    """
    Thread-safe in-memory mapping store.

    Data lives only in RAM. Never touches disk.
    Cleared on process restart or explicit session destruction.

    Best for: Development, short-lived request processing,
    environments where data sovereignty requires zero persistence.
    """

    def __init__(self):
        # {session_id: {token: MappingEntry}}
        self._sessions: Dict[str, Dict[str, MappingEntry]] = {}
        # {session_id: {value_hash: token}} — for deduplication
        self._value_index: Dict[str, Dict[str, str]] = {}
        self._lock = threading.RLock()

    def create_session(self, session_id: str):
        with self._lock:
            self._sessions[session_id] = {}
            self._value_index[session_id] = {}

    def store(self, session_id: str, token: str, original_value: str, entity_type: str):
        with self._lock:
            if session_id not in self._sessions:
                self.create_session(session_id)

            # Encrypt even in memory for defense-in-depth
            encrypted = encrypt_value(original_value)

            self._sessions[session_id][token] = MappingEntry(
                token=token,
                encrypted_value=encrypted,
                entity_type=entity_type
            )

            # Build value index for deduplication
            value_hash = self._hash_value(original_value, entity_type)
            self._value_index[session_id][value_hash] = token

    def retrieve(self, session_id: str, token: str) -> Optional[str]:
        with self._lock:
            session = self._sessions.get(session_id, {})
            entry = session.get(token)
            if not entry:
                return None
            entry.access_count += 1
            return decrypt_value(entry.encrypted_value)

    def get_token_for_value(
        self, session_id: str, value: str, entity_type: str
    ) -> Optional[str]:
        """Check if we already have a token for this value (deduplication)."""
        with self._lock:
            value_hash = self._hash_value(value, entity_type)
            index = self._value_index.get(session_id, {})
            return index.get(value_hash)

    def destroy_session(self, session_id: str):
        with self._lock:
            # Explicit deletion to clear from RAM immediately
            if session_id in self._sessions:
                del self._sessions[session_id]
            if session_id in self._value_index:
                del self._value_index[session_id]

    def purge_expired(self, ttl_seconds: int) -> int:
        """Remove sessions older than TTL. Returns number of purged sessions."""
        now = time.time()
        expired_sessions = []

        with self._lock:
            for session_id, entries in self._sessions.items():
                if entries:
                    newest = max(e.created_at for e in entries.values())
                    if now - newest > ttl_seconds:
                        expired_sessions.append(session_id)
                else:
                    # Empty session — created but never used
                    expired_sessions.append(session_id)

            for session_id in expired_sessions:
                if session_id in self._sessions:
                    del self._sessions[session_id]
                if session_id in self._value_index:
                    del self._value_index[session_id]

        return len(expired_sessions)

    def _hash_value(self, value: str, entity_type: str) -> str:
        """One-way hash for deduplication index. Cannot recover original value."""
        return hashlib.sha256(f"{entity_type}:{value}".encode()).hexdigest()


class EncryptedSQLiteBackend(BaseMappingBackend):
    """Encrypted local SQLite mapping backend with session-scoped cleanup."""

    def __init__(self):
        db_path = settings.ENCRYPTED_DB_PATH
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mappings (
                session_id TEXT NOT NULL,
                token TEXT NOT NULL,
                value_hash TEXT NOT NULL,
                encrypted_value BLOB NOT NULL,
                entity_type TEXT NOT NULL,
                created_at REAL NOT NULL,
                access_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (session_id, token)
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mappings_value_hash ON mappings (session_id, value_hash)"
        )
        self._conn.commit()
        self._lock = threading.RLock()

    def create_session(self, session_id: str):
        # Session state is implicit in persisted mappings.
        return None

    def store(self, session_id: str, token: str, original_value: str, entity_type: str):
        encrypted = encrypt_value(original_value)
        value_hash = self._hash_value(original_value, entity_type)
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO mappings
                (session_id, token, value_hash, encrypted_value, entity_type, created_at, access_count)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE((
                    SELECT access_count FROM mappings WHERE session_id = ? AND token = ?
                ), 0))
                """,
                (session_id, token, value_hash, encrypted, entity_type, time.time(), session_id, token),
            )
            self._conn.commit()

    def retrieve(self, session_id: str, token: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT encrypted_value, access_count FROM mappings WHERE session_id = ? AND token = ?",
                (session_id, token),
            ).fetchone()
            if not row:
                return None
            self._conn.execute(
                "UPDATE mappings SET access_count = access_count + 1 WHERE session_id = ? AND token = ?",
                (session_id, token),
            )
            self._conn.commit()
            return decrypt_value(row[0])

    def get_token_for_value(self, session_id: str, value: str, entity_type: str) -> Optional[str]:
        value_hash = self._hash_value(value, entity_type)
        with self._lock:
            row = self._conn.execute(
                "SELECT token FROM mappings WHERE session_id = ? AND value_hash = ? LIMIT 1",
                (session_id, value_hash),
            ).fetchone()
            return row[0] if row else None

    def destroy_session(self, session_id: str):
        with self._lock:
            self._conn.execute("DELETE FROM mappings WHERE session_id = ?", (session_id,))
            self._conn.commit()

    def purge_expired(self, ttl_seconds: int) -> int:
        """Remove sessions with all entries older than TTL."""
        cutoff = time.time() - ttl_seconds
        with self._lock:
            cursor = self._conn.execute(
                """
                DELETE FROM mappings WHERE session_id IN (
                    SELECT session_id FROM mappings
                    GROUP BY session_id
                    HAVING MAX(created_at) < ?
                )
                """,
                (cutoff,),
            )
            self._conn.commit()
            return cursor.rowcount

    @staticmethod
    def _hash_value(value: str, entity_type: str) -> str:
        return hashlib.sha256(f"{entity_type}:{value}".encode()).hexdigest()


class RedisBackend(BaseMappingBackend):
    """Redis-backed mapping store for distributed deployments."""

    def __init__(self):
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("Redis backend selected but redis package is not installed") from exc

        if not settings.REDIS_URL:
            raise RuntimeError("REDIS_URL must be set when MAPPING_BACKEND=redis")

        self._client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self._ttl_seconds = settings.MAPPING_TTL_SECONDS

    def create_session(self, session_id: str):
        self._client.setex(self._session_marker_key(session_id), self._ttl_seconds, "1")

    def store(self, session_id: str, token: str, original_value: str, entity_type: str):
        encrypted = b64encode(encrypt_value(original_value)).decode("ascii")
        value_hash = self._hash_value(original_value, entity_type)
        entry = {
            "encrypted_value": encrypted,
            "entity_type": entity_type,
            "created_at": time.time(),
            "access_count": 0,
        }

        pipe = self._client.pipeline()
        pipe.hset(self._token_key(session_id), token, json.dumps(entry))
        pipe.hset(self._value_index_key(session_id), value_hash, token)
        pipe.expire(self._token_key(session_id), self._ttl_seconds)
        pipe.expire(self._value_index_key(session_id), self._ttl_seconds)
        pipe.setex(self._session_marker_key(session_id), self._ttl_seconds, "1")
        pipe.execute()

    def retrieve(self, session_id: str, token: str) -> Optional[str]:
        raw_entry = self._client.hget(self._token_key(session_id), token)
        if not raw_entry:
            return None

        entry = json.loads(raw_entry)
        entry["access_count"] = int(entry.get("access_count", 0)) + 1

        pipe = self._client.pipeline()
        pipe.hset(self._token_key(session_id), token, json.dumps(entry))
        pipe.expire(self._token_key(session_id), self._ttl_seconds)
        pipe.expire(self._value_index_key(session_id), self._ttl_seconds)
        pipe.setex(self._session_marker_key(session_id), self._ttl_seconds, "1")
        pipe.execute()

        return decrypt_value(b64decode(entry["encrypted_value"].encode("ascii")))

    def get_token_for_value(self, session_id: str, value: str, entity_type: str) -> Optional[str]:
        value_hash = self._hash_value(value, entity_type)
        return self._client.hget(self._value_index_key(session_id), value_hash)

    def destroy_session(self, session_id: str):
        self._client.delete(
            self._token_key(session_id),
            self._value_index_key(session_id),
            self._session_marker_key(session_id),
        )

    @staticmethod
    def _hash_value(value: str, entity_type: str) -> str:
        return hashlib.sha256(f"{entity_type}:{value}".encode()).hexdigest()

    @staticmethod
    def _token_key(session_id: str) -> str:
        return f"sg:session:{session_id}:tokens"

    @staticmethod
    def _value_index_key(session_id: str) -> str:
        return f"sg:session:{session_id}:values"

    @staticmethod
    def _session_marker_key(session_id: str) -> str:
        return f"sg:session:{session_id}:active"


class VaultBackend(BaseMappingBackend):
    """
    HashiCorp Vault KV v2 backend for mapping storage.

    Stores encrypted token mappings in Vault paths:
      <VAULT_PREFIX>/<session_id>/<token_hash>
    """

    def __init__(self):
        try:
            import hvac  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Vault backend selected but hvac package is not installed"
            ) from exc

        if not settings.VAULT_URL or not settings.VAULT_TOKEN:
            raise RuntimeError(
                "VAULT_URL and VAULT_TOKEN must be set when VAULT_ENABLED=true"
            )

        self._client = hvac.Client(url=settings.VAULT_URL, token=settings.VAULT_TOKEN)
        if not self._client.is_authenticated():
            raise RuntimeError("Vault authentication failed")

        self._mount = settings.VAULT_MOUNT_PATH
        self._prefix = settings.VAULT_PREFIX.rstrip("/")

    def create_session(self, session_id: str):
        # Session marker document
        self._write(
            self._session_meta_path(session_id),
            {
                "created_at": time.time(),
                "session_id": session_id,
            },
        )

    def store(self, session_id: str, token: str, original_value: str, entity_type: str):
        encrypted = b64encode(encrypt_value(original_value)).decode("ascii")
        value_hash = self._hash_value(original_value, entity_type)
        token_hash = self._token_hash(token)

        self._write(
            self._token_path(session_id, token_hash),
            {
                "token": token,
                "value_hash": value_hash,
                "encrypted_value": encrypted,
                "entity_type": entity_type,
                "created_at": time.time(),
                "access_count": 0,
            },
        )

        # Value index for deduplication
        self._write(
            self._value_index_path(session_id, value_hash),
            {"token": token},
        )

    def retrieve(self, session_id: str, token: str) -> Optional[str]:
        token_hash = self._token_hash(token)
        doc = self._read(self._token_path(session_id, token_hash))
        if not doc:
            return None

        access_count = int(doc.get("access_count", 0)) + 1
        doc["access_count"] = access_count
        self._write(self._token_path(session_id, token_hash), doc)

        encrypted_b64 = doc.get("encrypted_value")
        if not encrypted_b64:
            return None

        return decrypt_value(b64decode(encrypted_b64.encode("ascii")))

    def get_token_for_value(self, session_id: str, value: str, entity_type: str) -> Optional[str]:
        value_hash = self._hash_value(value, entity_type)
        doc = self._read(self._value_index_path(session_id, value_hash))
        return doc.get("token") if doc else None

    def destroy_session(self, session_id: str):
        # Vault KV does not support recursive delete in a single call.
        # We best-effort delete metadata marker; token docs expire by TTL policy.
        self._delete(self._session_meta_path(session_id))

    @staticmethod
    def _hash_value(value: str, entity_type: str) -> str:
        return hashlib.sha256(f"{entity_type}:{value}".encode()).hexdigest()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def _session_meta_path(self, session_id: str) -> str:
        return f"{self._prefix}/{session_id}/meta"

    def _token_path(self, session_id: str, token_hash: str) -> str:
        return f"{self._prefix}/{session_id}/tokens/{token_hash}"

    def _value_index_path(self, session_id: str, value_hash: str) -> str:
        return f"{self._prefix}/{session_id}/values/{value_hash}"

    def _write(self, path: str, data: Dict):
        self._client.secrets.kv.v2.create_or_update_secret(
            mount_point=self._mount,
            path=path,
            secret=data,
        )

    def _read(self, path: str) -> Optional[Dict]:
        try:
            res = self._client.secrets.kv.v2.read_secret_version(
                mount_point=self._mount,
                path=path,
            )
            return res.get("data", {}).get("data", {})
        except Exception:
            return None

    def _delete(self, path: str):
        try:
            self._client.secrets.kv.v2.delete_metadata_and_all_versions(
                mount_point=self._mount,
                path=path,
            )
        except Exception:
            return


class MappingStore:
    """
    High-level interface to the mapping backend.
    Backend is selected based on settings.MAPPING_BACKEND.
    """

    def __init__(self):
        if settings.VAULT_ENABLED:
            self._backend = VaultBackend()
        elif settings.MAPPING_BACKEND == MappingBackend.MEMORY:
            self._backend = InMemoryBackend()
        elif settings.MAPPING_BACKEND == MappingBackend.ENCRYPTED_LOCAL:
            self._backend = EncryptedSQLiteBackend()
        elif settings.MAPPING_BACKEND == MappingBackend.REDIS:
            self._backend = RedisBackend()
        else:
            raise ValueError(f"Unknown mapping backend: {settings.MAPPING_BACKEND}")

    def create_session(self, session_id: str):
        self._backend.create_session(session_id)

    def store(self, session_id: str, token: str, original_value: str, entity_type: str):
        self._backend.store(session_id, token, original_value, entity_type)

    def retrieve(self, session_id: str, token: str) -> Optional[str]:
        return self._backend.retrieve(session_id, token)

    def get_token_for_value(self, session_id: str, value: str, entity_type: str) -> Optional[str]:
        return self._backend.get_token_for_value(session_id, value, entity_type)

    def destroy_session(self, session_id: str):
        self._backend.destroy_session(session_id)

    def purge_expired(self, ttl_seconds: int) -> int:
        """Purge expired sessions. Returns number of purged sessions."""
        if hasattr(self._backend, "purge_expired"):
            return self._backend.purge_expired(ttl_seconds)
        return 0
