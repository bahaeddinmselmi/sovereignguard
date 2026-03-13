# Changelog

All notable changes to SovereignGuard will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2024-12-XX

### Added
- **Authentication middleware**: API key authentication for gateway clients (`GATEWAY_API_KEYS`)
- **Rate limiting**: Per-IP sliding window rate limiter (`RATE_LIMIT_ENABLED`, `RATE_LIMIT_RPM`)
- **Request size enforcement**: `MAX_REQUEST_SIZE_MB` now enforced via middleware
- **Request ID correlation**: `X-Request-ID` header generation and propagation
- **Structured logging**: Full structlog integration with JSON output in production
- **Session cleanup daemon**: Background task purges expired sessions every 5 minutes
- **Person name recognizer**: Context-aware detection with title/keyword patterns
- **Date of birth recognizer**: Multi-format DOB detection with contextual matching
- **Multi-provider support**: Anthropic and Mistral response format adapters
- **Admin endpoints**: `GET /admin/stats`, `DELETE /admin/sessions/{id}`
- **CORS configuration**: `ALLOWED_ORIGINS` environment variable for production
- **Startup config validation**: Pydantic model validator checks config on boot
- **Security headers**: HSTS, Cache-Control headers added
- **Prometheus metrics server**: Now actually starts on configured port
- `.gitignore`, `.dockerignore`, `SECURITY.md`, `CHANGELOG.md`
- GitHub Actions CI workflow with tests, linting, and Docker build
- Makefile with common development commands
- Comprehensive test suite (40+ tests)
- Operations runbook documentation

### Changed
- `/health` endpoint no longer exposes internal configuration details
- Error responses now use OpenAI-compatible format `{"error": {"message", "type", "code"}}`
- `TARGET_API_KEY` is now optional (with startup warning) for development flexibility
- Restored `restorer.py` to use shared regex patterns (eliminated code duplication)
- Version bumped to 0.2.0

### Fixed
- `/audit/report` date parameters now validated (prevents injection)
- CORS wildcard replaced with configurable `ALLOWED_ORIGINS`
- Mapping store TTL enforcement (previously `MAPPING_TTL_SECONDS` was unused)

### Security
- Added authentication middleware with constant-time key comparison
- Request size limits prevent OOM attacks
- Rate limiting prevents brute force and DoS
- Audit endpoint protected behind auth middleware

## [0.1.0] - 2024-12-XX

### Added
- Initial release
- Core masking engine with session-scoped token mapping
- Universal recognizers: email, phone, credit card, IBAN, IP address
- Tunisia recognizers: national ID, phone, company ID, address
- France recognizers: NIR, SIRET, phone, address
- Morocco recognizers: CIN, phone, ICE
- Three mapping backends: in-memory, encrypted SQLite, Redis
- OpenAI-compatible proxy endpoints
- Streaming response support with cross-chunk token restoration
- GDPR audit logging (JSONL)
- Docker and Docker Compose deployment
- FastAPI with CORS and security headers
