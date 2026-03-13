# Multi-Provider Setup

SovereignGuard can sit in front of more than one LLM provider, but response restoration depends on the gateway understanding the provider response format correctly.

This document explains how provider selection works and what to validate for each supported provider family.

## Provider Selection

Two settings control provider integration:

```env
TARGET_PROVIDER=openai
TARGET_API_URL=https://api.openai.com
```

Supported `TARGET_PROVIDER` values:

- `openai`
- `anthropic`
- `mistral`
- `custom`

## How the Adapter Layer Works

Provider adapters are implemented in [sovereignguard/proxy/providers.py](../sovereignguard/proxy/providers.py).

They are responsible for:

1. locating text fields inside provider responses
2. locating text deltas inside streaming chunks
3. writing restored values back into the correct schema

If `TARGET_PROVIDER` does not match the actual response schema, the request may succeed but restoration may leave `{{SG_*}}` tokens in the final response.

## OpenAI

Recommended settings:

```env
TARGET_PROVIDER=openai
TARGET_API_URL=https://api.openai.com
```

Expected response handling:

- chat: `choices[].message.content`
- completions: `choices[].text`
- streaming: `choices[].delta.content`

Use this mode for:

- OpenAI
- Azure endpoints that expose an OpenAI-compatible shape, if routed compatibly
- compatible gateways that mimic the OpenAI REST schema

## Anthropic

Recommended settings:

```env
TARGET_PROVIDER=anthropic
TARGET_API_URL=https://api.anthropic.com
```

Expected response handling:

- content blocks: `content[].text`
- streaming text deltas: `content_block_delta` events with `delta.text`

Validation checklist:

1. send a request containing a maskable value
2. confirm the upstream provider receives SG tokens, not raw identifiers
3. confirm the final response contains restored values, not tokens
4. repeat the same test in streaming mode if you use streaming in production

## Mistral

Recommended settings:

```env
TARGET_PROVIDER=mistral
TARGET_API_URL=https://api.mistral.ai
```

Current behavior uses the OpenAI adapter because Mistral commonly exposes an OpenAI-compatible response structure.

You should still validate this against your exact Mistral endpoint version and SDK path.

## Custom Providers

If your upstream provider exposes an OpenAI-compatible response schema, use:

```env
TARGET_PROVIDER=custom
TARGET_API_URL=https://your-provider.example.com
```

If the response schema differs materially, add a dedicated adapter rather than trying to force compatibility at the application layer.

## Adding a New Provider Adapter

To add a new provider:

1. create a new adapter class inheriting from `BaseProviderAdapter`
2. implement response text extraction and delta extraction methods
3. register it in `get_provider_adapter()`
4. add unit tests for response and streaming handling
5. validate full end-to-end masking and restoration against a real or mocked provider response

## Provider Validation Checklist

Use this checklist before shipping a provider integration:

1. standard response restoration works
2. streaming restoration works
3. provider errors still surface cleanly to the client
4. multipart text content is masked correctly before forwarding
5. long prompts and multi-entity prompts restore reliably

## Common Provider Pitfalls

### Wrong `TARGET_PROVIDER`

The gateway forwards successfully, but restoration logic reads the wrong response fields.

### Provider-Compatible but Not Fully Identical Schemas

Some providers mimic OpenAI but differ in subtle ways during streaming or tool output. Test both non-streaming and streaming paths.

### SDK Base URL Differences

Some SDKs expect the base URL to include `/v1`, while others append it automatically. Validate your client SDK configuration separately from gateway runtime configuration.