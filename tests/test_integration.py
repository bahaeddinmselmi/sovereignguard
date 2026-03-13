"""
Integration tests — full request → mask → forward (mock) → restore → response pipeline.
"""

import os
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

os.environ.setdefault("TARGET_API_KEY", "test-key")

from sovereignguard.main import app
from sovereignguard.proxy.router import handler


@pytest.fixture
def client():
    return TestClient(app)


class TestFullPipeline:

    def test_email_masked_and_restored(self, client, monkeypatch):
        """Email PII should be masked before forwarding and restored in response."""

        async def fake_forward(endpoint, body, headers):
            content = body["messages"][0]["content"]
            assert "user@example.com" not in content
            assert "{{SG_EMAIL_" in content
            # Echo back the masked content
            return {"choices": [{"message": {"content": content}}]}

        monkeypatch.setattr(handler, "forward_request", fake_forward)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "My email is user@example.com"}],
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "user@example.com" in body["choices"][0]["message"]["content"]

    def test_multiple_pii_types_masked(self, client, monkeypatch):
        """Multiple PII types in one request should all be masked and restored."""

        async def fake_forward(endpoint, body, headers):
            content = body["messages"][0]["content"]
            assert "user@test.com" not in content
            assert "12345678" not in content
            return {"choices": [{"message": {"content": content}}]}

        monkeypatch.setattr(handler, "forward_request", fake_forward)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": "CIN 12345678, email user@test.com",
                    }
                ],
            },
        )

        assert response.status_code == 200
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        assert "user@test.com" in content
        assert "12345678" in content

    def test_no_pii_passthrough(self, client, monkeypatch):
        """Text without PII should pass through unchanged."""

        async def fake_forward(endpoint, body, headers):
            content = body["messages"][0]["content"]
            assert content == "What is the capital of France?"
            return {
                "choices": [{"message": {"content": "Paris is the capital of France."}}]
            }

        monkeypatch.setattr(handler, "forward_request", fake_forward)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "user", "content": "What is the capital of France?"}
                ],
            },
        )

        assert response.status_code == 200

    def test_legacy_completions_endpoint(self, client, monkeypatch):
        """Legacy /v1/completions should also mask and restore."""

        async def fake_forward(endpoint, body, headers):
            assert "user@example.com" not in body.get("prompt", "")
            return {"choices": [{"text": body["prompt"]}]}

        monkeypatch.setattr(handler, "forward_request", fake_forward)

        response = client.post(
            "/v1/completions",
            json={"model": "gpt-3.5-turbo-instruct", "prompt": "Email: user@example.com"},
        )

        assert response.status_code == 200
        body = response.json()
        assert "user@example.com" in body["choices"][0]["text"]

    def test_multipart_message_content(self, client, monkeypatch):
        """Multipart messages (text + image) should mask text parts."""

        async def fake_forward(endpoint, body, headers):
            parts = body["messages"][0]["content"]
            text_part = next(p for p in parts if p["type"] == "text")
            assert "user@test.com" not in text_part["text"]
            return {"choices": [{"message": {"content": text_part["text"]}}]}

        monkeypatch.setattr(handler, "forward_request", fake_forward)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Email: user@test.com"},
                            {
                                "type": "image_url",
                                "image_url": {"url": "data:image/png;base64,abc"},
                            },
                        ],
                    }
                ],
            },
        )

        assert response.status_code == 200


class TestErrorHandling:

    def test_invalid_json_returns_400(self, client):
        response = client.post(
            "/v1/chat/completions",
            content=b"not valid json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400

    def test_missing_messages_returns_400(self, client):
        response = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o"},
        )
        assert response.status_code == 400

    def test_forward_failure_returns_500(self, client, monkeypatch):
        async def fake_forward(endpoint, body, headers):
            raise Exception("Target API returned 503")

        monkeypatch.setattr(handler, "forward_request", fake_forward)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert response.status_code == 500
