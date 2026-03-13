# SovereignGuard

SovereignGuard is an open source AI privacy gateway that sits between your application and an external LLM provider, detects personally identifiable information, replaces it with reversible tokens, forwards only the tokenized payload, then restores the original values in the model response before returning data to your app.

The goal is simple: let teams ship LLM features without sending raw customer PII to OpenAI, Anthropic, Mistral, or any other upstream model API.

Built with an EMEA-first data sovereignty mindset, including locale-aware recognizers for Tunisia, Morocco, and France.

## Proof in 10 Seconds

Input from your app:

```text
"Call baha at xxx, CIN 12345678"
```

What upstream receives:

```text
"Call {{SG_PERSON_NAME_a3f9b2}} at {{SG_TN_PHONE_c4d5e6}}, {{SG_TN_NATIONAL_ID_f7e3b1}}"
```

What your app gets back:

```text
"Call baha at xxx, CIN 12345678"
```

## Full Documentation

The consolidated single-file documentation is available at [DOCUMENTATION.md](DOCUMENTATION.md).

If you want one file that covers setup, architecture, configuration, APIs, providers, operations, security, compliance, and contribution workflow, start there.

## What SovereignGuard Does

SovereignGuard provides four core controls:

1. Detects PII in outbound prompts using universal and locale-specific recognizers.
2. Replaces those values with reversible SG tokens such as `{{SG_EMAIL_a3f9b2c1}}`.
3. Stores the token-to-original mapping locally in memory, encrypted SQLite, or Redis.
4. Restores original values after the provider responds so your application receives usable text.

This gives engineering, legal, security, and compliance teams a concrete architectural boundary around regulated data flows.

## Why It Exists

Most teams evaluating LLM adoption run into the same blocker: the application prompt includes names, emails, phone numbers, customer IDs, addresses, invoices, or other regulated data, and those values cannot simply be forwarded to a third-party inference provider without review.

SovereignGuard is designed to reduce that exposure by making the provider see tokens instead of raw identifiers.

It is not a legal substitute for vendor due diligence, data processing agreements, retention controls, or internal governance. It is the technical enforcement layer that makes those reviews materially easier.

## Request Lifecycle

```text
Your App
     |
     |  OpenAI-compatible request
     v
SovereignGuard
     |
     |-- create session
     |-- detect PII
     |-- replace values with SG tokens
     |-- store token mapping locally
     v
LLM Provider
     |
     |-- receives tokenized text only
     |-- returns tokenized response
     v
SovereignGuard
     |
     |-- restore SG tokens to original values
     |-- destroy or expire session mapping
     v
Your App
```

## Current Capabilities

### Privacy and Security

- API key authentication for gateway clients
- Per-IP rate limiting
- Request size enforcement
- Structured logging with request IDs
- Tamper-evident immutable audit logging (hash-chained entries)
- Fail-closed circuit breaker for masking/encryption failures
- Minimal public health endpoint
- Protected audit reporting and admin endpoints
- Session TTL cleanup daemon
- OpenAI-compatible error responses
- Optional encrypted local mapping backend

### Advanced Gateway Controls

- Semantic token restoration for LLM token reformatting and paraphrasing
- Async masking pipeline (fast regex path + heavy recognizer path)
- Policy engine for role-based masking behavior (RBAC-ready)
- Sensitivity-aware smart routing for local fallback LLM flows
- Streaming response restoration with chunk boundary handling

### Provider Support

- OpenAI-compatible APIs
- Anthropic response restoration support
- Mistral via OpenAI-compatible adapter behavior
- Custom OpenAI-compatible endpoints

### Mapping Backends

- `memory`: fast, single-instance, non-persistent
- `local`: encrypted SQLite backend for persistent local storage
- `redis`: shared backend for distributed deployments
- `vault`: HashiCorp Vault KV v2 backend for security-standard secret storage

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

Recognizer behavior is heuristic and pattern-based. You should validate it against your own real data classes before production rollout.

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

## Drop-in Usage

### OpenAI Python SDK

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
                              "content": "Contact baha at baha@example.com and xxx.",
                    }
          ],
)

print(response.choices[0].message.content)
```

### Raw HTTP

```bash
curl http://localhost:8000/v1/chat/completions \
     -H "Authorization: Bearer sg-client-key-1" \
     -H "Content-Type: application/json" \
     -d '{
          "model": "gpt-4o-mini",
          "messages": [
               {"role": "user", "content": "Email user@example.com about invoice 123."}
          ]
     }'
