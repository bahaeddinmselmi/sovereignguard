# Configuration

This document describes the runtime configuration model for SovereignGuard and explains how to choose values for development, staging, and production.

## Configuration Sources

SovereignGuard loads configuration from environment variables using Pydantic settings.

Primary source order:

1. Process environment variables
2. `.env` file in the project root
3. Code defaults defined in [sovereignguard/config.py](../sovereignguard/config.py)

Startup validation runs automatically and will either raise hard errors for invalid combinations or emit warnings for unsafe but technically runnable configurations.

## Core Settings

### Provider Settings

| Variable | Required | Description |
|----------|----------|-------------|
| `TARGET_API_URL` | Yes | Base URL of the upstream model provider |
| `TARGET_API_KEY` | Yes in real usage | Credential used by SovereignGuard when forwarding requests |
| `TARGET_PROVIDER` | Yes | `openai`, `anthropic`, `mistral`, or `custom` |

Example:

```env
TARGET_PROVIDER=openai
TARGET_API_URL=https://api.openai.com
TARGET_API_KEY=sk-...
```

### Gateway Authentication

| Variable | Required | Description |
|----------|----------|-------------|
| `GATEWAY_API_KEYS` | Strongly recommended | Comma-separated client API keys accepted by the gateway |

Example:

```env
GATEWAY_API_KEYS=sg-prod-key-1,sg-prod-key-2
```

If this value is empty, the gateway allows unauthenticated requests. That is acceptable only for local development or tightly isolated testing.

### Mapping Storage

| Variable | Required | Description |
|----------|----------|-------------|
| `MAPPING_BACKEND` | Yes | `memory`, `local`, or `redis` (or set `VAULT_ENABLED=true`) |
| `MAPPING_TTL_SECONDS` | Yes | Session expiration window |
| `ENCRYPTION_KEY` | Required for durable local storage | Key used to encrypt stored values |
| `ENCRYPTED_DB_PATH` | For `local` backend | Path to the SQLite file |
| `REDIS_URL` | Required for `redis` backend | Redis connection URL |
| `VAULT_ENABLED` | Optional | Enables HashiCorp Vault mapping backend |
| `VAULT_URL` | Required when Vault enabled | Vault API base URL |
| `VAULT_TOKEN` | Required when Vault enabled | Vault access token |
| `VAULT_MOUNT_PATH` | Vault only | KV mount path (for example `secret`) |
| `VAULT_PREFIX` | Vault only | Prefix for session/token documents |

Backend selection guidance:

- `memory`: simplest, non-persistent, good for development and single-node short-lived requests
- `local`: persistent encrypted storage on disk, suitable for single-node production with local durability requirements
- `redis`: required for horizontally scaled or shared-session environments
- `vault`: high-assurance secret storage for regulated environments

### Detection and Masking

| Variable | Description |
|----------|-------------|
| `ENABLED_LOCALES` | Comma-separated recognizer locales to load |
| `CONFIDENCE_THRESHOLD` | Minimum recognizer score required to mask a match |
| `BYPASS_MASKING` | Completely disables masking; use only for local debugging |

Example:

```env
ENABLED_LOCALES=universal,tn,fr,ma
CONFIDENCE_THRESHOLD=0.7
BYPASS_MASKING=false
```

### Security and Traffic Control

| Variable | Description |
|----------|-------------|
| `ALLOWED_ORIGINS` | Browser origin allowlist for CORS |
| `RATE_LIMIT_ENABLED` | Enables per-IP rate limiting |
| `RATE_LIMIT_RPM` | Requests per minute per client IP |
| `MAX_REQUEST_SIZE_MB` | Reject requests larger than this size |
| `CIRCUIT_BREAKER_ENABLED` | Enables fail-closed masking/encryption circuit breaker |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Number of failures before opening breaker |
| `CIRCUIT_BREAKER_RESET_TIMEOUT` | Seconds before half-open recovery trial |

### Policy and Sovereign Routing

