"""
Multi-Provider Format Adapters

Handles the differences between LLM API response formats.
Each provider (OpenAI, Anthropic, Mistral) structures responses differently.
This module normalizes the mask/restore logic across providers.

Supported providers:
- OpenAI: choices[].message.content
- Anthropic: content[].text
- Mistral: choices[].message.content (OpenAI-compatible)
"""

import logging
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

from sovereignguard.config import LLMProvider

logger = logging.getLogger(__name__)


class BaseProviderAdapter(ABC):
    """Base class for provider-specific response handling."""

    @abstractmethod
    def extract_response_texts(self, response: Dict) -> List[Dict[str, Any]]:
        """
        Extract text content from provider response.
        Returns list of dicts: [{"path": ["choices", 0, "message", "content"], "text": "..."}]
        """
        pass

    @abstractmethod
    def set_response_text(self, response: Dict, path: List, new_text: str) -> Dict:
        """Set text at the given path in the response."""
        pass

    @abstractmethod
    def extract_stream_delta(self, chunk: Dict) -> Optional[str]:
        """Extract delta text content from a streaming chunk."""
        pass

    @abstractmethod
    def set_stream_delta(self, chunk: Dict, new_text: str) -> Dict:
        """Set delta text in a streaming chunk."""
        pass

    @abstractmethod
    def format_error(self, status_code: int, message: str) -> Dict:
        """Format an error response in the provider's format."""
        pass


class OpenAIAdapter(BaseProviderAdapter):
    """Handles OpenAI and OpenAI-compatible APIs (Mistral, etc.)."""

    def extract_response_texts(self, response: Dict) -> List[Dict[str, Any]]:
        texts = []
        for i, choice in enumerate(response.get("choices", [])):
            # Chat completions format
            msg = choice.get("message", {})
            if isinstance(msg.get("content"), str):
                texts.append({
                    "path": ["choices", i, "message", "content"],
                    "text": msg["content"],
                })
            # Legacy completions format
            if isinstance(choice.get("text"), str):
                texts.append({
                    "path": ["choices", i, "text"],
                    "text": choice["text"],
                })
        return texts

    def set_response_text(self, response: Dict, path: List, new_text: str) -> Dict:
        obj = response
        for key in path[:-1]:
            obj = obj[key]
        obj[path[-1]] = new_text
        return response

    def extract_stream_delta(self, chunk: Dict) -> Optional[str]:
        choices = chunk.get("choices", [{}])
        if not choices:
            return None
        return choices[0].get("delta", {}).get("content")

    def set_stream_delta(self, chunk: Dict, new_text: str) -> Dict:
        if chunk.get("choices"):
            chunk["choices"][0]["delta"]["content"] = new_text
        return chunk

    def format_error(self, status_code: int, message: str) -> Dict:
        return {
            "error": {
                "message": message,
                "type": "server_error",
                "code": str(status_code),
            }
        }


class AnthropicAdapter(BaseProviderAdapter):
    """Handles Anthropic Claude API format."""

    def extract_response_texts(self, response: Dict) -> List[Dict[str, Any]]:
        texts = []
        for i, block in enumerate(response.get("content", [])):
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                texts.append({
                    "path": ["content", i, "text"],
                    "text": block["text"],
                })
        return texts

    def set_response_text(self, response: Dict, path: List, new_text: str) -> Dict:
        obj = response
        for key in path[:-1]:
            obj = obj[key]
        obj[path[-1]] = new_text
        return response

    def extract_stream_delta(self, chunk: Dict) -> Optional[str]:
        if chunk.get("type") == "content_block_delta":
            delta = chunk.get("delta", {})
            if delta.get("type") == "text_delta":
                return delta.get("text")
        return None

    def set_stream_delta(self, chunk: Dict, new_text: str) -> Dict:
        if chunk.get("type") == "content_block_delta":
            chunk["delta"]["text"] = new_text
        return chunk

    def format_error(self, status_code: int, message: str) -> Dict:
        return {
            "type": "error",
            "error": {
                "type": "api_error",
                "message": message,
            },
        }


def get_provider_adapter(provider: LLMProvider) -> BaseProviderAdapter:
    """Get the appropriate adapter for the configured provider."""
    adapters = {
        LLMProvider.OPENAI: OpenAIAdapter,
        LLMProvider.MISTRAL: OpenAIAdapter,  # Mistral uses OpenAI-compatible format
        LLMProvider.ANTHROPIC: AnthropicAdapter,
        LLMProvider.CUSTOM: OpenAIAdapter,  # Default to OpenAI format for custom
    }
    adapter_class = adapters.get(provider, OpenAIAdapter)
    return adapter_class()
