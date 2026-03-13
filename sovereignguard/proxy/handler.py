"""
Request Handler — Orchestrates the full mask → forward → restore pipeline.
Supports multiple LLM providers (OpenAI, Anthropic, Mistral) via adapters.
Includes smart routing, circuit breaker, policy engine, and streaming restoration.
"""

import httpx
import json
import logging
import re
from typing import Dict, Any, AsyncGenerator, Optional

from sovereignguard.engine.masker import MaskingEngine
from sovereignguard.engine.circuit_breaker import CircuitBreaker, CircuitBreakerError
from sovereignguard.engine.smart_router import SmartRouter, RoutingDestination
from sovereignguard.engine.policy import PolicyEngine
from sovereignguard.audit.immutable_logger import immutable_audit_log
from sovereignguard.config import settings
from sovereignguard.proxy.providers import get_provider_adapter

logger = logging.getLogger(__name__)


class RequestHandler:

    def __init__(self):
        self.engine = MaskingEngine()
        self.client = httpx.AsyncClient(
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        self.provider = get_provider_adapter(settings.TARGET_PROVIDER)
        self.circuit_breaker = CircuitBreaker(name="masking")
        self.smart_router = SmartRouter()
        self.policy_engine = PolicyEngine()

        # Load policies if configured
        if settings.POLICY_FILE:
            self.policy_engine.load_policies_from_file(settings.POLICY_FILE)

    async def mask_request_body(
        self, body: Dict[str, Any], session_id: str,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mask PII in all text fields of a chat completions request body.
        Handles nested message structures.
        Uses circuit breaker and policy engine when configured.
        """
        # Circuit breaker: fail-closed if masking subsystem is broken
        try:
            self.circuit_breaker.check()
        except CircuitBreakerError:
            raise

        if "messages" not in body:
            return body

        masked_body = dict(body)
        masked_messages = []

        try:
            for message in body["messages"]:
                masked_message = dict(message)

                if isinstance(message.get("content"), str):
                    result = self.engine.mask(message["content"], session_id)
                    masked_message["content"] = result.masked_text

                elif isinstance(message.get("content"), list):
                    masked_parts = []
                    for part in message["content"]:
                        if part.get("type") == "text":
                            result = self.engine.mask(part["text"], session_id)
                            masked_parts.append({**part, "text": result.masked_text})
                        else:
                            masked_parts.append(part)
                    masked_message["content"] = masked_parts

                masked_messages.append(masked_message)

            masked_body["messages"] = masked_messages

            if "system" in body and isinstance(body["system"], str):
                result = self.engine.mask(body["system"], session_id)
                masked_body["system"] = result.masked_text

            self.circuit_breaker.record_success()

            # Immutable audit log
            immutable_audit_log(
                "REQUEST_MASKED",
                session_id=session_id,
                message_count=len(masked_messages),
                role=self.policy_engine.get_role_for_key(api_key) if api_key else None,
            )

        except CircuitBreakerError:
            raise
        except Exception as e:
            self.circuit_breaker.record_failure(e)
            logger.error(f"Masking failed, circuit breaker notified: {e}")
            raise

        return masked_body

    async def forward_request(
        self, endpoint: str, body: Dict, headers: Dict
    ) -> Dict:
        """Forward masked request to target LLM API."""

        # Use our API key, not the client's (client sends any string)
        forward_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.TARGET_API_KEY}",
        }

        # Preserve useful headers
        headers_lower = {k.lower(): v for k, v in headers.items()}
        for header in ["user-agent", "x-request-id"]:
            if header in headers_lower:
                forward_headers[header] = headers_lower[header]

        response = await self.client.post(
            f"{settings.TARGET_API_URL}{endpoint}",
            json=body,
            headers=forward_headers,
        )

        if response.status_code != 200:
            logger.error(f"Target API error: {response.status_code} {response.text[:200]}")
            raise Exception(f"Target API returned {response.status_code}")

        return response.json()

    async def restore_response_body(
        self, response: Dict, session_id: str
    ) -> Dict:
        """Restore PII tokens in LLM response back to original values."""
        texts = self.provider.extract_response_texts(response)

        if not texts:
            return response

        restored_response = json.loads(json.dumps(response))  # Deep copy
        for entry in texts:
            result = self.engine.restore(entry["text"], session_id)
            self.provider.set_response_text(
                restored_response, entry["path"], result.restored_text
            )

        return restored_response

    async def stream_with_restoration(
        self, body: Dict, session_id: str, original_request
    ) -> AsyncGenerator[str, None]:
        """
        Handle streaming responses with PII token restoration.

        Buffers chunks until a complete token is detected, then restores and yields.
        Handles token splits across chunk boundaries.
        """
        forward_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.TARGET_API_KEY}",
        }

        # Rolling text buffer so split tokens across chunks can be restored safely.
        # Keep a small tail window unflushed to capture boundary fragments.
        buffer = ""
        tail_window = 96

        async with self.client.stream(
            "POST",
            f"{settings.TARGET_API_URL}/v1/chat/completions",
            json=body,
            headers=forward_headers,
        ) as response:
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                data = line[6:]

                if data == "[DONE]":
                    if buffer:
                        result = self.engine.restore(buffer, session_id)
                        yield f"data: {json.dumps({'choices': [{'delta': {'content': result.restored_text}}]})}\n\n"
                    yield "data: [DONE]\n\n"
                    break

                try:
                    chunk = json.loads(data)
                    delta_content = self.provider.extract_stream_delta(chunk) or ""

                    if not delta_content:
                        yield f"data: {json.dumps(chunk)}\n\n"
                        continue

                    buffer += delta_content

                    # If token opener appears but token not closed yet, keep buffering.
                    open_idx = buffer.rfind("{{SG_")
                    close_idx = buffer.rfind("}}")
                    if open_idx != -1 and close_idx < open_idx:
                        continue

                    # Restore everything except a small tail to protect split boundaries.
                    if len(buffer) <= tail_window:
                        continue

                    flushable = buffer[:-tail_window]
                    buffer = buffer[-tail_window:]

                    restored = self.engine.restore(flushable, session_id)
                    if restored.restored_text:
                        chunk = self.provider.set_stream_delta(
                            chunk,
                            restored.restored_text,
                        )
                        yield f"data: {json.dumps(chunk)}\n\n"

                except json.JSONDecodeError:
                    continue