```

## Configuration Overview

Important settings are defined in [.env.example](.env.example):

| Setting | Purpose |
|---------|---------|
| `TARGET_API_URL` | Base URL of the upstream provider |
| `TARGET_API_KEY` | Real API key used by SovereignGuard to call the provider |
| `TARGET_PROVIDER` | `openai`, `anthropic`, `mistral`, or `custom` |
| `GATEWAY_API_KEYS` | Comma-separated client keys accepted by the gateway |
| `MAPPING_BACKEND` | `memory`, `local`, or `redis` |
| `MAPPING_TTL_SECONDS` | Session mapping expiration window |
| `ENCRYPTION_KEY` | Required for durable encrypted local mappings |
| `ALLOWED_ORIGINS` | CORS allowlist |
| `RATE_LIMIT_ENABLED` | Turns request throttling on or off |
| `RATE_LIMIT_RPM` | Requests per minute per client IP |
| `MAX_REQUEST_SIZE_MB` | Upper bound for request body size |
| `ENABLED_LOCALES` | Recognizer locale set |
| `CONFIDENCE_THRESHOLD` | Minimum detection score to mask |
| `POLICY_FILE` | Path to role-based masking policy definition |
| `LOCAL_FALLBACK_ENABLED` | Enables sensitivity-based local model fallback |
| `LOCAL_LLM_URL` | Base URL for local sovereign model endpoint |
| `SENSITIVITY_THRESHOLD` | Route-to-local threshold for high sensitivity payloads |
| `CIRCUIT_BREAKER_ENABLED` | Enables fail-closed masking safety circuit |
| `VAULT_ENABLED` | Enables HashiCorp Vault mapping backend |

For full configuration details, see [docs/configuration.md](docs/configuration.md).

## API Surface

SovereignGuard exposes an OpenAI-style gateway plus operational endpoints:

- `GET /health`
- `POST /v1/chat/completions`
- `POST /v1/completions`
- `POST /v1/embeddings`
- `GET /v1/models`
- `GET /audit/report`
- `GET /admin/stats`
- `DELETE /admin/sessions/{session_id}`

See [docs/api-reference.md](docs/api-reference.md) for request and response details.

## Documentation Map

- [docs/architecture.md](docs/architecture.md): internal architecture and execution flow
- [docs/configuration.md](docs/configuration.md): all runtime settings and production guidance
- [docs/deployment.md](docs/deployment.md): local, container, and production deployment patterns
- [docs/api-reference.md](docs/api-reference.md): endpoints, payloads, and operational routes
- [docs/gdpr-compliance.md](docs/gdpr-compliance.md): compliance posture, limits, and governance guidance
- [docs/operations.md](docs/operations.md): monitoring, alerting, troubleshooting, scaling
- [docs/multi-provider-setup.md](docs/multi-provider-setup.md): provider-specific integration notes
- [docs/adding-recognizers.md](docs/adding-recognizers.md): extending the recognizer system
- [docs/launch-kit.md](docs/launch-kit.md): demo-first launch playbook and LinkedIn distribution templates

## Project Structure

```text
sovereignguard/
     audit/         audit logging, metrics, reporting
     engine/        masking, restoration, session mapping
     middleware/    auth, rate limiting, request ID, size limits
     proxy/         API routes, provider adapters, forwarding logic
     recognizers/   universal and locale-specific PII detection
     utils/         crypto, tokenizer, shared helpers
```

## Production Recommendations

Use these as the minimum production baseline:

1. Set `GATEWAY_API_KEYS` and keep them in a secrets manager.
2. Set an explicit `ENCRYPTION_KEY` if you use `MAPPING_BACKEND=local`.
3. Use `MAPPING_BACKEND=redis` for multi-instance deployments.
4. Restrict `ALLOWED_ORIGINS` and disable `DEBUG`.
5. Put the gateway behind TLS termination and controlled ingress.
6. Keep `BYPASS_MASKING=false` outside local development.
7. Enable `CIRCUIT_BREAKER_ENABLED=true` for fail-closed protection.
8. Use `VAULT_ENABLED=true` when policy requires external secret vaulting.
9. Monitor Prometheus metrics and verify immutable audit chain integrity.

## Testing

Run the test suite:

```bash
python -m pytest tests/ -v
```

Current status: `79 passed`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow, testing requirements, and extension guidance.

## Security

See [SECURITY.md](SECURITY.md) for vulnerability disclosure, threat model, deployment hardening, and key rotation guidance.

## License

Business Source License 1.1. See [LICENSE](LICENSE) for the full terms.
