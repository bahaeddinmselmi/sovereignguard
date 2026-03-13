from unittest.mock import AsyncMock

from sovereignguard.proxy.router import handler


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["gateway"] == "SovereignGuard"


def test_chat_completion_masks_and_restores(client, monkeypatch):
    async def fake_forward_request(endpoint, body, headers):
        # Ensure request was masked before forwarding
        combined = " ".join(msg.get("content", "") for msg in body["messages"] if isinstance(msg.get("content"), str))
        assert "12345678" not in combined
        assert "+216 98 765 432" not in combined
        assert "{{SG_TN_NATIONAL_ID_" in combined
        assert "{{SG_TN_PHONE_" in combined
        return {
            "choices": [
                {
                    "message": {
                        "content": "Bonjour {{SG_TN_NATIONAL_ID_deadbeef}} {{SG_TN_PHONE_cafebabe}}"
                    }
                }
            ]
        }

    original_forward = handler.forward_request

    async def wrapped_forward(endpoint, body, headers):
        # Pull real tokens from masked request so restoration can succeed
        content = body["messages"][0]["content"]
        tokens = [token for token in content.split() if token.startswith("{{SG_")]
        return {
            "choices": [
                {
                    "message": {
                        "content": f"Processed {tokens[0]} and {tokens[1]}"
                    }
                }
            ]
        }

    monkeypatch.setattr(handler, "forward_request", wrapped_forward)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": "CIN 12345678 phone +216 98 765 432",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    content = body["choices"][0]["message"]["content"]
    assert "12345678" in content
    assert "+216 98 765 432" in content

    monkeypatch.setattr(handler, "forward_request", original_forward)
