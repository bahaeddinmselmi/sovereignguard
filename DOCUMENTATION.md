# SovereignGuard Documentation

SovereignGuard is an open source AI privacy gateway for EMEA data sovereignty workflows. It sits between your application and an external LLM provider, detects personally identifiable information (PII), replaces it with reversible tokens, forwards only tokenized payloads, then restores original values in the model response before returning data to your application.

This file is the consolidated documentation for the project. It combines product overview, architecture, setup, configuration, API reference, operations, security, compliance notes, and extension guidance in one place.

## Proof in 10 Seconds

Input from your app:

```text
"Call Mohamed Ben Ali at +216 98 765 432, CIN 12345678"
```

What the upstream model sees:

```text
"Call {{SG_PERSON_NAME_a3f9b2}} at {{SG_TN_PHONE_c4d5e6}}, {{SG_TN_NATIONAL_ID_f7e3b1}}"
```

What your app receives back:

```text
"Call Mohamed Ben Ali at +216 98 765 432, CIN 12345678"
```

The provider processes tokens, not raw identifiers.

## Table of Contents

1. Overview
2. How It Works
3. Features
4. Quick Start
5. Configuration
6. Architecture
7. API Reference
8. Provider Setup
9. Deployment
10. Operations
11. GDPR and Compliance Notes
12. Security Guidance
13. Extending the System
14. Launch and Adoption Kit
15. Contributing
16. License

## Overview

The purpose of SovereignGuard is to let teams use LLM APIs without sending raw supported PII directly to upstream model providers.

Primary positioning:

- built for EMEA privacy-sensitive AI adoption
- locale-aware recognizers for Tunisia, Morocco, France, and universal patterns
- designed to reduce compliance friction in real customer workflows

At runtime, SovereignGuard:

1. receives an OpenAI-compatible or supported provider request from your app
2. detects supported PII in request text
3. replaces detected values with SG tokens such as `{{SG_EMAIL_a3f9b2c1}}`
4. stores the mapping between the token and the original value locally
5. forwards only the tokenized payload to the upstream provider
6. restores the original values after the provider responds
7. returns the restored response to the caller

This creates a clear technical boundary around sensitive prompt data.

## Demo-First Quick Pitch

If you are presenting SovereignGuard to leadership, legal, or non-developer stakeholders, lead with this sequence:

1. show raw prompt with PII
2. show tokenized payload sent upstream
3. show restored response returned to the app

The architecture matters, but the mask-forward-restore proof is the core product moment.

## How It Works

```text
Client Application
  |
  |  OpenAI-compatible request
  v
SovereignGuard Gateway
  |
  |-- authentication
  |-- rate limiting
  |-- request size enforcement
  |-- request ID propagation
  |-- PII detection
  |-- tokenization
  |-- local mapping storage
  v
External LLM Provider
  |
  |-- receives SG tokens instead of raw identifiers
  v
SovereignGuard Gateway
  |
  |-- response parsing
  |-- token restoration
  |-- session cleanup
  v
Client Application
```

## Features

### Security and Privacy Controls

- gateway API key authentication
- per-IP rate limiting
- request size enforcement
- request correlation IDs
- structured logging
- tamper-evident immutable audit logging (hash-chained entries)
- fail-closed circuit breaker for masking/encryption failures
- minimal public health endpoint
- protected audit and admin endpoints
- session TTL cleanup daemon
- OpenAI-compatible error responses
- optional encrypted local mapping storage

### Advanced Gateway Controls

- semantic token restoration for LLM token reformatting and paraphrasing
- async masking pipeline (fast regex path + heavy recognizer path)
- policy engine for role-based masking behavior (RBAC-ready)
- sensitivity-aware smart routing for local fallback model flows
- streaming response restoration with chunk boundary handling

### Provider Support

- OpenAI-compatible APIs
- Anthropic response restoration support
- Mistral through OpenAI-compatible response handling
- custom OpenAI-compatible providers

