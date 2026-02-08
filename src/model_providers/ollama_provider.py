"""Ollama provider — local LLM via OpenAI-compatible API.

Supports Llama, Mistral, Qwen, CodeLlama, and any model served by Ollama.
"""

from __future__ import annotations

from src.model_providers.config import ProviderConfig, ProviderType
from src.model_providers.openai_provider import OpenAIProvider


DEFAULT_OLLAMA_URL = "http://localhost:11434/v1"


class OllamaProvider(OpenAIProvider):
    """Provider for local models via Ollama (Llama 3.3, Mistral, Qwen, etc.).

    Ollama exposes an OpenAI-compatible endpoint at ``/v1``, so this
    inherits from ``OpenAIProvider`` with the local URL.
    No API key is needed.
    """

    provider_type = ProviderType.OLLAMA

    def __init__(self, config: ProviderConfig):
        if not config.base_url:
            config.base_url = DEFAULT_OLLAMA_URL
        if not config.api_key:
            config.api_key = "ollama"  # Placeholder; Ollama doesn't check
        super().__init__(config)

    def _get_client(self):
        if self._client is None:
            import openai
            self._client = openai.OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )
        return self._client

    def is_available(self) -> bool:
        """Check if Ollama is running locally."""
        try:
            import openai  # noqa: F401
        except ImportError:
            return False

        try:
            import urllib.request
            url = (self.config.base_url or DEFAULT_OLLAMA_URL).replace("/v1", "")
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False
