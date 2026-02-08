"""Agent engine — runs the agentic tool-use loop for a specific agent.

Supports multiple LLM providers via the model_providers system.
Falls back to direct Anthropic SDK when no provider registry is given.
"""

from __future__ import annotations

from typing import Optional

from app.tools import TOOL_DEFINITIONS, execute_tool
from src.agents.config import AgentConfig


class AgentEngine:
    """Executes the agent's agentic loop with tool filtering.

    Supports two modes:
    1. **Direct mode** (default) — uses the Anthropic SDK directly.
       Same behavior as the original ``app/chat.py:get_chat_response``.
    2. **Provider mode** — routes through ``ProviderRegistry`` for
       multi-model support (Claude, GPT, Gemini, DeepSeek, Ollama).
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        provider_registry=None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self._registry = provider_registry

    # ── public API ────────────────────────────────────────────────────

    def get_response(
        self,
        messages: list[dict],
        api_key: str,
        agent_config: AgentConfig,
    ) -> tuple[str, list[dict], list[dict]]:
        """Run the agentic tool-use loop for an agent.

        Returns ``(assistant_text, updated_messages, tool_calls)``
        — same shape as ``get_chat_response`` for drop-in compatibility.

        If a ``provider_registry`` was given and the agent has a
        ``preferred_model``, routes through the multi-provider system.
        Otherwise falls back to direct Anthropic SDK.
        """
        model_id = agent_config.preferred_model or self.model

        # Route through provider system if available
        if self._registry is not None:
            return self._run_with_provider(messages, agent_config, model_id)

        # Direct Anthropic mode (backward-compatible)
        return self._run_anthropic_direct(messages, api_key, agent_config, model_id)

    # ── Provider-based loop ───────────────────────────────────────────

    def _run_with_provider(
        self,
        messages: list[dict],
        agent_config: AgentConfig,
        model_id: str,
    ) -> tuple[str, list[dict], list[dict]]:
        """Agentic loop using the multi-provider system."""
        from src.model_providers.config import get_model_info

        info = get_model_info(model_id)
        if not info:
            raise ValueError(f"Unknown model: {model_id}")

        provider = self._registry.get_provider(info.provider)
        filtered_tools = self._filter_tools(agent_config)
        native_tools = provider.convert_tools_to_native(filtered_tools)
        system_prompt = agent_config.system_prompt
        max_tokens = agent_config.response_style.max_tokens or self.max_tokens

        current_messages = list(messages)
        tool_calls: list[dict] = []

        while True:
            response = provider.chat(
                messages=current_messages,
                system_prompt=system_prompt,
                tools=native_tools if info.supports_tool_use else [],
                model=model_id,
                max_tokens=max_tokens,
            )

            if response.has_tool_calls:
                for tc in response.tool_calls:
                    tool_calls.append({"name": tc.name, "input": tc.arguments})
                    result = execute_tool(tc.name, tc.arguments)

                    # Build follow-up messages in provider-native format
                    result_msgs = provider.build_tool_result_messages(
                        response.raw_response
                        if hasattr(response.raw_response, "content")
                        else response.raw_response,
                        [{"call_id": tc.call_id, "name": tc.name, "output": result}],
                    )
                    current_messages.extend(result_msgs)
            else:
                return response.text, current_messages, tool_calls

    # ── Direct Anthropic loop (backward-compatible) ───────────────────

    def _run_anthropic_direct(
        self,
        messages: list[dict],
        api_key: str,
        agent_config: AgentConfig,
        model_id: str,
    ) -> tuple[str, list[dict], list[dict]]:
        """Original agentic loop using the Anthropic SDK directly."""
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        filtered_tools = self._filter_tools(agent_config)
        system_prompt = agent_config.system_prompt
        max_tokens = agent_config.response_style.max_tokens or self.max_tokens

        current_messages = list(messages)
        tool_calls: list[dict] = []

        while True:
            response = client.messages.create(
                model=model_id,
                max_tokens=max_tokens,
                system=system_prompt,
                tools=filtered_tools,
                messages=current_messages,
            )

            if response.stop_reason == "tool_use":
                assistant_content = response.content
                current_messages.append({"role": "assistant", "content": assistant_content})

                tool_results = []
                for block in assistant_content:
                    if block.type == "tool_use":
                        tool_calls.append({"name": block.name, "input": block.input})
                        result = execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                current_messages.append({"role": "user", "content": tool_results})
            else:
                text_parts = []
                for block in response.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)

                final_text = "\n".join(text_parts)
                return final_text, current_messages, tool_calls

    # ── private helpers ───────────────────────────────────────────────

    def _filter_tools(self, agent_config: AgentConfig) -> list[dict]:
        """Return TOOL_DEFINITIONS filtered to tools with non-zero weight."""
        available = set(agent_config.available_tool_names)
        if not available:
            return list(TOOL_DEFINITIONS)
        return [t for t in TOOL_DEFINITIONS if t["name"] in available]
