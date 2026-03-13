"""
Tests for middleware components: auth, rate limiting, request size, request ID.
"""

import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("TARGET_API_KEY", "test-key")

from sovereignguard.main import app
from sovereignguard.config import settings


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:

    def test_health_returns_minimal_info(self, client):
        """Health endpoint should not expose internal state."""
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["gateway"] == "SovereignGuard"
        # Should NOT expose recognizer count or backend details
        assert "recognizers_loaded" not in body
        assert "mapping_backend" not in body


class TestRequestID:

    def test_response_has_request_id_header(self, client):
        """Every response should have X-Request-ID header."""
        response = client.get("/health")
        assert "x-request-id" in response.headers

    def test_client_provided_request_id_preserved(self, client):
        """Client-provided X-Request-ID should be echoed back."""
        response = client.get(
            "/health",
            headers={"X-Request-ID": "test-req-123"},
        )
        assert response.headers.get("x-request-id") == "test-req-123"


class TestSecurityHeaders:

    def test_security_headers_present(self, client):
        """Security headers should be set on every response."""
        response = client.get("/health")
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"

    def test_timing_header_present(self, client):
        response = client.get("/health")
        assert "x-process-time-ms" in response.headers


class TestAuthentication:

    def test_health_is_public(self, client):
        """Health endpoint should be accessible without auth."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_no_auth_when_no_keys_configured(self, client):
        """When GATEWAY_API_KEYS is empty, all endpoints should be accessible."""
        # Default test config has no keys, so this should work
        response = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
        )
        # Should get past auth (may fail at forward, but not 401)
        assert response.status_code != 401


class TestAuditEndpoint:

    def test_audit_report_rejects_invalid_dates(self, client):
        """Audit endpoint should validate date format."""
        response = client.get("/audit/report?start_date=invalid")
        assert response.status_code == 400

    def test_audit_report_accepts_valid_dates(self, client):
        """Audit endpoint should accept ISO date format."""
        response = client.get("/audit/report?start_date=2024-01-01&end_date=2024-12-31")
        assert response.status_code == 200


class TestAdminEndpoints:

    def test_admin_stats(self, client):
        """Admin stats should return gateway configuration."""
        response = client.get("/admin/stats")
        assert response.status_code == 200
        body = response.json()
        assert "recognizers_loaded" in body
        assert "masking_enabled" in body

    def test_admin_delete_session(self, client):
        """Admin should be able to force-destroy a session."""
        response = client.delete("/admin/sessions/fake-session-id")
        assert response.status_code == 200
        assert response.json()["status"] == "destroyed"
