"""Model router — selects models and implements fallback chains."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.model_providers.config import (
    MODEL_CATALOG,
    ModelInfo,
    ModelTier,
    ProviderResponse,
    ProviderType,
    get_model_info,
)
from src.model_providers.registry import ProviderRegistry


@dataclass
class FallbackChain:
    """Ordered list of model IDs to try. First success wins."""

    models: list[str] = field(default_factory=list)

    def add(self, model_id: str) -> "FallbackChain":
        if model_id not in self.models:
            self.models.append(model_id)
        return self


# ── Pre-built fallback chains ─────────────────────────────────────────

FLAGSHIP_CHAIN = FallbackChain(models=[
    "claude-sonnet-4-20250514",
    "gpt-4o",
    "gemini-1.5-pro",
    "deepseek-chat",
])

FAST_CHAIN = FallbackChain(models=[
    "claude-haiku-4-5-20251001",
    "gpt-4o-mini",
    "gemini-2.0-flash",
    "deepseek-chat",
])

LOCAL_CHAIN = FallbackChain(models=[
    "llama3.3",
    "mistral",
    "qwen2.5",
])


class ModelRouter:
    """Selects the best model and handles fallback on failure.

    Usage::

        router = ModelRouter(registry)
        response = router.chat_with_fallback(
            messages, system_prompt, tools, chain=FLAGSHIP_CHAIN
        )
    """

    def __init__(self, registry: ProviderRegistry):
        self.registry = registry

    def select_model(
        self,
        preferred_model: Optional[str] = None,
        tier: Optional[ModelTier] = None,
        provider: Optional[ProviderType] = None,
    ) -> Optional[str]:
        """Pick the best available model given constraints.

        Priority: preferred_model > tier filter > provider filter > first available.
        """
        # Try preferred model first
        if preferred_model:
            info = get_model_info(preferred_model)
            if info and self.registry.is_configured(info.provider):
                return preferred_model

        available = self.registry.list_available_models()
        if not available:
            return None

        # Filter by tier
        if tier:
            candidates = [m for m in available if m.tier == tier]
            if candidates:
                return candidates[0].model_id

        # Filter by provider
        if provider:
            candidates = [m for m in available if m.provider == provider]
            if candidates:
                return candidates[0].model_id

        # Return first available
        return available[0].model_id

    def chat_with_fallback(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[dict],
        chain: Optional[FallbackChain] = None,
        preferred_model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> tuple[ProviderResponse, str]:
        """Try models in order until one succeeds.

        Returns ``(ProviderResponse, model_id_used)``.
        Raises the last error if all models fail.
        """
        models_to_try = []

        # Start with preferred model
        if preferred_model:
            models_to_try.append(preferred_model)

        # Add chain models
        if chain:
            for m in chain.models:
                if m not in models_to_try:
                    models_to_try.append(m)

        # Fallback: any configured model
        if not models_to_try:
            available = self.registry.list_available_models()
            models_to_try = [m.model_id for m in available]

        if not models_to_try:
            raise RuntimeError("No models configured. Add at least one provider API key.")

        last_error = None
        for model_id in models_to_try:
            info = get_model_info(model_id)
            if not info:
                continue

            if not self.registry.is_configured(info.provider):
                continue

            try:
                provider = self.registry.get_provider(info.provider)
                if not provider.is_available():
                    continue

                native_tools = provider.convert_tools_to_native(tools)
                response = provider.chat(
                    messages=messages,
                    system_prompt=system_prompt,
                    tools=native_tools if info.supports_tool_use else [],
                    model=model_id,
                    max_tokens=max_tokens,
                )
                return response, model_id

            except Exception as e:
                last_error = e
                continue

        raise last_error or RuntimeError("All models in fallback chain failed.")

    def estimate_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for a given model usage."""
        info = get_model_info(model_id)
        if not info:
            return 0.0
        return (
            (input_tokens / 1000) * info.cost_per_1k_input
            + (output_tokens / 1000) * info.cost_per_1k_output
        )
