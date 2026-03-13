"""
SovereignGuard Configuration
All settings loaded from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Optional, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MappingBackend(str, Enum):
    MEMORY = "memory"           # Fast, session-only, no persistence
    ENCRYPTED_LOCAL = "local"   # AES-256 encrypted SQLite, persists across restarts
    REDIS = "redis"             # For distributed/multi-instance deployments


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MISTRAL = "mistral"
    CUSTOM = "custom"


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Settings(BaseSettings):
    # ─── Gateway Configuration ─────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # ─── Gateway Authentication ────────────────────────────────────────────
    # Comma-separated list of valid API keys for clients connecting to the gateway
    # If empty, authentication is disabled (development mode only)
    GATEWAY_API_KEYS: List[str] = []

    # ─── Target LLM API ────────────────────────────────────────────────────
    TARGET_API_URL: str = "https://api.openai.com"
    TARGET_API_KEY: str = ""
    TARGET_PROVIDER: LLMProvider = LLMProvider.OPENAI

    # ─── Masking Configuration ─────────────────────────────────────────────
    MAPPING_BACKEND: MappingBackend = MappingBackend.MEMORY
    TOKEN_PREFIX: str = "{{SG_"
    TOKEN_SUFFIX: str = "}}"

    # ─── Encryption (for local encrypted mapping backend) ──────────────────
    ENCRYPTION_KEY: Optional[str] = None  # Auto-generated if not set
    ENCRYPTED_DB_PATH: str = "./data/sg_mapping.db"

    # ─── Redis (for distributed deployments) ───────────────────────────────
    REDIS_URL: Optional[str] = None
    MAPPING_TTL_SECONDS: int = 3600  # 1 hour session TTL

    # ─── Recognizer Configuration ──────────────────────────────────────────
    ENABLED_LOCALES: List[str] = ["universal", "tn", "fr", "ma"]
    CONFIDENCE_THRESHOLD: float = 0.7  # Min confidence to mask an entity

    # ─── Audit & Compliance ────────────────────────────────────────────────
    AUDIT_LOGGING_ENABLED: bool = True
    AUDIT_LOG_PATH: str = "./logs/audit.jsonl"
    LOG_MASKED_PREVIEWS: bool = False

    # ─── Security ──────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = []  # Empty = allow all in dev; set in production
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_RPM: int = 60  # Requests per minute per IP

    # ─── Performance ───────────────────────────────────────────────────────
    MAX_REQUEST_SIZE_MB: int = 10
    REQUEST_TIMEOUT_SECONDS: int = 60

    # ─── Policy Engine (RBAC) ─────────────────────────────────────────────
    POLICY_FILE: Optional[str] = None  # Path to policies.json

    # ─── Smart Router (Local Fallback) ────────────────────────────────────
    LOCAL_LLM_URL: Optional[str] = None  # e.g., http://localhost:11434 (Ollama)
    LOCAL_LLM_MODEL: str = "llama3"
    SENSITIVITY_THRESHOLD: float = 0.90  # Route to local LLM above this
    LOCAL_FALLBACK_ENABLED: bool = False

    # ─── Circuit Breaker ──────────────────────────────────────────────────
    CIRCUIT_BREAKER_ENABLED: bool = True
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RESET_TIMEOUT: int = 60  # seconds

    # ─── HashiCorp Vault ──────────────────────────────────────────────────
    VAULT_ENABLED: bool = False
    VAULT_URL: Optional[str] = None  # e.g., http://127.0.0.1:8200
    VAULT_TOKEN: Optional[str] = None
    VAULT_MOUNT_PATH: str = "secret"
    VAULT_PREFIX: str = "sovereignguard/sessions"

    # ─── Metrics ───────────────────────────────────────────────────────────
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090

    # ─── Development ───────────────────────────────────────────────────────
    DEBUG: bool = False
    LOG_LEVEL: LogLevel = LogLevel.INFO
    BYPASS_MASKING: bool = False  # NEVER set True in production

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @model_validator(mode="after")
    def validate_config(self):
        """Validate configuration constraints on startup."""
        warnings = []

        if not self.TARGET_API_KEY:
            warnings.append(
                "TARGET_API_KEY is not set. Requests to the target LLM will fail."
            )

        if self.MAPPING_BACKEND == MappingBackend.REDIS and not self.REDIS_URL:
            raise ValueError(
                "REDIS_URL must be set when using Redis mapping backend."
            )

        if self.BYPASS_MASKING:
            warnings.append(
                "BYPASS_MASKING is enabled — PII will NOT be protected!"
            )

        if not self.GATEWAY_API_KEYS:
            warnings.append(
                "No GATEWAY_API_KEYS configured — gateway is open to all clients."
            )

        if not self.ALLOWED_ORIGINS:
            warnings.append(
                "No ALLOWED_ORIGINS set — CORS will allow all origins."
            )

        if self.ENCRYPTION_KEY is None and self.MAPPING_BACKEND == MappingBackend.ENCRYPTED_LOCAL:
            warnings.append(
                "ENCRYPTION_KEY not set for encrypted local backend. "
                "A session-scoped key will be generated (lost on restart)."
            )

        for w in warnings:
            logger.warning(f"CONFIG WARNING: {w}")

        return self


settings = Settings()
