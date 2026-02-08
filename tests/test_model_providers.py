"""Tests for PRD-132: Multi-Model AI Provider System."""

import json
from unittest.mock import MagicMock, patch

import pytest

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


# ── Sample tool definitions in Anthropic format ──────────────────────

SAMPLE_TOOLS = [
    {
        "name": "analyze_stock",
        "description": "Analyze a stock using factors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_stock_quote",
        "description": "Get current quote.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
            },
            "required": ["ticker"],
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════
# Test Provider Enums
# ═══════════════════════════════════════════════════════════════════════


class TestProviderEnums:
    """Test enum definitions."""

    def test_provider_type_has_five_members(self):
        assert len(ProviderType) == 5

    def test_provider_types(self):
        assert ProviderType.ANTHROPIC.value == "anthropic"
        assert ProviderType.OPENAI.value == "openai"
        assert ProviderType.GEMINI.value == "gemini"
        assert ProviderType.DEEPSEEK.value == "deepseek"
        assert ProviderType.OLLAMA.value == "ollama"

    def test_model_tier_has_four_members(self):
        assert len(ModelTier) == 4

    def test_model_tiers(self):
        assert ModelTier.FLAGSHIP.value == "flagship"
        assert ModelTier.STANDARD.value == "standard"
        assert ModelTier.FAST.value == "fast"
        assert ModelTier.LOCAL.value == "local"


# ═══════════════════════════════════════════════════════════════════════
# Test Model Catalog
# ═══════════════════════════════════════════════════════════════════════


class TestModelCatalog:
    """Test the static model catalog."""

    def test_catalog_has_models(self):
        assert len(MODEL_CATALOG) >= 14

    def test_claude_sonnet_in_catalog(self):
        info = get_model_info("claude-sonnet-4-20250514")
        assert info is not None
        assert info.provider == ProviderType.ANTHROPIC
        assert info.tier == ModelTier.STANDARD

    def test_gpt4o_in_catalog(self):
        info = get_model_info("gpt-4o")
        assert info is not None
        assert info.provider == ProviderType.OPENAI
        assert info.tier == ModelTier.FLAGSHIP

    def test_gemini_flash_in_catalog(self):
        info = get_model_info("gemini-2.0-flash")
        assert info is not None
        assert info.provider == ProviderType.GEMINI

    def test_deepseek_chat_in_catalog(self):
        info = get_model_info("deepseek-chat")
        assert info is not None
        assert info.provider == ProviderType.DEEPSEEK

    def test_llama_in_catalog(self):
        info = get_model_info("llama3.3")
        assert info is not None
        assert info.provider == ProviderType.OLLAMA
        assert info.cost_per_1k_input == 0.0

    def test_unknown_model_returns_none(self):
        assert get_model_info("nonexistent-model") is None

    def test_list_all_models(self):
        models = list_all_models()
        assert len(models) >= 14
        assert all(isinstance(m, ModelInfo) for m in models)

    def test_list_models_for_anthropic(self):
        models = list_models_for_provider(ProviderType.ANTHROPIC)
        assert len(models) >= 3
        assert all(m.provider == ProviderType.ANTHROPIC for m in models)

    def test_list_models_for_openai(self):
        models = list_models_for_provider(ProviderType.OPENAI)
        assert len(models) >= 2

    def test_list_models_for_ollama(self):
        models = list_models_for_provider(ProviderType.OLLAMA)
        assert len(models) >= 2

    def test_all_models_have_display_name(self):
        for model in list_all_models():
            assert model.display_name
            assert len(model.display_name) > 3

    def test_all_models_have_context_window(self):
        for model in list_all_models():
            assert model.context_window > 0


# ═══════════════════════════════════════════════════════════════════════
# Test ProviderConfig
# ═══════════════════════════════════════════════════════════════════════


class TestProviderConfig:
    """Test ProviderConfig dataclass."""

    def test_creation(self):
        cfg = ProviderConfig(provider=ProviderType.OPENAI, api_key="sk-test")
        assert cfg.provider == ProviderType.OPENAI
        assert cfg.api_key == "sk-test"

    def test_is_configured_with_key(self):
        cfg = ProviderConfig(provider=ProviderType.OPENAI, api_key="sk-test")
        assert cfg.is_configured

    def test_is_not_configured_without_key(self):
        cfg = ProviderConfig(provider=ProviderType.OPENAI)
        assert not cfg.is_configured

    def test_ollama_configured_without_key(self):
        cfg = ProviderConfig(provider=ProviderType.OLLAMA)
        assert cfg.is_configured  # Ollama doesn't need an API key

    def test_default_timeout(self):
        cfg = ProviderConfig(provider=ProviderType.ANTHROPIC)
        assert cfg.timeout_seconds == 60

    def test_custom_base_url(self):
        cfg = ProviderConfig(
            provider=ProviderType.DEEPSEEK,
            api_key="sk-test",
            base_url="https://custom.api.com",
        )
        assert cfg.base_url == "https://custom.api.com"


# ═══════════════════════════════════════════════════════════════════════
# Test ProviderResponse / ToolCall
# ═══════════════════════════════════════════════════════════════════════


class TestProviderResponse:
    """Test normalized response types."""

    def test_tool_call_creation(self):
        tc = ToolCall(call_id="abc", name="analyze_stock", arguments={"ticker": "AAPL"})
        assert tc.call_id == "abc"
        assert tc.name == "analyze_stock"
        assert tc.arguments["ticker"] == "AAPL"

    def test_response_without_tools(self):
        resp = ProviderResponse(text="Hello", finish_reason="end_turn")
        assert not resp.has_tool_calls
        assert resp.text == "Hello"

    def test_response_with_tools(self):
        tc = ToolCall(call_id="1", name="test", arguments={})
        resp = ProviderResponse(text="", tool_calls=[tc], finish_reason="tool_use")
        assert resp.has_tool_calls
        assert len(resp.tool_calls) == 1

    def test_response_defaults(self):
        resp = ProviderResponse()
        assert resp.text == ""
        assert resp.tool_calls == []
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0


# ═══════════════════════════════════════════════════════════════════════
# Test OpenAI Provider Tool Conversion
# ═══════════════════════════════════════════════════════════════════════


class TestOpenAIToolConversion:
    """Test Anthropic → OpenAI tool format conversion."""

    def setup_method(self):
        from src.model_providers.openai_provider import OpenAIProvider
        cfg = ProviderConfig(provider=ProviderType.OPENAI, api_key="test")
        self.provider = OpenAIProvider(cfg)

    def test_converts_to_function_format(self):
        native = self.provider.convert_tools_to_native(SAMPLE_TOOLS)
        assert len(native) == 2
        assert native[0]["type"] == "function"
        assert native[0]["function"]["name"] == "analyze_stock"

    def test_preserves_description(self):
        native = self.provider.convert_tools_to_native(SAMPLE_TOOLS)
        assert native[0]["function"]["description"] == "Analyze a stock using factors."

    def test_converts_input_schema_to_parameters(self):
        native = self.provider.convert_tools_to_native(SAMPLE_TOOLS)
        params = native[0]["function"]["parameters"]
        assert params["type"] == "object"
        assert "ticker" in params["properties"]

    def test_preserves_required_fields(self):
        native = self.provider.convert_tools_to_native(SAMPLE_TOOLS)
        params = native[0]["function"]["parameters"]
        assert "ticker" in params["required"]

    def test_empty_tools(self):
        native = self.provider.convert_tools_to_native([])
        assert native == []


# ═══════════════════════════════════════════════════════════════════════
# Test DeepSeek Provider
# ═══════════════════════════════════════════════════════════════════════


class TestDeepSeekProvider:
    """Test DeepSeek provider inherits from OpenAI."""

    def test_sets_deepseek_base_url(self):
        from src.model_providers.deepseek_provider import DeepSeekProvider, DEEPSEEK_BASE_URL
        cfg = ProviderConfig(provider=ProviderType.DEEPSEEK, api_key="test")
        provider = DeepSeekProvider(cfg)
        assert provider.config.base_url == DEEPSEEK_BASE_URL

    def test_respects_custom_base_url(self):
        from src.model_providers.deepseek_provider import DeepSeekProvider
        cfg = ProviderConfig(
            provider=ProviderType.DEEPSEEK,
            api_key="test",
            base_url="https://custom.deepseek.com",
        )
        provider = DeepSeekProvider(cfg)
        assert provider.config.base_url == "https://custom.deepseek.com"

    def test_inherits_tool_conversion(self):
        from src.model_providers.deepseek_provider import DeepSeekProvider
        cfg = ProviderConfig(provider=ProviderType.DEEPSEEK, api_key="test")
        provider = DeepSeekProvider(cfg)
        native = provider.convert_tools_to_native(SAMPLE_TOOLS)
        assert native[0]["type"] == "function"


# ═══════════════════════════════════════════════════════════════════════
# Test Ollama Provider
# ═══════════════════════════════════════════════════════════════════════


class TestOllamaProvider:
    """Test Ollama provider inherits from OpenAI."""

    def test_sets_local_url(self):
        from src.model_providers.ollama_provider import OllamaProvider, DEFAULT_OLLAMA_URL
        cfg = ProviderConfig(provider=ProviderType.OLLAMA)
        provider = OllamaProvider(cfg)
        assert provider.config.base_url == DEFAULT_OLLAMA_URL

    def test_sets_placeholder_api_key(self):
        from src.model_providers.ollama_provider import OllamaProvider
        cfg = ProviderConfig(provider=ProviderType.OLLAMA)
        provider = OllamaProvider(cfg)
        assert provider.config.api_key == "ollama"

    def test_inherits_tool_conversion(self):
        from src.model_providers.ollama_provider import OllamaProvider
        cfg = ProviderConfig(provider=ProviderType.OLLAMA)
        provider = OllamaProvider(cfg)
        native = provider.convert_tools_to_native(SAMPLE_TOOLS)
        assert native[0]["type"] == "function"


# ═══════════════════════════════════════════════════════════════════════
# Test Provider Registry
# ═══════════════════════════════════════════════════════════════════════


class TestProviderRegistry:
    """Test ProviderRegistry CRUD and lookup."""

    def test_empty_registry(self):
        reg = ProviderRegistry()
        assert reg.list_configured() == []

    def test_configure_provider(self):
        reg = ProviderRegistry()
        reg.configure(ProviderConfig(provider=ProviderType.OPENAI, api_key="test"))
        assert reg.is_configured(ProviderType.OPENAI)
        assert not reg.is_configured(ProviderType.ANTHROPIC)

    def test_get_config(self):
        reg = ProviderRegistry()
        cfg = ProviderConfig(provider=ProviderType.OPENAI, api_key="sk-test")
        reg.configure(cfg)
        retrieved = reg.get_config(ProviderType.OPENAI)
        assert retrieved is not None
        assert retrieved.api_key == "sk-test"

    def test_get_config_unconfigured(self):
        reg = ProviderRegistry()
        assert reg.get_config(ProviderType.OPENAI) is None

    def test_get_provider(self):
        reg = ProviderRegistry()
        reg.configure(ProviderConfig(provider=ProviderType.OPENAI, api_key="test"))
        provider = reg.get_provider(ProviderType.OPENAI)
        assert provider is not None

    def test_get_provider_unconfigured_raises(self):
        reg = ProviderRegistry()
        with pytest.raises(ValueError, match="not configured"):
            reg.get_provider(ProviderType.OPENAI)

    def test_get_provider_for_model(self):
        reg = ProviderRegistry()
        reg.configure(ProviderConfig(provider=ProviderType.OPENAI, api_key="test"))
        provider = reg.get_provider_for_model("gpt-4o")
        assert provider is not None

    def test_get_provider_for_unknown_model(self):
        reg = ProviderRegistry()
        with pytest.raises(ValueError, match="Unknown model"):
            reg.get_provider_for_model("nonexistent")

    def test_list_configured(self):
        reg = ProviderRegistry()
        reg.configure(ProviderConfig(provider=ProviderType.OPENAI, api_key="a"))
        reg.configure(ProviderConfig(provider=ProviderType.ANTHROPIC, api_key="b"))
        assert len(reg.list_configured()) == 2

    def test_remove_provider(self):
        reg = ProviderRegistry()
        reg.configure(ProviderConfig(provider=ProviderType.OPENAI, api_key="test"))
        reg.remove(ProviderType.OPENAI)
        assert not reg.is_configured(ProviderType.OPENAI)

    def test_clear_all(self):
        reg = ProviderRegistry()
        reg.configure(ProviderConfig(provider=ProviderType.OPENAI, api_key="a"))
        reg.configure(ProviderConfig(provider=ProviderType.ANTHROPIC, api_key="b"))
        reg.clear()
        assert reg.list_configured() == []

    def test_reconfigure_invalidates_cache(self):
        reg = ProviderRegistry()
        reg.configure(ProviderConfig(provider=ProviderType.OPENAI, api_key="key1"))
        p1 = reg.get_provider(ProviderType.OPENAI)
        reg.configure(ProviderConfig(provider=ProviderType.OPENAI, api_key="key2"))
        p2 = reg.get_provider(ProviderType.OPENAI)
        assert p1 is not p2  # New instance after reconfigure


# ═══════════════════════════════════════════════════════════════════════
# Test create_provider Factory
# ═══════════════════════════════════════════════════════════════════════


class TestCreateProvider:
    """Test the factory function."""

    def test_create_anthropic(self):
        p = create_provider(ProviderConfig(provider=ProviderType.ANTHROPIC, api_key="t"))
        assert p.provider_type == ProviderType.ANTHROPIC

    def test_create_openai(self):
        p = create_provider(ProviderConfig(provider=ProviderType.OPENAI, api_key="t"))
        assert p.provider_type == ProviderType.OPENAI

    def test_create_gemini(self):
        p = create_provider(ProviderConfig(provider=ProviderType.GEMINI, api_key="t"))
        assert p.provider_type == ProviderType.GEMINI

    def test_create_deepseek(self):
        p = create_provider(ProviderConfig(provider=ProviderType.DEEPSEEK, api_key="t"))
        assert p.provider_type == ProviderType.DEEPSEEK

    def test_create_ollama(self):
        p = create_provider(ProviderConfig(provider=ProviderType.OLLAMA))
        assert p.provider_type == ProviderType.OLLAMA


# ═══════════════════════════════════════════════════════════════════════
# Test Fallback Chains
# ═══════════════════════════════════════════════════════════════════════


class TestFallbackChain:
    """Test FallbackChain and pre-built chains."""

    def test_flagship_chain_has_models(self):
        assert len(FLAGSHIP_CHAIN.models) >= 3

    def test_fast_chain_has_models(self):
        assert len(FAST_CHAIN.models) >= 3

    def test_local_chain_has_models(self):
        assert len(LOCAL_CHAIN.models) >= 2

    def test_custom_chain_creation(self):
        chain = FallbackChain()
        chain.add("gpt-4o").add("claude-sonnet-4-20250514")
        assert len(chain.models) == 2

    def test_chain_deduplicates(self):
        chain = FallbackChain()
        chain.add("gpt-4o").add("gpt-4o")
        assert len(chain.models) == 1

    def test_flagship_chain_starts_with_claude(self):
        assert FLAGSHIP_CHAIN.models[0].startswith("claude")


# ═══════════════════════════════════════════════════════════════════════
# Test Model Router
# ═══════════════════════════════════════════════════════════════════════


class TestModelRouter:
    """Test model selection and routing."""

    def setup_method(self):
        self.registry = ProviderRegistry()
        self.registry.configure(ProviderConfig(
            provider=ProviderType.ANTHROPIC, api_key="test-key"
        ))
        self.router = ModelRouter(self.registry)

    def test_select_preferred_model(self):
        result = self.router.select_model(preferred_model="claude-sonnet-4-20250514")
        assert result == "claude-sonnet-4-20250514"

    def test_select_unconfigured_preferred_falls_through(self):
        result = self.router.select_model(preferred_model="gpt-4o")
        # OpenAI not configured, should return None or something else
        assert result != "gpt-4o" or result is None

    def test_select_by_tier(self):
        result = self.router.select_model(tier=ModelTier.STANDARD)
        assert result is not None

    def test_select_by_provider(self):
        result = self.router.select_model(provider=ProviderType.ANTHROPIC)
        assert result is not None
        info = get_model_info(result)
        assert info.provider == ProviderType.ANTHROPIC

    def test_select_from_empty_registry(self):
        empty_reg = ProviderRegistry()
        router = ModelRouter(empty_reg)
        result = router.select_model()
        assert result is None

    def test_estimate_cost_claude(self):
        cost = self.router.estimate_cost("claude-sonnet-4-20250514", 1000, 500)
        assert cost > 0

    def test_estimate_cost_local(self):
        cost = self.router.estimate_cost("llama3.3", 1000, 500)
        assert cost == 0.0

    def test_estimate_cost_unknown_model(self):
        cost = self.router.estimate_cost("nonexistent", 1000, 500)
        assert cost == 0.0


# ═══════════════════════════════════════════════════════════════════════
# Test Agent Engine Integration
# ═══════════════════════════════════════════════════════════════════════


class TestAgentEngineIntegration:
    """Test that AgentEngine works with provider_registry parameter."""

    def test_engine_accepts_registry(self):
        from src.agents.engine import AgentEngine
        reg = ProviderRegistry()
        engine = AgentEngine(provider_registry=reg)
        assert engine._registry is reg

    def test_engine_without_registry_falls_back(self):
        from src.agents.engine import AgentEngine
        engine = AgentEngine()
        assert engine._registry is None

    def test_agent_config_has_preferred_model(self):
        from src.agents.config import AgentConfig, AgentType, AgentCategory
        cfg = AgentConfig(
            agent_type=AgentType.ALPHA_STRATEGIST,
            name="Test",
            category=AgentCategory.INVESTMENT_STYLE,
            description="Test",
            avatar="🤖",
            system_prompt="Test",
            preferred_model="gpt-4o",
        )
        assert cfg.preferred_model == "gpt-4o"

    def test_agent_config_default_preferred_model_is_none(self):
        from src.agents.config import AgentConfig, AgentType, AgentCategory
        cfg = AgentConfig(
            agent_type=AgentType.ALPHA_STRATEGIST,
            name="Test",
            category=AgentCategory.INVESTMENT_STYLE,
            description="Test",
            avatar="🤖",
            system_prompt="Test",
        )
        assert cfg.preferred_model is None


# ═══════════════════════════════════════════════════════════════════════
# Test Public API Imports
# ═══════════════════════════════════════════════════════════════════════


class TestPublicAPI:
    """Test that all public symbols are importable."""

    def test_import_all(self):
        from src.model_providers import (
            ProviderType,
            ModelTier,
            ModelInfo,
            ProviderConfig,
            ProviderResponse,
            ToolCall,
            MODEL_CATALOG,
            get_model_info,
            list_all_models,
            list_models_for_provider,
            BaseProvider,
            ProviderRegistry,
            create_provider,
            ModelRouter,
            FallbackChain,
            FLAGSHIP_CHAIN,
            FAST_CHAIN,
            LOCAL_CHAIN,
        )
        assert len(MODEL_CATALOG) >= 14

    def test_provider_types_are_complete(self):
        expected = {"anthropic", "openai", "gemini", "deepseek", "ollama"}
        actual = {p.value for p in ProviderType}
        assert actual == expected