### Mapping Backends

- `memory`
- `local` encrypted SQLite
- `redis`
- `vault` HashiCorp Vault KV v2

### Built-in Recognizers

| Type | Universal | Tunisia | France | Morocco |
|------|-----------|---------|--------|---------|
| Email | Yes | Yes | Yes | Yes |
| Phone | Yes | Yes | Yes | Yes |
| National ID | No | Yes | Yes | Yes |
| Company ID | No | Yes | Yes | Yes |
| IBAN | Yes | Yes | Yes | Yes |
| Credit card | Yes | Yes | Yes | Yes |
| IP address | Yes | Yes | Yes | Yes |
| Address | No | Yes | Yes | No |
| Person name | Yes | Context-aware | Context-aware | Context-aware |
| Date of birth | Yes | Context-aware | Context-aware | Context-aware |

Recognizer logic is regex and heuristic based. You should validate it against real data samples before production use.

## Quick Start

### Docker

```bash
git clone https://github.com/sovereignguard/sovereignguard
cd sovereignguard
copy .env.example .env
```

Edit `.env` and set at minimum:

```env
TARGET_API_KEY=sk-your-provider-key
GATEWAY_API_KEYS=sg-client-key-1
TARGET_PROVIDER=openai
TARGET_API_URL=https://api.openai.com
```

Then run:

```bash
docker compose up --build
```

The gateway will be available on `http://localhost:8000`.

### Python

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn sovereignguard.main:app --reload --port 8000
```

### Smoke Test

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"healthy","gateway":"SovereignGuard","version":"0.2.0"}
```

### OpenAI SDK Example

```python
from openai import OpenAI

client = OpenAI(
    api_key="sg-client-key-1",
    base_url="http://localhost:8000/v1",
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "user",
            "content": "Contact Mohamed Ben Ali at mohamed@example.com and +216 98 765 432.",
        }
    ],
)

print(response.choices[0].message.content)
```

## Configuration

SovereignGuard loads settings from environment variables via Pydantic settings.

Configuration sources are:

1. process environment variables
2. `.env` file in the repository root
3. defaults in `sovereignguard/config.py`

### Provider Settings

| Variable | Required | Description |
|----------|----------|-------------|
| `TARGET_API_URL` | Yes | Base URL of the upstream model provider |
| `TARGET_API_KEY` | Yes in real usage | Credential used by the gateway when forwarding requests |
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

If this is empty, the gateway allows unauthenticated requests. That is acceptable only for local development or tightly isolated test environments.

### Mapping Storage

| Variable | Required | Description |
|----------|----------|-------------|
| `MAPPING_BACKEND` | Yes | `memory`, `local`, or `redis` (or set `VAULT_ENABLED=true`) |
| `MAPPING_TTL_SECONDS` | Yes | Session expiration window |
| `ENCRYPTION_KEY` | Required for durable local storage | Key used to encrypt stored values |
| `ENCRYPTED_DB_PATH` | For `local` backend | Path to the SQLite file |
| `REDIS_URL` | Required for `redis` backend | Redis connection URL |
| `VAULT_ENABLED` | Optional | Enables HashiCorp Vault storage backend |
| `VAULT_URL` | Required when Vault enabled | Vault API base URL |
| `VAULT_TOKEN` | Required when Vault enabled | Vault auth token |
| `VAULT_MOUNT_PATH` | Vault only | KV mount path (for example `secret`) |
| `VAULT_PREFIX` | Vault only | Path prefix for session/token documents |

Backend selection guidance:

- `memory`: non-persistent, simple, good for local development and single-node ephemeral flows
- `local`: persistent encrypted local storage for single-node production
- `redis`: shared backend for multi-instance production
- `vault`: external secret vault for high-assurance environments

### Detection and Masking

