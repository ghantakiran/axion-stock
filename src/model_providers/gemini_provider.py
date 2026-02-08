"""Google Gemini provider implementation."""

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


class GeminiProvider(BaseProvider):
    """Provider for Google Gemini models (gemini-2.0-flash, gemini-1.5-pro).

    Uses the google-generativeai SDK. Handles format conversion between
    Anthropic-style tool definitions and Gemini's function declarations.
    """

    provider_type = ProviderType.GEMINI

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._model_cache: dict = {}

    def _get_model(self, model: str):
        if model not in self._model_cache:
            import google.generativeai as genai
            genai.configure(api_key=self.config.api_key)
            self._model_cache[model] = genai.GenerativeModel(model)
        return self._model_cache[model]

    def convert_tools_to_native(self, tools: list[dict]) -> list:
        """Convert Anthropic tool format to Gemini function declarations.

        Gemini format uses ``function_declarations`` inside a tools wrapper.
        """
        import google.generativeai as genai

        declarations = []
        for tool in tools:
            schema = tool.get("input_schema", {})
            # Gemini doesn't support top-level 'required' the same way;
            # we pass it through the schema
            params = {
                "type_": "OBJECT",
                "properties": {},
            }
            for prop_name, prop_def in schema.get("properties", {}).items():
                prop_type = prop_def.get("type", "string").upper()
                if prop_type == "INTEGER":
                    prop_type = "NUMBER"
                if prop_type == "ARRAY":
                    prop_type = "STRING"  # Simplify for compatibility
                params["properties"][prop_name] = {
                    "type_": prop_type,
                    "description": prop_def.get("description", ""),
                }

            declarations.append(genai.protos.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=genai.protos.Schema(**params) if params["properties"] else None,
            ))

        return [genai.protos.Tool(function_declarations=declarations)]

    def _convert_messages(self, messages: list[dict], system_prompt: str) -> list:
        """Convert Anthropic-style messages to Gemini Content format."""
        import google.generativeai as genai

        contents = []
        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")

            # Map roles
            gemini_role = "model" if role == "assistant" else "user"

            if isinstance(content, str):
                contents.append(genai.protos.Content(
                    role=gemini_role,
                    parts=[genai.protos.Part(text=content)],
                ))
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "tool_result":
                            parts.append(genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=item.get("tool_name", "unknown"),
                                    response={"result": item.get("content", "")},
                                )
                            ))
                        elif item.get("type") == "text":
                            parts.append(genai.protos.Part(text=item.get("text", "")))
                    elif hasattr(item, "type"):
                        if item.type == "text":
                            parts.append(genai.protos.Part(text=item.text))
                if parts:
                    contents.append(genai.protos.Content(role=gemini_role, parts=parts))

        return contents

    def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[dict],
        model: str,
        max_tokens: int = 4096,
    ) -> ProviderResponse:
        import google.generativeai as genai

        genai.configure(api_key=self.config.api_key)

        native_tools = self.convert_tools_to_native(tools) if tools else None
        contents = self._convert_messages(messages, system_prompt)

        gen_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
        )

        gen_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
        )

        response = gen_model.generate_content(
            contents=contents,
            tools=native_tools,
            generation_config=gen_config,
        )

        # Parse response
        text_parts = []
        tool_calls = []

        if response.candidates:
            candidate = response.candidates[0]
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    tool_calls.append(ToolCall(
                        call_id=str(uuid.uuid4()),
                        name=fc.name,
                        arguments=dict(fc.args) if fc.args else {},
                    ))

        finish_reason = "tool_use" if tool_calls else "end_turn"

        return ProviderResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=model,
            raw_response=response,
        )

    def build_tool_result_messages(
        self,
        assistant_message: object,
        tool_results: list[dict],
    ) -> list[dict]:
        """Build Gemini-style tool result messages."""
        # For Gemini, tool results are sent as function_response parts
        results = []
        for tr in tool_results:
            results.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_name": tr.get("name", "unknown"),
                    "content": tr["output"],
                }],
            })
        return results

    def is_available(self) -> bool:
        if not self.config.is_configured:
            return False
        try:
            import google.generativeai  # noqa: F401
            return True
        except ImportError:
            return False