| Variable | Description |
|----------|-------------|
| `POLICY_FILE` | Path to role-based masking policy JSON file |
| `LOCAL_FALLBACK_ENABLED` | Enable local fallback for high-sensitivity prompts |
| `LOCAL_LLM_URL` | Local model endpoint URL (for example Ollama) |
| `LOCAL_LLM_MODEL` | Default local model name |
| `SENSITIVITY_THRESHOLD` | Threshold used by smart router |

### Runtime and Observability

| Variable | Description |
|----------|-------------|
| `WORKERS` | Uvicorn worker count |
| `REQUEST_TIMEOUT_SECONDS` | Timeout for upstream provider requests |
| `METRICS_ENABLED` | Starts the Prometheus metrics server |
| `METRICS_PORT` | Port for metrics exposure |
| `AUDIT_LOGGING_ENABLED` | Enables audit log writes |
| `AUDIT_LOG_PATH` | JSONL audit log path |
| `DEBUG` | Enables docs and development-oriented behavior |
| `LOG_LEVEL` | `debug`, `info`, `warning`, `error` |

## Recommended Configurations

### Local Development

```env
TARGET_PROVIDER=openai
TARGET_API_URL=https://api.openai.com
TARGET_API_KEY=sk-dev-key
GATEWAY_API_KEYS=
MAPPING_BACKEND=memory
DEBUG=true
BYPASS_MASKING=false
```

### Single-Node Production

```env
TARGET_PROVIDER=openai
TARGET_API_URL=https://api.openai.com
TARGET_API_KEY=sk-prod-key
GATEWAY_API_KEYS=sg-prod-client-key
MAPPING_BACKEND=local
ENCRYPTION_KEY=replace-me-with-strong-secret
ENCRYPTED_DB_PATH=./data/sg_mapping.db
ALLOWED_ORIGINS=https://app.example.com
RATE_LIMIT_ENABLED=true
RATE_LIMIT_RPM=60
DEBUG=false
```

### Multi-Instance Production

```env
TARGET_PROVIDER=anthropic
TARGET_API_URL=https://api.anthropic.com
TARGET_API_KEY=sk-ant-...
GATEWAY_API_KEYS=sg-prod-client-key
MAPPING_BACKEND=redis
REDIS_URL=redis://redis:6379/0
MAPPING_TTL_SECONDS=3600
ALLOWED_ORIGINS=https://app.example.com
RATE_LIMIT_ENABLED=true
DEBUG=false
```

## Validation Behavior

SovereignGuard validates a few critical combinations on startup:

- `REDIS_URL` must be set when `MAPPING_BACKEND=redis`
- `VAULT_URL` and `VAULT_TOKEN` must be set when `VAULT_ENABLED=true`
- Missing `TARGET_API_KEY` generates a startup warning because forwarding will fail
- Missing `GATEWAY_API_KEYS` generates a warning because the gateway is open
- Missing `ALLOWED_ORIGINS` generates a warning because CORS falls back to permissive behavior
- Using `MAPPING_BACKEND=local` without `ENCRYPTION_KEY` generates a warning because auto-generated keys are not durable across restarts

## Key Management Guidance

### Encryption Key

Generate a strong key and inject it through your secrets platform.

Example generation command:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Do not rely on the auto-generated fallback key in production. If the process restarts, previously encrypted local mappings become unrecoverable.

### Gateway API Keys

Treat client gateway keys like service credentials:

1. Store them in a secrets manager.
2. Rotate them periodically.
3. Support a short overlap window during rotation.
4. Audit which internal apps receive which keys.

## Common Misconfigurations

### The Gateway Starts but All Provider Calls Fail

Likely causes:

- `TARGET_API_KEY` missing or invalid
- `TARGET_API_URL` points to the wrong provider
- `TARGET_PROVIDER` does not match the actual upstream response format

### Responses Contain Tokens Instead of Restored Values

Likely causes:

- Session expired too early
- Wrong shared backend in a multi-instance deployment
- Provider-specific format mismatch

### Everything Returns 401

Likely causes:

- Client is using the provider API key instead of a gateway API key
- `Authorization` header is missing the `Bearer` prefix
- `GATEWAY_API_KEYS` contains whitespace or malformed comma-separated values