| Variable | Description |
|----------|-------------|
| `ENABLED_LOCALES` | Comma-separated recognizer locales to load |
| `CONFIDENCE_THRESHOLD` | Minimum recognizer score required to mask |
| `BYPASS_MASKING` | Disables masking entirely; for local debugging only |

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
| `CIRCUIT_BREAKER_ENABLED` | Enables fail-closed circuit breaker |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Consecutive failures before breaker opens |
| `CIRCUIT_BREAKER_RESET_TIMEOUT` | Seconds before half-open recovery attempt |

### Policy and Sovereign Routing

| Variable | Description |
|----------|-------------|
| `POLICY_FILE` | Path to policy JSON file for RBAC masking behavior |
| `LOCAL_FALLBACK_ENABLED` | Enables sensitivity-based local model fallback |
| `LOCAL_LLM_URL` | Base URL of local LLM endpoint |
| `LOCAL_LLM_MODEL` | Default local model identifier |
| `SENSITIVITY_THRESHOLD` | Routing threshold for high-sensitivity prompts |

### Runtime and Observability

| Variable | Description |
|----------|-------------|
| `WORKERS` | Uvicorn worker count |
| `REQUEST_TIMEOUT_SECONDS` | Timeout for upstream provider requests |
| `METRICS_ENABLED` | Starts the Prometheus metrics server |
| `METRICS_PORT` | Port for metrics exposure |
| `AUDIT_LOGGING_ENABLED` | Enables audit log writes |
| `AUDIT_LOG_PATH` | JSONL audit log path |
| `DEBUG` | Enables docs and development behavior |
| `LOG_LEVEL` | `debug`, `info`, `warning`, `error` |

### Recommended Development Config

```env
TARGET_PROVIDER=openai
TARGET_API_URL=https://api.openai.com
TARGET_API_KEY=sk-dev-key
GATEWAY_API_KEYS=
MAPPING_BACKEND=memory
DEBUG=true
BYPASS_MASKING=false
```

### Recommended Single-Node Production Config

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

### Recommended Multi-Instance Production Config

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

### Validation Behavior

The gateway validates several combinations on startup:

- `REDIS_URL` must be set when `MAPPING_BACKEND=redis`
- missing `TARGET_API_KEY` triggers a warning because forwarding will fail
- missing `GATEWAY_API_KEYS` triggers a warning because the gateway is open
- missing `ALLOWED_ORIGINS` triggers a warning because CORS becomes permissive
- using `MAPPING_BACKEND=local` without `ENCRYPTION_KEY` triggers a warning because auto-generated keys are not durable across restarts

### Common Misconfigurations

#### The Gateway Starts but Provider Calls Fail

Likely causes:

- `TARGET_API_KEY` missing or invalid
- `TARGET_API_URL` points to the wrong provider
- `TARGET_PROVIDER` does not match the actual upstream response format

#### Responses Contain Tokens Instead of Restored Values

Likely causes:

- session expired too early
- wrong shared backend in a multi-instance deployment
- provider-specific format mismatch

#### Everything Returns 401

Likely causes:

- client is using the provider API key instead of a gateway API key
- `Authorization` header is missing the `Bearer` prefix
- `GATEWAY_API_KEYS` contains whitespace or malformed comma-separated values

## Architecture

SovereignGuard is a FastAPI-based privacy gateway that exposes OpenAI-style endpoints while enforcing local masking, reversible token mapping, and response restoration.

### Request Pipeline

1. request enters the FastAPI application
2. middleware enforces authentication, rate limiting, request size checks, and request ID propagation
3. a masking session is created
4. recognizers scan request text and return `RecognizerResult` objects
5. overlapping detections are resolved by confidence and locale priority
6. detected values are replaced with SG tokens and stored in the mapping backend
7. the tokenized payload is forwarded upstream with the gateway provider key
8. the provider response is parsed through an adapter layer
9. SG tokens are restored to original values
10. the session is destroyed or later cleaned up by TTL expiration

### Main Components

#### Configuration Layer

Responsibilities:

