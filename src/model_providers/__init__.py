"""Multi-Model AI Provider System.

Provides a unified interface to multiple LLM backends (Claude, OpenAI,
Gemini, DeepSeek, Ollama/Llama) with tool-calling normalization,
fallback chains, and cost estimation.
"""

from src.model_providers.config import (
    MODEL_CATALOG,
    ModelInfo,
    ModelTier,
    ProviderConfig,
    ProviderResponse,
    ProviderType,
    ToolCall,
    get_model_info,
    list_all_models,
    list_models_for_provider,
)
from src.model_providers.base import BaseProvider
from src.model_providers.registry import ProviderRegistry, create_provider
from src.model_providers.router import (
    FAST_CHAIN,
    FLAGSHIP_CHAIN,
    LOCAL_CHAIN,
    FallbackChain,
    ModelRouter,
)

__all__ = [
    # Config
    "ProviderType",
    "ModelTier",
    "ModelInfo",
    "ProviderConfig",
    "ProviderResponse",
    "ToolCall",
    "MODEL_CATALOG",
    "get_model_info",
    "list_all_models",
    "list_models_for_provider",
    # Base
    "BaseProvider",
    # Registry
    "ProviderRegistry",
    "create_provider",
    # Router
    "ModelRouter",
    "FallbackChain",
    "FLAGSHIP_CHAIN",
    "FAST_CHAIN",
    "LOCAL_CHAIN",
]
