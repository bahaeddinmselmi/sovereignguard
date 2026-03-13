# Deployment

This guide covers local development, containerized deployment, and production rollout considerations for SovereignGuard.

## Deployment Modes

You can run SovereignGuard in three common modes:

1. Local process with Python and Uvicorn
2. Single-node container deployment with Docker Compose
3. Multi-instance deployment behind a reverse proxy or orchestrator

## Local Development

### 1. Prepare the Environment

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Set at minimum:

```env
TARGET_API_KEY=sk-your-provider-key
TARGET_PROVIDER=openai
TARGET_API_URL=https://api.openai.com
```

### 2. Start the Gateway

```bash
python -m uvicorn sovereignguard.main:app --reload --port 8000
```

### 3. Verify It Is Running

```bash
curl http://localhost:8000/health
```

## Docker Compose

### 1. Prepare `.env`

```bash
copy .env.example .env
```

Recommended minimum production-like values:

```env
TARGET_API_KEY=sk-your-provider-key
GATEWAY_API_KEYS=sg-client-key-1
TARGET_PROVIDER=openai
TARGET_API_URL=https://api.openai.com
MAPPING_BACKEND=local
ENCRYPTION_KEY=replace-me-with-real-secret
```

### 2. Build and Start

```bash
docker compose up --build
```

### 3. Validate

```bash
curl http://localhost:8000/health
curl http://localhost:9090/
```

The second command verifies the Prometheus metrics server if `METRICS_ENABLED=true`.

## Production Deployment Checklist

Before rolling out to production, verify all of the following:

### Security

- `GATEWAY_API_KEYS` configured
- `BYPASS_MASKING=false`
- `DEBUG=false`
- `ALLOWED_ORIGINS` restricted to approved origins
- TLS enabled at the ingress layer
- Provider and gateway keys stored in a secrets manager

### Durability and Storage

- `MAPPING_BACKEND=local` with explicit `ENCRYPTION_KEY` for single-node durability
- or `MAPPING_BACKEND=redis` with reachable `REDIS_URL` for multi-node deployments
- audit log path mounted to persistent storage if logs must survive container rotation

### Operations

- health checks configured against `GET /health`
- metrics scraped if monitoring is required
- log aggregation collects application and audit logs
- alerting thresholds defined for errors, session growth, and latency

## Reverse Proxy Guidance

SovereignGuard is intended to sit behind a trusted reverse proxy or ingress controller.

Recommended responsibilities for the edge layer:

- terminate TLS
- restrict ingress by network policy or IP allowlist
- apply global request limits if needed
- inject standard proxy headers
- route internal app traffic only

## Scaling Guidance

### Single Instance

Use one instance with:

- `MAPPING_BACKEND=memory` for pure ephemeral workflows
- `MAPPING_BACKEND=local` if you need restart durability on the same host

### Multiple Instances

Use multiple instances only with a shared mapping backend:

```env
MAPPING_BACKEND=redis
REDIS_URL=redis://redis:6379/0
```

Without a shared backend, a request could be masked on one instance and restored on another with no matching session state.

### Worker Count

`WORKERS` controls Uvicorn worker count in non-development deployments. Tune it relative to CPU, memory, request body size, and provider latency. More workers are not always better if your requests are large or recognizer coverage is broad.

## Secret Management

Do not commit secrets into the repository.

Recommended secret sources:

- orchestrator secret injection
- CI/CD secret stores
- cloud parameter stores
- container runtime environment injection

At minimum, treat these as secrets:

- `TARGET_API_KEY`
- `GATEWAY_API_KEYS`
- `ENCRYPTION_KEY`
- `REDIS_URL` if it contains credentials

## Upgrade Strategy

When upgrading SovereignGuard:

1. read [CHANGELOG.md](../CHANGELOG.md)
2. deploy to staging with real masking test payloads
3. validate provider-specific response restoration
4. validate metrics and audit log outputs
5. rotate traffic gradually if running multiple instances

## Failure Recovery Notes

### If the Provider Is Down

The gateway will return upstream failure responses. It does not currently queue or retry requests automatically.

### If Redis Is Down

Distributed session restoration will fail. Recovery options:

1. restore Redis
2. temporarily move to single-instance mode with local backend
3. reject traffic until mapping integrity is restored

### If the Encryption Key Is Lost

Encrypted local mappings created under that key cannot be restored. Store the key separately from the application image and back it up in your secrets platform.