- load runtime settings
- validate configuration combinations
- expose provider, mapping, and security settings to the application

#### Middleware Layer

Responsibilities:

- authenticate clients
- enforce rate limiting
- reject oversized requests
- attach request IDs for tracing

#### Proxy Layer

Responsibilities:

- expose OpenAI-compatible endpoints
- normalize request handling
- forward provider calls
- restore provider responses

#### Recognizer Layer

Responsibilities:

- detect PII in plain text
- provide universal and locale-aware coverage
- return precise offsets into the original text

#### Engine Layer

Responsibilities:

- orchestrate masking and restoration
- manage session-scoped mappings
- encrypt and store original values
- resolve overlaps and deduplicate values

#### Audit and Metrics Layer

Responsibilities:

- write JSONL audit logs without raw PII
- expose Prometheus metrics
- generate aggregate audit reports

### Storage Model

#### In-Memory Backend

- fastest option
- no disk persistence
- state lost on process restart
- suited to development and ephemeral workloads

#### Encrypted SQLite Backend

- persistent local storage
- values encrypted before being written
- good for single-node durable deployments

#### Redis Backend

- shared state across instances
- required for horizontal scaling
- TTL-based expiration built in

### Security Invariants

1. raw PII should not cross the provider boundary when masking is enabled
2. raw PII should never be written to audit logs
3. token maps must be session-isolated
4. public operational endpoints should expose minimal information
5. provider credentials should be held by the gateway, not supplied by clients

### Failure Modes and Tradeoffs

#### Recognizer Coverage Is Heuristic

The system favors explicit and inspectable recognizer logic over opaque NLP dependencies. Coverage is only as strong as the recognizers you enable and validate.

#### Token Restoration Depends on Session Availability

If the session expires too early or the wrong backend is used in a multi-instance deployment, restoration may fail and tokens may remain in the output.

#### Provider Format Drift Must Be Managed

If an upstream provider changes its schema, the adapter layer may need updates before restoration continues to work correctly.

## API Reference

Unless otherwise noted, endpoints require:

```http
Authorization: Bearer <gateway-api-key>
```

### Success and Error Conventions

Model endpoints generally return the same schema shape as the upstream provider.

Gateway-generated errors use an OpenAI-style envelope:

```json
{
  "error": {
    "message": "Internal gateway error. Check logs for details.",
    "type": "server_error",
    "code": "internal_error"
  }
}
```

### `GET /health`

Minimal unauthenticated health endpoint.

Example response:

```json
{
  "status": "healthy",
  "gateway": "SovereignGuard",
  "version": "0.2.0"
}
```

### `POST /v1/chat/completions`

Behavior:

1. validates request JSON
2. creates a masking session
3. masks text in `messages`
4. forwards tokenized content to the configured provider
5. restores tokens in the provider response
6. ends the session

Example request:

```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {
      "role": "user",
      "content": "Email user@example.com and call +216 98 765 432."
    }
  ]
}
```

Notes:

- multipart message content with text blocks is supported
- streaming mode is supported
- masking only applies to text-bearing fields the handler understands

### `POST /v1/completions`

Legacy completion endpoint.

Behavior:

- masks `prompt`
- restores `choices[].text`

### `POST /v1/embeddings`

Embeddings endpoint.

Behavior:

- masks `input` if it is a string
- forwards the request upstream
- embedding vectors themselves do not require restoration

### `GET /v1/models`

Pass-through model listing endpoint.

### `GET /audit/report`

Returns aggregate audit information without exposing raw PII.

Query parameters:

- `start_date`: optional, `YYYY-MM-DD`
- `end_date`: optional, `YYYY-MM-DD`

Validation rules:

- invalid date formats return `400`
- endpoint is protected by gateway authentication middleware

### `GET /admin/stats`

Returns operational metadata such as:

- loaded recognizer count
- masking enabled status
- configured backend
- configured provider
- enabled locales
- rate limiting status

