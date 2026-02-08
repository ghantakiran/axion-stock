"""OpenAI (GPT) provider implementation."""

from __future__ import annotations

import json
import uuid
from typing import Optional

from src.model_providers.base import BaseProvider
from src.model_providers.config import (
    ProviderConfig,
    ProviderResponse,
    ProviderType,
    ToolCall,
)


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI GPT models (gpt-4o, gpt-4o-mini, o3-mini).

    Also serves as base class for OpenAI-compatible APIs (DeepSeek, Ollama).
    Handles the format differences between Anthropic and OpenAI tool calling.
    """

    provider_type = ProviderType.OPENAI

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        if self._client is None:
            import openai
            kwargs = {"api_key": self.config.api_key}
            if self.config.base_url:
                kwargs["base_url"] = self.config.base_url
            self._client = openai.OpenAI(**kwargs)
        return self._client

    def convert_tools_to_native(self, tools: list[dict]) -> list[dict]:
        """Convert Anthropic tool format to OpenAI function calling format.

        Anthropic:  {"name", "description", "input_schema": {"type": "object", ...}}
        OpenAI:     {"type": "function", "function": {"name", "description", "parameters": ...}}
        """
        native = []
        for tool in tools:
            native.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                },
            })
        return native

    def _convert_messages(self, messages: list[dict], system_prompt: str) -> list[dict]:
        """Convert Anthropic-style messages to OpenAI format.

        Key differences:
        - System prompt becomes a system message
        - Tool results use role='tool' instead of nested tool_result content blocks
        """
        native = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")

            # Handle tool result messages (Anthropic format)
            if role == "user" and isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        native.append({
                            "role": "tool",
                            "tool_call_id": item.get("tool_use_id", str(uuid.uuid4())),
                            "content": item.get("content", ""),
                        })
                continue

            # Handle assistant messages with raw Anthropic content blocks
            if role == "assistant" and isinstance(content, list):
                text_parts = []
                tool_calls = []
                for block in content:
                    if hasattr(block, "type"):
                        if block.type == "text":
                            text_parts.append(block.text)
                        elif block.type == "tool_use":
                            tool_calls.append({
                                "id": block.id,
                                "type": "function",
                                "function": {
                                    "name": block.name,
                                    "arguments": json.dumps(block.input),
                                },
                            })
                    elif isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            tool_calls.append({
                                "id": block.get("id", str(uuid.uuid4())),
                                "type": "function",
                                "function": {
                                    "name": block["name"],
                                    "arguments": json.dumps(block.get("input", {})),
                                },
                            })

                msg_dict = {"role": "assistant", "content": "\n".join(text_parts) or None}
                if tool_calls:
                    msg_dict["tool_calls"] = tool_calls
                native.append(msg_dict)
                continue

            # Standard text messages
            if isinstance(content, str):
                native.append({"role": role, "content": content})
            else:
                native.append({"role": role, "content": str(content)})

        return native

    def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[dict],
        model: str,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        client = self._get_client()
        native_tools = self.convert_tools_to_native(tools)
        native_messages = self._convert_messages(messages, system_prompt)

        kwargs = {
            "model": model,
            "messages": native_messages,
            "max_tokens": max_tokens,
        }
        if native_tools:
            kwargs["tools"] = native_tools

        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        # Extract text
        text = message.content or ""

        # Extract tool calls
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, AttributeError):
                    args = {}
                tool_calls.append(ToolCall(
                    call_id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        finish_reason = choice.finish_reason or "stop"
        # Normalize finish reason to Anthropic-style
        if finish_reason == "tool_calls":
            finish_reason = "tool_use"
        elif finish_reason == "stop":
            finish_reason = "end_turn"

        usage = response.usage

        return ProviderResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=model,
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            raw_response=response,
        )

    def build_tool_result_messages(
        self,
        assistant_message: object,
        tool_results: list[dict],
    ) -> list[dict]:
        """Build OpenAI-format tool result messages.

        OpenAI expects: assistant message with tool_calls, then
        individual role='tool' messages per tool result.
        """
        msgs = []

        # Reconstruct assistant message with tool_calls
        if hasattr(assistant_message, "tool_calls"):
            msgs.append({
                "role": "assistant",
                "content": getattr(assistant_message, "content", None),
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in assistant_message.tool_calls
                ],
            })

        # Tool results
        for tr in tool_results:
            msgs.append({
                "role": "tool",
                "tool_call_id": tr["call_id"],
                "content": tr["output"],
            })

        return msgs

    def is_available(self) -> bool:
        if not self.config.is_configured:
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False
