"""Configuration types for multi-model AI provider system."""

import enum
from dataclasses import dataclass, field
from typing import Optional


class ProviderType(enum.Enum):
    """Supported LLM provider backends."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"


class ModelTier(enum.Enum):
    """Model capability tiers for routing."""

    FLAGSHIP = "flagship"     # Best quality (Claude Opus, GPT-4o, Gemini Pro)
    STANDARD = "standard"     # Good balance  (Claude Sonnet, GPT-4o-mini)
    FAST = "fast"             # Speed-first  (Claude Haiku, Gemini Flash)
    LOCAL = "local"           # On-device    (Ollama Llama, Mistral)


@dataclass
class ModelInfo:
    """Metadata for a specific model."""

    model_id: str
    provider: ProviderType
    display_name: str
    tier: ModelTier
    context_window: int = 128_000
    max_output_tokens: int = 4096
    supports_tool_use: bool = True
    supports_vision: bool = False
    cost_per_1k_input: float = 0.0   # USD per 1K input tokens
    cost_per_1k_output: float = 0.0  # USD per 1K output tokens


@dataclass
class ProviderConfig:
    """Connection configuration for a provider."""

    provider: ProviderType
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    timeout_seconds: int = 60
    max_retries: int = 2
    extra: dict = field(default_factory=dict)

    @property
    def is_configured(self) -> bool:
        """True if the provider has enough config to make requests."""
        if self.provider == ProviderType.OLLAMA:
            return True  # No API key needed for local Ollama
        return bool(self.api_key)


@dataclass
class ToolCall:
    """Normalized tool call extracted from any provider's response."""

    call_id: str
    name: str
    arguments: dict


@dataclass
class ProviderResponse:
    """Normalized response from any provider."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "end_turn"
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    raw_response: object = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


# ── Model catalog ─────────────────────────────────────────────────────

MODEL_CATALOG: dict[str, ModelInfo] = {
    # Anthropic
    "claude-opus-4-6": ModelInfo(
        model_id="claude-opus-4-6",
        provider=ProviderType.ANTHROPIC,
        display_name="Claude Opus 4.6",
        tier=ModelTier.FLAGSHIP,
        context_window=200_000,
        max_output_tokens=32_000,
        supports_vision=True,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
    ),
    "claude-sonnet-4-5-20250929": ModelInfo(
        model_id="claude-sonnet-4-5-20250929",
        provider=ProviderType.ANTHROPIC,
        display_name="Claude Sonnet 4.5",
        tier=ModelTier.STANDARD,
        context_window=200_000,
        max_output_tokens=16_000,
        supports_vision=True,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
    ),
    "claude-sonnet-4-20250514": ModelInfo(
        model_id="claude-sonnet-4-20250514",
        provider=ProviderType.ANTHROPIC,
        display_name="Claude Sonnet 4",
        tier=ModelTier.STANDARD,
        context_window=200_000,
        max_output_tokens=8_192,
        supports_vision=True,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
    ),
    "claude-haiku-4-5-20251001": ModelInfo(
        model_id="claude-haiku-4-5-20251001",
        provider=ProviderType.ANTHROPIC,
        display_name="Claude Haiku 4.5",
        tier=ModelTier.FAST,
        context_window=200_000,
        max_output_tokens=8_192,
        supports_vision=True,
        cost_per_1k_input=0.0008,
        cost_per_1k_output=0.004,
    ),
    # OpenAI
    "gpt-4o": ModelInfo(
        model_id="gpt-4o",
        provider=ProviderType.OPENAI,
        display_name="GPT-4o",
        tier=ModelTier.FLAGSHIP,
        context_window=128_000,
        max_output_tokens=16_384,
        supports_vision=True,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.015,
    ),
    "gpt-4o-mini": ModelInfo(
        model_id="gpt-4o-mini",
        provider=ProviderType.OPENAI,
        display_name="GPT-4o Mini",
        tier=ModelTier.FAST,
        context_window=128_000,
        max_output_tokens=16_384,
        supports_vision=True,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    ),
    "o3-mini": ModelInfo(
        model_id="o3-mini",
        provider=ProviderType.OPENAI,
        display_name="o3-mini",
        tier=ModelTier.STANDARD,
        context_window=128_000,
        max_output_tokens=65_536,
        supports_tool_use=True,
        cost_per_1k_input=0.0011,
        cost_per_1k_output=0.0044,
    ),
    # Google Gemini
    "gemini-2.0-flash": ModelInfo(
        model_id="gemini-2.0-flash",
        provider=ProviderType.GEMINI,
        display_name="Gemini 2.0 Flash",
        tier=ModelTier.FAST,
        context_window=1_000_000,
        max_output_tokens=8_192,
        supports_vision=True,
        cost_per_1k_input=0.0001,
        cost_per_1k_output=0.0004,
    ),
    "gemini-1.5-pro": ModelInfo(
        model_id="gemini-1.5-pro",
        provider=ProviderType.GEMINI,
        display_name="Gemini 1.5 Pro",
        tier=ModelTier.FLAGSHIP,
        context_window=2_000_000,
        max_output_tokens=8_192,
        supports_vision=True,
        cost_per_1k_input=0.00125,
        cost_per_1k_output=0.005,
    ),
    # DeepSeek
    "deepseek-chat": ModelInfo(
        model_id="deepseek-chat",
        provider=ProviderType.DEEPSEEK,
        display_name="DeepSeek V3",
        tier=ModelTier.STANDARD,
        context_window=64_000,
        max_output_tokens=8_192,
        cost_per_1k_input=0.00027,
        cost_per_1k_output=0.0011,
    ),
    "deepseek-reasoner": ModelInfo(
        model_id="deepseek-reasoner",
        provider=ProviderType.DEEPSEEK,
        display_name="DeepSeek R1",
        tier=ModelTier.FLAGSHIP,
        context_window=64_000,
        max_output_tokens=8_192,
        supports_tool_use=False,
        cost_per_1k_input=0.00055,
        cost_per_1k_output=0.0022,
    ),
    # Ollama (local)
    "llama3.3": ModelInfo(
        model_id="llama3.3",
        provider=ProviderType.OLLAMA,
        display_name="Llama 3.3 70B",
        tier=ModelTier.LOCAL,
        context_window=128_000,
        max_output_tokens=4_096,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
    ),
    "mistral": ModelInfo(
        model_id="mistral",
        provider=ProviderType.OLLAMA,
        display_name="Mistral 7B",
        tier=ModelTier.LOCAL,
        context_window=32_000,
        max_output_tokens=4_096,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
    ),
    "qwen2.5": ModelInfo(
        model_id="qwen2.5",
        provider=ProviderType.OLLAMA,
        display_name="Qwen 2.5",
        tier=ModelTier.LOCAL,
        context_window=128_000,
        max_output_tokens=4_096,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
    ),
}


def get_model_info(model_id: str) -> Optional[ModelInfo]:
    """Look up model info. Returns None if unknown."""
    return MODEL_CATALOG.get(model_id)


def list_models_for_provider(provider: ProviderType) -> list[ModelInfo]:
    """Return all catalog entries for a given provider."""
    return [m for m in MODEL_CATALOG.values() if m.provider == provider]


def list_all_models() -> list[ModelInfo]:
    """Return all models in the catalog."""
    return list(MODEL_CATALOG.values())
