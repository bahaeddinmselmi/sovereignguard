# Architecture

SovereignGuard is a FastAPI-based privacy gateway that exposes OpenAI-style endpoints to client applications while enforcing local masking, reversible token mapping, and post-response restoration before data returns to the caller.

## High-Level Design

At runtime, SovereignGuard acts as a privacy boundary between a source application and an external LLM provider.

```text
Client Application
	|
	|  OpenAI-compatible request
	v
FastAPI Gateway Layer
	|
	|-- auth
	|-- rate limit
	|-- request size check
	|-- request ID propagation
	v
Masking Engine
	|
	|-- recognizer registry
	|-- overlap resolution
	|-- token generation
	|-- local mapping store
	v
Provider Adapter + Forwarder
	|
	|-- OpenAI / Anthropic / Mistral handling
	v
External LLM Provider
	|
	v
Restoration Layer
	|
	|-- response text extraction
	|-- token restoration
	v
Client Application
```

## Request Processing Pipeline

### 1. Ingress and Traffic Controls

Requests enter through the FastAPI app in [sovereignguard/main.py](../sovereignguard/main.py).

The middleware stack performs:

1. Request ID generation or propagation
2. Security header injection
3. Timing measurement
4. Per-IP rate limiting
5. Gateway API key authentication
6. Request size enforcement
7. CORS handling

This is the first protection layer. It ensures malformed, oversized, or unauthorized traffic is rejected before any masking work begins.

### 2. Session Creation

The request handler creates a session-scoped namespace in the mapping store. Every token generated for the request is isolated to that session.

Session isolation matters because it prevents tokens from one request being resolved using another request's token map.

### 3. PII Detection

The masking engine loads recognizers from the registry based on `ENABLED_LOCALES`.

Recognizer groups:

- Universal recognizers: email, generic phone, credit card, IBAN, IP address, person name, date of birth
- Locale-specific recognizers: Tunisia, France, Morocco

Each recognizer returns `RecognizerResult` objects containing:

- `entity_type`
- `start`
- `end`
- `score`
- `text`
- `locale`

### 4. Overlap Resolution

When multiple recognizers match overlapping text regions, the masking engine resolves conflicts by keeping the highest-confidence candidate. Locale-specific recognizers receive a small priority boost so that a country-specific identifier can beat a looser universal match.

### 5. Tokenization and Mapping Storage

For each resolved entity:

1. A token is generated such as `{{SG_EMAIL_4fa9d2c1}}`
2. The original value is encrypted
3. The token-to-value relationship is stored in the selected backend
4. The original text segment is replaced with the token in the outbound payload

Deduplication logic reuses an existing token for the same value and entity type within a session.

### 6. Provider Forwarding

The request handler forwards the tokenized payload to the configured upstream provider using the gateway's `TARGET_API_KEY`, not the client-supplied credential.

The client credential authenticates against SovereignGuard. The provider credential authenticates SovereignGuard against the upstream LLM API.

### 7. Response Adaptation and Restoration

Different providers structure responses differently. The provider adapter layer extracts text from the provider-specific schema, passes it to the restoration engine, then writes the restored text back into the correct response structure before returning it to the caller.

Supported patterns:

- OpenAI-style `choices[].message.content`
- Legacy completions `choices[].text`
- Anthropic `content[].text`
- Streaming delta restoration

### 8. Session Cleanup

At the end of the request lifecycle, the active session is explicitly destroyed where possible. In addition, a background cleanup daemon periodically purges expired sessions using `MAPPING_TTL_SECONDS`.

This gives the system both deterministic cleanup for normal requests and bounded cleanup for abnormal flows.

## Main Components

### Configuration Layer

Defined in [sovereignguard/config.py](../sovereignguard/config.py).

Responsibilities:

- load environment-driven settings
- validate critical configuration combinations
- expose provider, mapping, logging, and security settings to the rest of the system

### Middleware Layer

Located in [sovereignguard/middleware](../sovereignguard/middleware).

Responsibilities:

- authenticate clients
- enforce traffic controls
- attach request correlation metadata
- reject abusive or invalid requests early

### Proxy Layer

Located in [sovereignguard/proxy](../sovereignguard/proxy).

Responsibilities:

- expose OpenAI-compatible endpoints
- parse and normalize incoming request bodies
- forward calls to providers
- restore tokenized responses

### Recognizer Layer

Located in [sovereignguard/recognizers](../sovereignguard/recognizers).

Responsibilities:

- detect PII in plain text
- provide locale-aware coverage
- return offset-correct matches without mutating source text

### Engine Layer

Located in [sovereignguard/engine](../sovereignguard/engine).

Responsibilities:

- orchestrate masking and restoration
- manage sessions
- store and retrieve encrypted mappings
- resolve overlaps and deduplicate values

### Audit and Metrics Layer

Located in [sovereignguard/audit](../sovereignguard/audit).

Responsibilities:

- write JSONL audit logs without raw PII
- expose Prometheus metrics
- generate aggregate audit reports

## Storage Model

### In-Memory Backend

- fastest option
- plaintext never written to disk
- state lost on process restart
- suited to development and single-node ephemeral processing

### Encrypted SQLite Backend

- persistent local storage
- values encrypted before storage
- good for single-node deployments needing local durability

### Redis Backend

- shared state across instances
- required for horizontally scaled deployments
- TTL-based expiration built in

## Security Model

SovereignGuard is designed around a few invariants:

1. Raw PII should not cross the provider boundary when masking is enabled.
2. Raw PII should never be written to audit logs.
3. Token maps must be session-isolated.
4. Public operational endpoints should expose minimal information.
5. Upstream provider credentials should not be supplied by clients.

## Failure Modes and Design Tradeoffs

### Recognizer Coverage Is Heuristic

The system favors explicit, inspectable recognizer logic over opaque NLP dependencies. This improves operational clarity but means coverage is only as good as the recognizers you deploy.

### Token Restoration Depends on Session Availability

If a session expires too early or the wrong backend is used in a multi-instance deployment, response restoration may fail and tokens may remain in the output.

### Provider Format Drift Must Be Managed

If an upstream provider changes its response schema, the adapter layer may need updates before restoration continues to work correctly.
