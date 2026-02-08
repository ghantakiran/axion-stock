"""Anthropic (Claude) provider implementation."""

from __future__ import annotations

from src.model_providers.base import BaseProvider
from src.model_providers.config import (
    ProviderConfig,
    ProviderResponse,
    ProviderType,
    ToolCall,
)


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Claude models.

    This is the native format — tools and messages pass through directly
    since the Axion platform was built on the Anthropic API.
    """

    provider_type = ProviderType.ANTHROPIC

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.config.api_key)
        return self._client

    def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[dict],
        model: str,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        client = self._get_client()

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        # Parse response
        text_parts = []
        tool_calls = []

        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    call_id=block.id,
                    name=block.name,
                    arguments=block.input,
                ))

        finish_reason = response.stop_reason or "end_turn"
        usage = getattr(response, "usage", None)

        return ProviderResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=model,
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            raw_response=response,
        )

    def build_tool_result_messages(
        self,
        assistant_message: object,
        tool_results: list[dict],
    ) -> list[dict]:
        """For Anthropic, the assistant content is appended as-is,
        then tool results go in a user message."""
        return [
            {"role": "assistant", "content": assistant_message},
            {"role": "user", "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tr["call_id"],
                    "content": tr["output"],
                }
                for tr in tool_results
            ]},
        ]

    def is_available(self) -> bool:
        if not self.config.is_configured:
            return False
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False
