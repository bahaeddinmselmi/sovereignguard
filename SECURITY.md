# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in SovereignGuard, please report it
responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

### How to Report

1. Email: Send details to the maintainers with subject line `[SECURITY] SovereignGuard Vulnerability`
2. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 5 business days
- **Fix Timeline**: Critical vulnerabilities patched within 7 days

## Security Best Practices for Deployment

### Mandatory for Production

1. **Set `GATEWAY_API_KEYS`**: Never run without authentication in production
2. **Set `ENCRYPTION_KEY`**: Generate a strong key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
3. **Set `ALLOWED_ORIGINS`**: Restrict CORS to specific domains
4. **Set `TARGET_API_KEY`**: Never commit API keys to version control
5. **Use HTTPS**: Deploy behind a TLS-terminating reverse proxy (nginx, Caddy, etc.)
6. **Set `BYPASS_MASKING=false`**: Never bypass masking in production

### Recommended

- Enable rate limiting (`RATE_LIMIT_ENABLED=true`)
- Use encrypted mapping backend (`MAPPING_BACKEND=local`) or Redis
- Rotate `ENCRYPTION_KEY` periodically
- Monitor audit logs for anomalies
- Keep dependencies updated

## Threat Model

### What SovereignGuard Protects Against

- PII leaking to third-party LLM providers
- Accidental PII exposure in logs and metrics
- Unauthorized access to the gateway (when auth is configured)

### What SovereignGuard Does NOT Protect Against

- Compromised server infrastructure
- Side-channel attacks on the host machine
- PII embedded in images or binary data (text-only detection)
- Adversarial inputs designed to evade regex-based detection

### Known Limitations

- Person name detection uses heuristic patterns, not NLP — some names may escape detection
- Date of birth detection requires contextual keywords nearby
- In-memory mapping backend loses all data on process restart
- Auto-generated encryption keys are session-scoped (use explicit keys in production)

## Key Rotation

### Rotating the Encryption Key

1. Generate a new key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Update `ENCRYPTION_KEY` in your environment
3. Restart the gateway
4. Note: Existing encrypted SQLite mappings from old key will be unrecoverable

### Rotating Gateway API Keys

1. Add the new key to `GATEWAY_API_KEYS` (comma-separated list)
2. Restart the gateway
3. Migrate clients to the new key
4. Remove the old key from `GATEWAY_API_KEYS`
5. Restart again