### `DELETE /admin/sessions/{session_id}`

Force-clears a session mapping namespace.

Example response:

```json
{
  "status": "destroyed",
  "session_id": "abc-123"
}
```

### Common Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `400` | Invalid request payload or invalid parameters |
| `401` | Missing or invalid gateway API key |
| `413` | Request body too large |
| `429` | Rate limit exceeded |
| `500` | Internal gateway or upstream failure |

### Gateway Response Headers

The gateway adds:

- `X-Request-ID`
- `X-Process-Time-Ms`
- `X-Powered-By`
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`

It also adds security headers such as `X-Content-Type-Options`, `X-Frame-Options`, and `Strict-Transport-Security`.

## Provider Setup

Response restoration depends on the gateway understanding the upstream provider response format correctly.

### Provider Selection

```env
TARGET_PROVIDER=openai
TARGET_API_URL=https://api.openai.com
```

Supported values:

- `openai`
- `anthropic`
- `mistral`
- `custom`

### Adapter Responsibilities

Provider adapters:

1. locate text fields inside provider responses
2. locate text deltas inside streaming chunks
3. write restored values back into the correct schema

If `TARGET_PROVIDER` does not match the real response schema, the request may succeed but restoration may leave `{{SG_*}}` tokens in the final response.

### OpenAI

Recommended settings:

```env
TARGET_PROVIDER=openai
TARGET_API_URL=https://api.openai.com
```

Handled response fields:

- chat: `choices[].message.content`
- completions: `choices[].text`
- streaming: `choices[].delta.content`

Use this mode for OpenAI and other endpoints that truly expose the same response structure.

### Anthropic

Recommended settings:

```env
TARGET_PROVIDER=anthropic
TARGET_API_URL=https://api.anthropic.com
```

Handled response fields:

- content blocks: `content[].text`
- streaming text deltas: `content_block_delta` with `delta.text`

Validation checklist:

1. send a request containing a maskable value
2. confirm the upstream provider receives SG tokens, not raw identifiers
3. confirm the final response contains restored values, not tokens
4. repeat in streaming mode if streaming is used in production

### Mistral

Recommended settings:

```env
TARGET_PROVIDER=mistral
TARGET_API_URL=https://api.mistral.ai
```

Current behavior uses the OpenAI adapter because Mistral commonly exposes an OpenAI-compatible response structure. Validate against your specific endpoint version.

### Custom Providers

If the upstream provider exposes an OpenAI-compatible schema:

```env
TARGET_PROVIDER=custom
TARGET_API_URL=https://your-provider.example.com
```

If the response shape is materially different, add a dedicated adapter instead of forcing compatibility in client code.

### Provider Validation Checklist

1. standard response restoration works
2. streaming restoration works
3. provider errors surface cleanly
4. multipart text content is masked before forwarding
5. long prompts and multi-entity prompts restore reliably

## Deployment

You can run SovereignGuard in three common modes:

1. local process with Python and Uvicorn
2. single-node container deployment with Docker Compose
3. multi-instance deployment behind a reverse proxy or orchestrator

### Local Development Deployment

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn sovereignguard.main:app --reload --port 8000
```

### Docker Compose Deployment

Prepare `.env` with at least:

```env
TARGET_API_KEY=sk-your-provider-key
GATEWAY_API_KEYS=sg-client-key-1
TARGET_PROVIDER=openai
TARGET_API_URL=https://api.openai.com
MAPPING_BACKEND=local
ENCRYPTION_KEY=replace-me-with-real-secret
```

Start it:

```bash
docker compose up --build
```

Validate:

```bash
curl http://localhost:8000/health
curl http://localhost:9090/
```

### Production Checklist

#### Security

- `GATEWAY_API_KEYS` configured
- `BYPASS_MASKING=false`
- `DEBUG=false`
- `ALLOWED_ORIGINS` restricted
- TLS enabled at the ingress layer
- provider and gateway keys stored in a secrets manager

