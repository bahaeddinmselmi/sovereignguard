"""
Tests for provider format adapters (OpenAI, Anthropic, Mistral).
"""

from sovereignguard.proxy.providers import (
    OpenAIAdapter,
    AnthropicAdapter,
    get_provider_adapter,
)
from sovereignguard.config import LLMProvider


class TestOpenAIAdapter:

    def setup_method(self):
        self.adapter = OpenAIAdapter()

    def test_extract_chat_completion_text(self):
        response = {
            "choices": [
                {"message": {"content": "Hello {{SG_EMAIL_abc123}}"}}
            ]
        }
        texts = self.adapter.extract_response_texts(response)
        assert len(texts) == 1
        assert texts[0]["text"] == "Hello {{SG_EMAIL_abc123}}"
        assert texts[0]["path"] == ["choices", 0, "message", "content"]

    def test_extract_legacy_completion_text(self):
        response = {"choices": [{"text": "response text"}]}
        texts = self.adapter.extract_response_texts(response)
        assert len(texts) == 1
        assert texts[0]["text"] == "response text"

    def test_set_response_text(self):
        response = {"choices": [{"message": {"content": "old text"}}]}
        self.adapter.set_response_text(
            response, ["choices", 0, "message", "content"], "new text"
        )
        assert response["choices"][0]["message"]["content"] == "new text"

    def test_extract_stream_delta(self):
        chunk = {"choices": [{"delta": {"content": "hello"}}]}
        assert self.adapter.extract_stream_delta(chunk) == "hello"

    def test_extract_stream_delta_empty(self):
        chunk = {"choices": [{"delta": {}}]}
        assert self.adapter.extract_stream_delta(chunk) is None

    def test_format_error(self):
        error = self.adapter.format_error(500, "test error")
        assert error["error"]["message"] == "test error"
        assert error["error"]["type"] == "server_error"

    def test_empty_response(self):
        texts = self.adapter.extract_response_texts({})
        assert len(texts) == 0

    def test_multiple_choices(self):
        response = {
            "choices": [
                {"message": {"content": "first"}},
                {"message": {"content": "second"}},
            ]
        }
        texts = self.adapter.extract_response_texts(response)
        assert len(texts) == 2


class TestAnthropicAdapter:

    def setup_method(self):
        self.adapter = AnthropicAdapter()

    def test_extract_anthropic_text(self):
        response = {
            "content": [
                {"type": "text", "text": "Hello from Claude"}
            ]
        }
        texts = self.adapter.extract_response_texts(response)
        assert len(texts) == 1
        assert texts[0]["text"] == "Hello from Claude"

    def test_extract_anthropic_ignores_non_text(self):
        response = {
            "content": [
                {"type": "tool_use", "id": "123"},
                {"type": "text", "text": "Result"},
            ]
        }
        texts = self.adapter.extract_response_texts(response)
        assert len(texts) == 1
        assert texts[0]["text"] == "Result"

    def test_set_anthropic_text(self):
        response = {"content": [{"type": "text", "text": "old"}]}
        self.adapter.set_response_text(
            response, ["content", 0, "text"], "new"
        )
        assert response["content"][0]["text"] == "new"

    def test_extract_stream_delta_text(self):
        chunk = {
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "hello"},
        }
        assert self.adapter.extract_stream_delta(chunk) == "hello"

    def test_extract_stream_delta_non_text(self):
        chunk = {"type": "message_start"}
        assert self.adapter.extract_stream_delta(chunk) is None

    def test_format_error(self):
        error = self.adapter.format_error(400, "bad request")
        assert error["type"] == "error"
        assert error["error"]["message"] == "bad request"


class TestProviderFactory:

    def test_openai_adapter(self):
        adapter = get_provider_adapter(LLMProvider.OPENAI)
        assert isinstance(adapter, OpenAIAdapter)

    def test_mistral_uses_openai_adapter(self):
        adapter = get_provider_adapter(LLMProvider.MISTRAL)
        assert isinstance(adapter, OpenAIAdapter)

    def test_anthropic_adapter(self):
        adapter = get_provider_adapter(LLMProvider.ANTHROPIC)
        assert isinstance(adapter, AnthropicAdapter)
