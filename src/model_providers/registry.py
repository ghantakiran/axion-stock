"""Provider registry — create, cache, and look up provider instances."""

from __future__ import annotations

from typing import Optional

from src.model_providers.base import BaseProvider
from src.model_providers.config import (
    MODEL_CATALOG,
    ModelInfo,
    ProviderConfig,
    ProviderType,
    get_model_info,
    list_all_models,
    list_models_for_provider,
)


# ── Factory ───────────────────────────────────────────────────────────


def create_provider(config: ProviderConfig) -> BaseProvider:
    """Instantiate a provider from its config."""
    if config.provider == ProviderType.ANTHROPIC:
        from src.model_providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(config)
    elif config.provider == ProviderType.OPENAI:
        from src.model_providers.openai_provider import OpenAIProvider
        return OpenAIProvider(config)
    elif config.provider == ProviderType.GEMINI:
        from src.model_providers.gemini_provider import GeminiProvider
        return GeminiProvider(config)
    elif config.provider == ProviderType.DEEPSEEK:
        from src.model_providers.deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(config)
    elif config.provider == ProviderType.OLLAMA:
        from src.model_providers.ollama_provider import OllamaProvider
        return OllamaProvider(config)
    else:
        raise ValueError(f"Unknown provider type: {config.provider}")


# ── Registry singleton ────────────────────────────────────────────────


class ProviderRegistry:
    """Manages provider configs and cached instances.

    Usage::

        registry = ProviderRegistry()
        registry.configure(ProviderConfig(provider=ProviderType.OPENAI, api_key="sk-..."))
        provider = registry.get_provider(ProviderType.OPENAI)
        response = provider.chat(messages, system_prompt, tools, model)
    """

    def __init__(self):
        self._configs: dict[ProviderType, ProviderConfig] = {}
        self._providers: dict[ProviderType, BaseProvider] = {}

    def configure(self, config: ProviderConfig) -> None:
        """Register or update a provider config."""
        self._configs[config.provider] = config
        # Invalidate cached instance
        self._providers.pop(config.provider, None)

    def get_config(self, provider: ProviderType) -> Optional[ProviderConfig]:
        """Get stored config for a provider."""
        return self._configs.get(provider)

    def get_provider(self, provider: ProviderType) -> BaseProvider:
        """Get a cached provider instance. Raises if not configured."""
        if provider not in self._providers:
            config = self._configs.get(provider)
            if not config:
                raise ValueError(
                    f"Provider {provider.value} not configured. "
                    f"Call registry.configure() first."
                )
            self._providers[provider] = create_provider(config)
        return self._providers[provider]

    def get_provider_for_model(self, model_id: str) -> BaseProvider:
        """Look up the model's provider and return the instance."""
        info = get_model_info(model_id)
        if not info:
            raise ValueError(f"Unknown model: {model_id}. Check MODEL_CATALOG.")
        return self.get_provider(info.provider)

    def list_configured(self) -> list[ProviderType]:
        """Return provider types that have been configured."""
        return list(self._configs.keys())

    def list_available(self) -> list[ProviderType]:
        """Return configured providers whose SDKs are importable."""
        available = []
        for ptype, config in self._configs.items():
            try:
                provider = self.get_provider(ptype)
                if provider.is_available():
                    available.append(ptype)
            except Exception:
                pass
        return available

    def list_available_models(self) -> list[ModelInfo]:
        """Return models whose providers are configured and available."""
        available_providers = set(self.list_available())
        return [
            m for m in list_all_models()
            if m.provider in available_providers
        ]

    def is_configured(self, provider: ProviderType) -> bool:
        """Check if a provider has been configured."""
        return provider in self._configs

    def remove(self, provider: ProviderType) -> None:
        """Remove a provider config and cached instance."""
        self._configs.pop(provider, None)
        self._providers.pop(provider, None)

    def clear(self) -> None:
        """Remove all configs and cached instances."""
        self._configs.clear()
        self._providers.clear()