#### Durability and Storage

- use `MAPPING_BACKEND=local` with explicit `ENCRYPTION_KEY` for single-node durability
- or use `MAPPING_BACKEND=redis` with reachable `REDIS_URL` for multi-node deployments
- mount audit log paths to persistent storage if needed

#### Operations

- configure `GET /health` health checks
- scrape metrics if monitoring is required
- collect application and audit logs centrally
- define alert thresholds for errors, session growth, and latency

### Reverse Proxy Guidance

The gateway is intended to sit behind a trusted reverse proxy or ingress controller.

Recommended edge responsibilities:

- terminate TLS
- restrict ingress by network policy or IP allowlist
- apply additional global request limits if needed
- inject standard proxy headers
- route internal app traffic only

### Scaling Guidance

#### Single Instance

Use:

- `MAPPING_BACKEND=memory` for ephemeral workflows
- `MAPPING_BACKEND=local` for single-node durability

#### Multiple Instances

Use a shared backend:

```env
MAPPING_BACKEND=redis
REDIS_URL=redis://redis:6379/0
```

Without a shared backend, masking may happen on one instance while restoration is attempted on another with no matching session state.

### Secret Management

Do not commit secrets into the repository.

Treat these as secrets at minimum:

- `TARGET_API_KEY`
- `GATEWAY_API_KEYS`
- `ENCRYPTION_KEY`
- `REDIS_URL` if it contains credentials

### Upgrade Strategy

1. read `CHANGELOG.md`
2. deploy to staging with real masking test payloads
3. validate provider-specific restoration
4. validate metrics and audit output
5. roll traffic gradually if running multiple instances

## Operations

### Startup Checklist

Before production rollout, verify:

- `TARGET_API_KEY` is valid
- `GATEWAY_API_KEYS` is configured
- `ENCRYPTION_KEY` is explicitly set when needed
- `ALLOWED_ORIGINS` is restricted
- `BYPASS_MASKING` is `false`
- `DEBUG` is `false`
- TLS termination is configured
- audit log directory is writable and rotated

