# GDPR Compliance

SovereignGuard is intended to reduce data protection exposure by ensuring raw personal data is masked before it is sent to an external model provider. It is a technical control that supports compliance programs. It is not a legal conclusion on its own.

## What SovereignGuard Helps With

SovereignGuard can help organizations implement privacy-by-design around LLM integrations by introducing a local enforcement point for prompt anonymization and response restoration.

It directly supports the following objectives:

1. minimize outbound transfer of raw personal data
2. reduce the amount of directly identifying content sent to third-party APIs
3. keep restoration mappings inside infrastructure you control
4. maintain auditable records of masking and restoration activity without logging raw values

## Controls Provided by the Gateway

### Data Minimization

When masking is active, the provider receives tokens instead of raw identifiers for supported patterns. This can materially reduce the exposure of customer or employee data in prompt traffic.

### Local Restoration Boundary

Original values remain in the mapping store controlled by your environment. They are restored only after the provider response returns.

### Auditability

Audit logs record events such as masking counts, restoration counts, and session operations without logging the actual sensitive values.

### Scoped Session Isolation

Mappings are isolated by session, reducing the chance of cross-request leakage or accidental token reuse.

### Operational Hardening

Authentication, rate limiting, request size enforcement, and request correlation improve the ability to run the gateway as a controlled internal service.

## What SovereignGuard Does Not Solve

You still need to address the rest of the compliance program around the model provider and your internal usage.

SovereignGuard does not by itself provide:

- a lawful basis for processing
- a signed DPA or vendor terms review
- retention policy enforcement at the provider side
- model output review for generated personal data
- full classification of all possible sensitive content types
- legal validation that tokenization alone makes all data non-personal

## Practical GDPR Positioning

SovereignGuard is best described as a privacy-preserving proxy or anonymization control in the application-to-provider path.

The strongest internal compliance position usually looks like this:

1. the application sends traffic only through SovereignGuard
2. masking is enabled and tested against real production-like examples
3. provider credentials are held only by the gateway
4. audit logs, metrics, and operations controls are in place
5. the provider relationship is separately reviewed by legal and security teams

## Residual Risk Areas

### Recognizer Misses

Detection is regex and heuristic based. If a recognizer does not match a value, that value may still leave your environment in plain text.

Mitigation:

- validate recognizers against real data samples
- add custom recognizers for domain-specific identifiers
- tune `ENABLED_LOCALES` and `CONFIDENCE_THRESHOLD`

### Model Inference Leakage From Context

Even if direct identifiers are masked, a prompt may still contain enough surrounding information to make a person indirectly identifiable.

Mitigation:

- redact additional contextual fields
- minimize prompt content upstream of the gateway
- create custom policies for especially sensitive workflows

### Operational Misconfiguration

Examples:

- `BYPASS_MASKING=true`
- no gateway authentication
- permissive CORS in production
- wrong backend in multi-instance deployments

Mitigation:

- enforce production configuration via infrastructure policy
- use staging validation and smoke tests
- monitor startup warnings and audit events

## Recommended Governance Controls Around the Gateway

Use SovereignGuard as part of a broader control set:

1. DPIA or equivalent privacy review for the use case
2. vendor due diligence and contract review
3. access controls around prompt sources
4. key rotation and secret management
5. incident response procedures for failed masking or accidental disclosure
6. retention limits for logs and mapping backends

## Deployment Guidance for Stronger Compliance Posture

- place the gateway inside the same trusted network boundary as the source application
- disable debug mode in production
- use explicit `ENCRYPTION_KEY` values for persistent local mappings
- use Redis for clustered deployments to avoid restoration mismatches
- protect the gateway with service-to-service authentication
- archive audit logs according to your retention policy

## Documentation You Should Pair With This Guide

- [docs/configuration.md](configuration.md)
- [docs/deployment.md](deployment.md)
- [docs/operations.md](operations.md)
- [SECURITY.md](../SECURITY.md)
