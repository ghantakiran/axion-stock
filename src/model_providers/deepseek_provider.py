"""DeepSeek provider — OpenAI-compatible API."""

from __future__ import annotations

from src.model_providers.config import ProviderConfig, ProviderType
from src.model_providers.openai_provider import OpenAIProvider


DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider(OpenAIProvider):
    """Provider for DeepSeek models (V3, R1).

    DeepSeek exposes an OpenAI-compatible API, so this inherits from
    ``OpenAIProvider`` and only overrides the base URL and provider type.
    """

    provider_type = ProviderType.DEEPSEEK

    def __init__(self, config: ProviderConfig):
        # Set DeepSeek base URL if not already overridden
        if not config.base_url:
            config.base_url = DEEPSEEK_BASE_URL
        super().__init__(config)

    def _get_client(self):
        if self._client is None:
            import openai
            self._client = openai.OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )
        return self._client
