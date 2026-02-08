"""Abstract base class for all LLM providers."""

from __future__ import annotations

import abc
from typing import Optional

from src.model_providers.config import (
    ProviderConfig,
    ProviderResponse,
    ProviderType,
    ToolCall,
)


class BaseProvider(abc.ABC):
    """Interface that every model provider must implement.

    Subclasses handle:
    1. Converting tool definitions to provider-native format
    2. Converting messages to provider-native format
    3. Parsing the response into a normalized ``ProviderResponse``
    """

    provider_type: ProviderType

    def __init__(self, config: ProviderConfig):
        self.config = config

    # ── Abstract methods ──────────────────────────────────────────────

    @abc.abstractmethod
    def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[dict],
        model: str,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        """Send a chat request and return a normalized response.

        Args:
            messages: Conversation in Anthropic-style format
                      (``[{"role": "user"|"assistant", "content": ...}]``).
            system_prompt: System-level instructions.
            tools: Tool definitions in Anthropic format
                   (``[{"name": ..., "description": ..., "input_schema": ...}]``).
            model: Model ID string.
            max_tokens: Maximum output tokens.

        Returns:
            ``ProviderResponse`` with normalized text / tool_calls.
        """

    @abc.abstractmethod
    def build_tool_result_messages(
        self,
        assistant_message: object,
        tool_results: list[dict],
    ) -> list[dict]:
        """Construct the follow-up messages after tool execution.

        Each provider formats tool results differently.
        Returns messages in the provider's native format that can be
        appended to the conversation for the next ``chat()`` call.
        """

    # ── Shared helpers ────────────────────────────────────────────────

    def is_available(self) -> bool:
        """True if the provider SDK is importable and config looks valid."""
        return self.config.is_configured

    def convert_tools_to_native(self, tools: list[dict]) -> list:
        """Convert Anthropic-format tool definitions to this provider's format.

        Default implementation returns tools unchanged (suitable for Anthropic).
        Override in subclasses for OpenAI, Gemini, etc.
        """
        return tools

    @staticmethod
    def _extract_text(parts) -> str:
        """Safely join text parts."""
        if isinstance(parts, str):
            return parts
        return "\n".join(str(p) for p in parts if p)
