# API Reference

This document describes the public and operational API surface exposed by SovereignGuard.

Unless otherwise noted, endpoints require the client to send:

```http
Authorization: Bearer <gateway-api-key>
```

## Response Conventions

### Success

SovereignGuard generally returns the same schema shape as the upstream provider for model endpoints.

### Errors

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

## Public Endpoint

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

## Model Endpoints

### `POST /v1/chat/completions`

OpenAI-compatible chat endpoint.

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
- does not need text restoration in embedding vectors

### `GET /v1/models`

Pass-through model listing endpoint.

Behavior:

- forwards request to the configured provider
- returns provider model metadata

## Operational Endpoints

### `GET /audit/report`

Returns aggregate audit information without exposing raw PII.

Query parameters:

- `start_date`: optional, `YYYY-MM-DD`
- `end_date`: optional, `YYYY-MM-DD`

Validation rules:

- invalid date formats return `400`
- endpoint is protected by gateway authentication middleware

### `GET /admin/stats`

Returns gateway runtime metadata useful for operator inspection.

Current response fields include:

- loaded recognizer count
- masking enabled status
- configured backend
- configured provider
- enabled locales
- rate limiting status

This endpoint is operational, not public.

### `DELETE /admin/sessions/{session_id}`

Force-clears a session mapping namespace.

Use cases:

- debugging stuck sessions
- emergency cleanup
- administrative cleanup in long-running environments

Example response:

```json
{
	"status": "destroyed",
	"session_id": "abc-123"
}
```

## Common Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `400` | Invalid request payload or invalid parameters |
| `401` | Missing or invalid gateway API key |
| `413` | Request body too large |
| `429` | Rate limit exceeded |
| `500` | Internal gateway or upstream failure |

## Headers Added by the Gateway

SovereignGuard adds several response headers:

- `X-Request-ID`
- `X-Process-Time-Ms`
- `X-Powered-By`
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`

It also adds security headers such as `X-Content-Type-Options`, `X-Frame-Options`, and `Strict-Transport-Security`.