### Health Check

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"healthy","gateway":"SovereignGuard","version":"0.2.0"}
```

### Monitoring

#### Prometheus Metrics

Metrics are exposed on `METRICS_PORT` when enabled.

| Metric | Type | Description |
|--------|------|-------------|
| `sovereignguard_requests_total` | Counter | Total proxy requests labeled by status |
| `sovereignguard_entities_masked_total` | Counter | Total PII entities masked by type |
| `sovereignguard_tokens_restored_total` | Counter | Total restored tokens |
| `sovereignguard_request_duration_seconds` | Histogram | Request processing latency |
| `sovereignguard_active_sessions` | Gauge | Currently active masking sessions |

#### Useful Alerts

- `sovereignguard_active_sessions > 100` suggests a possible session leak
- a sustained error-rate increase suggests upstream or internal failures
- high request duration suggests latency degradation or overload

#### Structured Logs

In production, logs are JSON-formatted via structlog and include contextual fields such as provider, event type, and request IDs.

### Troubleshooting

#### High Memory Usage

Possible cause: session mappings are not being cleaned up.

Actions:

1. verify the session cleanup daemon is running
2. reduce `MAPPING_TTL_SECONDS`
3. monitor `sovereignguard_active_sessions`

#### High Latency

Possible cause: too many recognizers, large payloads, or slow upstreams.

Actions:

1. reduce `ENABLED_LOCALES` to the minimum required set
2. verify `MAX_REQUEST_SIZE_MB`
3. monitor request duration metrics

#### Token Restoration Failures

Possible cause: session expired too early or provider formatting drift.

Actions:

1. increase `MAPPING_TTL_SECONDS` if requests are long-lived
2. check audit logs for `tokens_not_found`
3. verify provider adapter settings

#### Redis Connection Failures

Possible cause: bad `REDIS_URL` or unavailable Redis.

Actions:

1. verify connectivity and credentials
2. fall back to single-instance mode if necessary

#### Authentication Failures

Possible cause: wrong client key or malformed `Authorization` header.

Actions:

1. verify `GATEWAY_API_KEYS`
2. ensure `Authorization: Bearer <key>` is present
3. check for whitespace or formatting issues in env vars

### Backup and Recovery

#### Audit Logs

- stored at `AUDIT_LOG_PATH`
- should be rotated and archived according to retention requirements

#### Encrypted SQLite Backend

- stored at `ENCRYPTED_DB_PATH`
- depends on the `ENCRYPTION_KEY`
- if the key is lost, encrypted mappings cannot be recovered

#### Redis Backend

- standard Redis backup policies apply
- TTL handles cleanup automatically

## GDPR and Compliance Notes

SovereignGuard is a technical control that supports privacy and compliance programs. It is not legal advice and does not by itself establish a lawful basis for processing.

### What It Helps With

It helps organizations:

1. minimize outbound transfer of raw personal data
2. reduce directly identifying content sent to third-party APIs
3. keep restoration mappings inside infrastructure they control
4. maintain auditable masking and restoration records without raw values

### Controls Provided

#### Data Minimization

When masking is enabled, the provider receives tokens instead of supported raw identifiers.

#### Local Restoration Boundary

Original values remain in the local mapping store and are restored only after the provider response returns.

#### Auditability

Audit logs record masking counts, restoration counts, and session events without logging raw PII.

#### Scoped Session Isolation

Mappings are session-isolated to reduce cross-request leakage.

### What It Does Not Solve

You still need:

- a lawful basis for processing
- vendor review and contractual controls
- retention policy enforcement at the provider side
- output review for generated personal data
- validation for all domain-specific sensitive data classes

### Residual Risks

#### Recognizer Misses

If a recognizer does not match a value, that value may still leave your environment in plain text.

Mitigations:

- validate recognizers against real data
- add domain-specific custom recognizers
- tune locale and confidence settings

#### Indirect Identification Through Context

Even if direct identifiers are masked, surrounding context may still make a person identifiable.

Mitigations:

- redact more contextual fields upstream
- minimize prompt contents
- create use-case-specific policies for sensitive workflows

#### Operational Misconfiguration

Examples:

- `BYPASS_MASKING=true`
- no gateway authentication
- permissive CORS in production
- wrong backend in multi-instance deployments

Mitigations:

- enforce production policy through infrastructure configuration
- validate in staging
- monitor startup warnings and audit events

### Recommended Governance Controls Around the Gateway

1. DPIA or equivalent privacy review
2. vendor due diligence and contract review
3. access controls around prompt sources
4. key rotation and secret management
5. incident response procedures for masking failures
6. retention limits for logs and mapping backends

## Security Guidance

### Supported Versions

| Version | Supported |
|---------|-----------|
| 0.2.x | Yes |
| below 0.2 | No |

### Reporting a Vulnerability

Do not open a public issue for security vulnerabilities.

Recommended reporting content:

1. vulnerability description
2. reproduction steps
3. potential impact
4. suggested fix if available

### Mandatory Production Practices

1. set `GATEWAY_API_KEYS`
2. set an explicit `ENCRYPTION_KEY`
3. restrict `ALLOWED_ORIGINS`
4. do not commit `TARGET_API_KEY`
5. use HTTPS behind a trusted reverse proxy
6. keep `BYPASS_MASKING=false`

### Recommended Additional Practices

- enable rate limiting
- use encrypted local or Redis mapping storage
- rotate `ENCRYPTION_KEY` periodically
- monitor audit logs and metrics
- keep dependencies updated

### Threat Model

#### What SovereignGuard Protects Against

- PII leaking to third-party LLM providers
- accidental PII exposure in logs and metrics
- unauthorized access to the gateway when authentication is configured

#### What It Does Not Protect Against

- compromised host infrastructure
- side-channel attacks on the host machine
- PII embedded in images or binary payloads
- adversarial inputs that evade regex-based detection

### Known Limitations

- person name detection is heuristic, not NLP-based
- date of birth detection depends on contextual keywords
- in-memory backend loses state on restart
- auto-generated encryption keys are session-scoped and not suitable for durable production storage

### Key Rotation

#### Rotating the Encryption Key

1. generate a new key
2. update `ENCRYPTION_KEY`
3. restart the gateway
4. note that old encrypted local mappings cannot be recovered under the new key

Example generation command:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### Rotating Gateway API Keys

1. add the new key to `GATEWAY_API_KEYS`
2. restart the gateway
3. migrate clients
4. remove the old key
5. restart again

## Extending the System

Recognizers are the main extension point for PII coverage.

### Recognizer Contract

All recognizers inherit from `BaseRecognizer` and must provide:

1. `entity_types`
2. `locale`
3. `priority`
4. `analyze(text)`

Each `RecognizerResult` includes:

- `entity_type`
- `start`
- `end`
- `score`
- `text`
- `locale`

### Where to Put New Recognizers

#### Universal

Use `sovereignguard/recognizers/universal/` for patterns that are not country-specific.

#### Locale-Specific

Use `sovereignguard/recognizers/<locale>/` when formats or language are local.

### Example Recognizer Skeleton

```python
from typing import List

