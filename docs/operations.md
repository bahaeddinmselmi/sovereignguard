# Operations Runbook

Operational guide for running SovereignGuard in production.

## Startup Checklist

Before deploying to production, verify:

- [ ] `TARGET_API_KEY` is set to a valid LLM provider key
- [ ] `GATEWAY_API_KEYS` is configured with client API keys
- [ ] `ENCRYPTION_KEY` is explicitly set (not auto-generated)
- [ ] `ALLOWED_ORIGINS` is set to your application domains
- [ ] `BYPASS_MASKING` is `false`
- [ ] `DEBUG` is `false`
- [ ] TLS termination is configured (nginx/Caddy/ALB)
- [ ] Audit log directory is writable and rotated

## Health Check

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","gateway":"SovereignGuard","version":"0.2.0"}
```

## Monitoring

### Prometheus Metrics

Metrics are exposed on port `METRICS_PORT` (default: 9090):

| Metric | Type | Description |
|--------|------|-------------|
| `sovereignguard_requests_total` | Counter | Total requests (labeled by status) |
| `sovereignguard_entities_masked_total` | Counter | PII entities masked (by type) |
| `sovereignguard_tokens_restored_total` | Counter | Tokens restored in responses |
| `sovereignguard_request_duration_seconds` | Histogram | Request processing latency |
| `sovereignguard_active_sessions` | Gauge | Currently active masking sessions |

### Key Alerts to Configure

- `sovereignguard_active_sessions > 100` — possible session leak
- `rate(sovereignguard_requests_total{status="error"}[5m]) > 0.1` — error rate spike
- `sovereignguard_request_duration_seconds{quantile="0.99"} > 5` — latency degradation

### Structured Logs

In production, logs are JSON-formatted via structlog:

```json
{
  "event": "gateway_starting",
  "target_api": "https://api.openai.com",
  "provider": "openai",
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "info"
}
```

## Troubleshooting

### High Memory Usage

**Symptom**: Memory grows over time.

**Cause**: Session mappings not being cleaned up.

**Fix**:
1. Check if session cleanup daemon is running (startup log: `session_cleanup`)
2. Reduce `MAPPING_TTL_SECONDS` (default: 3600)
3. Monitor `sovereignguard_active_sessions` gauge

### High Latency

**Symptom**: Requests take > 2s to process.

**Cause**: Too many recognizers running or large request bodies.

**Fix**:
1. Reduce `ENABLED_LOCALES` to only needed locales
2. Check `MAX_REQUEST_SIZE_MB` — reject overly large requests
3. Monitor `sovereignguard_request_duration_seconds` histogram

### Token Restoration Failures

**Symptom**: Response contains `{{SG_EMAIL_...}}` tokens instead of original values.

**Cause**: Session expired between mask and restore, or LLM significantly reformatted tokens.

**Fix**:
1. Increase `MAPPING_TTL_SECONDS` if using long-running models
2. Check audit logs for `tokens_not_found > 0` events
3. The fuzzy matching handles most LLM reformatting, but extreme cases may fail

### Redis Connection Failures

**Symptom**: `ConnectionError` at startup with `MAPPING_BACKEND=redis`.

**Fix**:
1. Verify `REDIS_URL` is correct and Redis is reachable
2. Check Redis auth credentials
3. Fall back to `MAPPING_BACKEND=memory` for quick recovery

### Authentication Failures

**Symptom**: All requests return 401.

**Fix**:
1. Verify `GATEWAY_API_KEYS` contains the correct keys
2. Ensure client sends `Authorization: Bearer <key>` header
3. Check for trailing whitespace in environment variable values

## Scaling

### Horizontal Scaling

For multiple instances:
1. Use `MAPPING_BACKEND=redis` — sessions must be shared across instances
2. Set `REDIS_URL` to a shared Redis instance
3. Load balance with sticky sessions (optional, not required)

### Vertical Scaling

- `WORKERS`: Set to `2 * CPU cores + 1` (default: 4)
- `MAX_REQUEST_SIZE_MB`: Reduce to limit memory per request
- `REQUEST_TIMEOUT_SECONDS`: Set based on target LLM latency

## Backup & Recovery

### Audit Logs

- Located at `AUDIT_LOG_PATH` (default: `./logs/audit.jsonl`)
- Set up log rotation (logrotate on Linux)
- Archive to S3/GCS for long-term GDPR compliance

### Encrypted SQLite Backend

- Database at `ENCRYPTED_DB_PATH` (default: `./data/sg_mapping.db`)
- **Requires `ENCRYPTION_KEY` to decrypt** — back up the key separately
- Use WAL mode for concurrent read/write (enabled by default)

### Redis Backend

- Standard Redis backup procedures apply (RDB snapshots, AOF)
- TTL handles automatic cleanup — no manual purging needed