from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class PassportRecognizer(BaseRecognizer):
    @property
    def entity_types(self) -> List[str]:
        return ["PASSPORT"]

    @property
    def locale(self) -> str:
        return "universal"

    @property
    def priority(self) -> int:
        return 50

    def analyze(self, text: str) -> List[RecognizerResult]:
        return self._regex_analyze(
            text,
            [
                (r"\b[A-Z]{2}\d{7}\b", "PASSPORT", 0.85),
            ],
        )
```

### Workflow

1. create the recognizer module
2. implement the recognizer
3. register it in `sovereignguard/recognizers/registry.py`
4. add unit tests
5. validate end-to-end masking and restoration

### Design Guidelines

- prefer precision over recall
- use context for ambiguous values
- keep offsets correct relative to the original input
- give locale-specific recognizers appropriate priority
- never log raw PII

### Common Mistakes

1. broad patterns that over-match normal business text
2. context-free date or number matching
3. forgetting registry registration
4. missing negative tests
5. incorrect offsets due to text mutation before match calculation

### Adding a New Provider Adapter

To support a new provider:

1. create an adapter class inheriting from `BaseProviderAdapter`
2. implement text extraction and streaming delta extraction
3. register it in `get_provider_adapter()`
4. add adapter tests
5. validate end-to-end masking and restoration

## Launch and Adoption Kit

If you are preparing a public launch, use the dedicated launch playbook:

- [docs/launch-kit.md](docs/launch-kit.md)

It includes:

1. a 60-second demo script
2. a copy-paste command sequence for recording
3. LinkedIn post templates
4. launch-day distribution checklist
5. post-launch metrics and security hygiene checks

## Contributing

### Development Setup

```bash
git clone https://github.com/your-org/sovereignguard.git
cd sovereignguard
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Running Tests

```bash
make test
make test-cov
pytest tests/test_masker.py -v
```

### Running the Gateway Locally

```bash
copy .env.example .env
make dev
```

### Contribution Expectations

1. create a feature branch
2. add tests for new functionality
3. run the full test suite
4. keep changes focused and documented
5. update `CHANGELOG.md` for user-facing changes when appropriate

### Code Style

- follow PEP 8
- use type hints for public function signatures
- keep functions focused
- use descriptive variable names

### Security Rules for Contributors

- never log actual PII values
- never weaken production authentication by default
- review security-sensitive changes carefully
- report vulnerabilities privately rather than publicly

## License

SovereignGuard is distributed under the Business Source License 1.1. See `LICENSE` for the full terms.
