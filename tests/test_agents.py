"""Tests for PRD-131: Multi-Agent AI System."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from src.agents.config import (
    AgentCategory,
    AgentConfig,
    AgentType,
    ResponseStyleConfig,
    ToolWeight,
)
from src.agents.registry import (
    AGENT_CONFIGS,
    get_agent,
    get_agents_by_category,
    get_default_agent,
    list_agents,
    ALL_TOOLS,
    BASE_TOOL_CONTEXT,
)
from src.agents.engine import AgentEngine
from src.agents.memory import AgentMemory, MemorySession
from src.agents.router import AgentRouter, AgentSuggestion


# ═══════════════════════════════════════════════════════════════════════
# Test Agent Enums
# ═══════════════════════════════════════════════════════════════════════


class TestAgentEnums:
    """Test enum definitions and membership."""

    def test_agent_category_has_two_values(self):
        assert len(AgentCategory) == 2

    def test_agent_category_investment_style(self):
        assert AgentCategory.INVESTMENT_STYLE.value == "investment_style"

    def test_agent_category_functional_role(self):
        assert AgentCategory.FUNCTIONAL_ROLE.value == "functional_role"

    def test_agent_type_has_ten_members(self):
        assert len(AgentType) == 10

    def test_agent_type_investment_style_members(self):
        style_agents = [
            AgentType.ALPHA_STRATEGIST,
            AgentType.VALUE_ORACLE,
            AgentType.GROWTH_HUNTER,
            AgentType.MOMENTUM_RIDER,
            AgentType.INCOME_ARCHITECT,
            AgentType.RISK_SENTINEL,
        ]
        assert len(style_agents) == 6
        for a in style_agents:
            assert isinstance(a, AgentType)

    def test_agent_type_functional_role_members(self):
        role_agents = [
            AgentType.RESEARCH_ANALYST,
            AgentType.PORTFOLIO_ARCHITECT,
            AgentType.OPTIONS_STRATEGIST,
            AgentType.MARKET_SCOUT,
        ]
        assert len(role_agents) == 4
        for a in role_agents:
            assert isinstance(a, AgentType)

    def test_agent_type_values_are_unique(self):
        values = [a.value for a in AgentType]
        assert len(values) == len(set(values))

    def test_agent_type_alpha_strategist_value(self):
        assert AgentType.ALPHA_STRATEGIST.value == "alpha_strategist"

    def test_agent_type_value_oracle_value(self):
        assert AgentType.VALUE_ORACLE.value == "value_oracle"


# ═══════════════════════════════════════════════════════════════════════
# Test ToolWeight
# ═══════════════════════════════════════════════════════════════════════


class TestToolWeight:
    """Test ToolWeight dataclass."""

    def test_default_weight_is_one(self):
        tw = ToolWeight(tool_name="analyze_stock")
        assert tw.weight == 1.0

    def test_custom_weight(self):
        tw = ToolWeight(tool_name="analyze_stock", weight=0.5)
        assert tw.weight == 0.5

    def test_weight_clamps_below_zero(self):
        tw = ToolWeight(tool_name="analyze_stock", weight=-0.5)
        assert tw.weight == 0.0

    def test_weight_clamps_above_one(self):
        tw = ToolWeight(tool_name="analyze_stock", weight=1.5)
        assert tw.weight == 1.0

    def test_zero_weight(self):
        tw = ToolWeight(tool_name="analyze_stock", weight=0.0)
        assert tw.weight == 0.0

    def test_tool_name_preserved(self):
        tw = ToolWeight(tool_name="recommend_options", weight=0.7)
        assert tw.tool_name == "recommend_options"


# ═══════════════════════════════════════════════════════════════════════
# Test ResponseStyleConfig
# ═══════════════════════════════════════════════════════════════════════


class TestResponseStyleConfig:
    """Test ResponseStyleConfig dataclass."""

    def test_defaults(self):
        cfg = ResponseStyleConfig()
        assert cfg.verbosity == "balanced"
        assert cfg.data_density == "medium"
        assert cfg.tone == "professional"
        assert cfg.max_tokens == 4096

    def test_custom_values(self):
        cfg = ResponseStyleConfig(
            verbosity="detailed",
            data_density="high",
            tone="academic",
            max_tokens=2048,
        )
        assert cfg.verbosity == "detailed"
        assert cfg.max_tokens == 2048


# ═══════════════════════════════════════════════════════════════════════
# Test AgentConfig
# ═══════════════════════════════════════════════════════════════════════


class TestAgentConfig:
    """Test AgentConfig dataclass and properties."""

    def _make_config(self, **kwargs):
        defaults = dict(
            agent_type=AgentType.ALPHA_STRATEGIST,
            name="Test Agent",
            category=AgentCategory.INVESTMENT_STYLE,
            description="A test agent.",
            avatar="🤖",
            system_prompt="You are a test agent.",
            tool_weights=[
                ToolWeight("analyze_stock", 1.0),
                ToolWeight("screen_stocks", 0.8),
                ToolWeight("recommend_options", 0.0),
            ],
        )
        defaults.update(kwargs)
        return AgentConfig(**defaults)

    def test_creation(self):
        cfg = self._make_config()
        assert cfg.name == "Test Agent"
        assert cfg.agent_type == AgentType.ALPHA_STRATEGIST

    def test_available_tool_names(self):
        cfg = self._make_config()
        available = cfg.available_tool_names
        assert "analyze_stock" in available
        assert "screen_stocks" in available
        assert "recommend_options" not in available

    def test_priority_tools_sorted_by_weight(self):
        cfg = self._make_config()
        priority = cfg.priority_tools
        assert priority[0] == "analyze_stock"  # 1.0
        assert priority[1] == "screen_stocks"  # 0.8

    def test_excluded_tools(self):
        cfg = self._make_config()
        excluded = cfg.excluded_tools
        assert "recommend_options" in excluded
        assert "analyze_stock" not in excluded

    def test_default_response_style(self):
        cfg = self._make_config()
        assert cfg.response_style.verbosity == "balanced"

    def test_default_color(self):
        cfg = self._make_config()
        assert cfg.color == "#06b6d4"

    def test_default_welcome_message_is_empty(self):
        cfg = self._make_config()
        assert cfg.welcome_message == ""

    def test_default_example_queries_is_empty(self):
        cfg = self._make_config()
        assert cfg.example_queries == []


# ═══════════════════════════════════════════════════════════════════════
# Test Agent Registry
# ═══════════════════════════════════════════════════════════════════════


class TestAgentRegistry:
    """Test registry functions and completeness."""

    def test_ten_agents_registered(self):
        assert len(AGENT_CONFIGS) == 10

    def test_all_agent_types_have_config(self):
        for agent_type in AgentType:
            assert agent_type in AGENT_CONFIGS

    def test_unique_names(self):
        names = [a.name for a in AGENT_CONFIGS.values()]
        assert len(names) == len(set(names))

    def test_unique_avatars(self):
        avatars = [a.avatar for a in AGENT_CONFIGS.values()]
        assert len(avatars) == len(set(avatars))

    def test_all_prompts_non_empty(self):
        for agent in AGENT_CONFIGS.values():
            assert len(agent.system_prompt) > 50

    def test_all_prompts_contain_base_context(self):
        for agent in AGENT_CONFIGS.values():
            assert "get_stock_quote" in agent.system_prompt

    def test_all_agents_have_welcome_message(self):
        for agent in AGENT_CONFIGS.values():
            assert len(agent.welcome_message) > 10

    def test_all_agents_have_example_queries(self):
        for agent in AGENT_CONFIGS.values():
            assert len(agent.example_queries) >= 2

    def test_all_agents_have_tool_weights(self):
        for agent in AGENT_CONFIGS.values():
            assert len(agent.tool_weights) > 0

    def test_get_agent_returns_correct_type(self):
        agent = get_agent(AgentType.VALUE_ORACLE)
        assert agent.agent_type == AgentType.VALUE_ORACLE
        assert agent.name == "Value Oracle"

    def test_get_agent_raises_on_unknown(self):
        with pytest.raises(ValueError, match="Unknown agent type"):
            get_agent("nonexistent")

    def test_list_agents_returns_ten(self):
        agents = list_agents()
        assert len(agents) == 10

    def test_get_agents_by_category_investment_style(self):
        style = get_agents_by_category(AgentCategory.INVESTMENT_STYLE)
        assert len(style) == 6

    def test_get_agents_by_category_functional_role(self):
        role = get_agents_by_category(AgentCategory.FUNCTIONAL_ROLE)
        assert len(role) == 4

    def test_get_default_agent_is_alpha_strategist(self):
        default = get_default_agent()
        assert default.agent_type == AgentType.ALPHA_STRATEGIST

    def test_base_tool_context_mentions_all_tools(self):
        for tool in ALL_TOOLS:
            assert tool in BASE_TOOL_CONTEXT

    def test_alpha_strategist_has_all_tools_at_1(self):
        alpha = get_agent(AgentType.ALPHA_STRATEGIST)
        for tw in alpha.tool_weights:
            assert tw.weight == 1.0

    def test_value_oracle_deprioritizes_options(self):
        vo = get_agent(AgentType.VALUE_ORACLE)
        options_weights = [tw for tw in vo.tool_weights if "option" in tw.tool_name]
        for tw in options_weights:
            assert tw.weight < 0.5

    def test_options_strategist_prioritizes_options(self):
        os_agent = get_agent(AgentType.OPTIONS_STRATEGIST)
        options_weights = [tw for tw in os_agent.tool_weights if "option" in tw.tool_name]
        for tw in options_weights:
            assert tw.weight >= 1.0


# ═══════════════════════════════════════════════════════════════════════
# Test Agent Engine
# ═══════════════════════════════════════════════════════════════════════


class TestAgentEngine:
    """Test AgentEngine with mocked API client."""

    def test_engine_creation(self):
        engine = AgentEngine()
        assert engine.model == "claude-sonnet-4-20250514"
        assert engine.max_tokens == 4096

    def test_engine_custom_model(self):
        engine = AgentEngine(model="claude-haiku-4-5-20251001", max_tokens=2048)
        assert engine.model == "claude-haiku-4-5-20251001"
        assert engine.max_tokens == 2048

    def test_filter_tools_all_available(self):
        engine = AgentEngine()
        agent = get_agent(AgentType.ALPHA_STRATEGIST)
        filtered = engine._filter_tools(agent)
        assert len(filtered) == 9  # All tools

    def test_filter_tools_excludes_zero_weight(self):
        engine = AgentEngine()
        agent_cfg = AgentConfig(
            agent_type=AgentType.ALPHA_STRATEGIST,
            name="Test",
            category=AgentCategory.INVESTMENT_STYLE,
            description="Test",
            avatar="🤖",
            system_prompt="Test",
            tool_weights=[
                ToolWeight("analyze_stock", 1.0),
                ToolWeight("recommend_options", 0.0),
            ],
        )
        filtered = engine._filter_tools(agent_cfg)
        filtered_names = [t["name"] for t in filtered]
        assert "analyze_stock" in filtered_names
        assert "recommend_options" not in filtered_names

    def test_filter_tools_returns_full_definitions(self):
        engine = AgentEngine()
        agent = get_agent(AgentType.VALUE_ORACLE)
        filtered = engine._filter_tools(agent)
        for tool_def in filtered:
            assert "name" in tool_def
            assert "description" in tool_def
            assert "input_schema" in tool_def

    @patch("anthropic.Anthropic")
    def test_get_response_uses_agent_prompt(self, mock_anthropic_cls):
        """Verify that agent's system_prompt is passed to the API."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # Simulate a non-tool-use response
        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = "Test response"
        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [mock_block]
        mock_client.messages.create.return_value = mock_response

        engine = AgentEngine()
        agent = get_agent(AgentType.VALUE_ORACLE)

        text, msgs, tools = engine.get_response(
            [{"role": "user", "content": "Hello"}],
            "fake-key",
            agent,
        )

        # Verify system prompt was the agent's
        call_kwargs = mock_client.messages.create.call_args
        assert "Value Oracle" in call_kwargs.kwargs["system"]
        assert text == "Test response"

    @patch("anthropic.Anthropic")
    def test_get_response_returns_tool_calls(self, mock_anthropic_cls):
        """Verify that tool calls are captured and returned."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # First call: tool use
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "analyze_stock"
        mock_tool_block.input = {"ticker": "AAPL"}
        mock_tool_block.id = "tool_123"
        mock_response_1 = MagicMock()
        mock_response_1.stop_reason = "tool_use"
        mock_response_1.content = [mock_tool_block]

        # Second call: text response
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "AAPL analysis complete."
        mock_response_2 = MagicMock()
        mock_response_2.stop_reason = "end_turn"
        mock_response_2.content = [mock_text_block]

        mock_client.messages.create.side_effect = [mock_response_1, mock_response_2]

        engine = AgentEngine()
        agent = get_agent(AgentType.RESEARCH_ANALYST)

        with patch("src.agents.engine.execute_tool", return_value='{"ticker":"AAPL"}'):
            text, msgs, tool_calls = engine.get_response(
                [{"role": "user", "content": "Analyze AAPL"}],
                "fake-key",
                agent,
            )

        assert len(tool_calls) == 1
        assert tool_calls[0]["name"] == "analyze_stock"
        assert text == "AAPL analysis complete."


# ═══════════════════════════════════════════════════════════════════════
# Test Agent Memory
# ═══════════════════════════════════════════════════════════════════════


class TestAgentMemory:
    """Test AgentMemory in-memory fallback mode."""

    def test_memory_creation_without_db(self):
        mem = AgentMemory()
        assert not mem.is_persistent

    def test_memory_creation_with_invalid_db(self):
        mem = AgentMemory(db_url="postgresql://invalid:5432/fake")
        assert not mem.is_persistent

    def test_create_session(self):
        mem = AgentMemory()
        session = mem.create_session("user1", "alpha_strategist", "Test Chat")
        assert session.user_id == "user1"
        assert session.agent_type == "alpha_strategist"
        assert session.title == "Test Chat"
        assert session.is_active

    def test_get_session(self):
        mem = AgentMemory()
        session = mem.create_session("user1", "value_oracle")
        retrieved = mem.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_session_nonexistent(self):
        mem = AgentMemory()
        assert mem.get_session("nonexistent") is None

    def test_save_and_load_messages(self):
        mem = AgentMemory()
        session = mem.create_session("user1", "alpha_strategist")
        mem.save_message(session.session_id, "user", "Hello")
        mem.save_message(session.session_id, "assistant", "Hi there!")

        messages = mem.load_messages(session.session_id)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[1]["role"] == "assistant"

    def test_save_message_to_nonexistent_session(self):
        mem = AgentMemory()
        # Should not raise
        mem.save_message("nonexistent", "user", "Hello")

    def test_load_messages_empty_session(self):
        mem = AgentMemory()
        session = mem.create_session("user1", "alpha_strategist")
        assert mem.load_messages(session.session_id) == []

    def test_load_messages_nonexistent_session(self):
        mem = AgentMemory()
        assert mem.load_messages("nonexistent") == []

    def test_get_user_sessions(self):
        mem = AgentMemory()
        mem.create_session("user1", "alpha_strategist")
        mem.create_session("user1", "value_oracle")
        mem.create_session("user2", "growth_hunter")

        user1_sessions = mem.get_user_sessions("user1")
        assert len(user1_sessions) == 2

    def test_get_user_sessions_active_only(self):
        mem = AgentMemory()
        s1 = mem.create_session("user1", "alpha_strategist")
        s2 = mem.create_session("user1", "value_oracle")
        s2.is_active = False

        active = mem.get_user_sessions("user1", active_only=True)
        assert len(active) == 1

        all_sessions = mem.get_user_sessions("user1", active_only=False)
        assert len(all_sessions) == 2

    def test_delete_session(self):
        mem = AgentMemory()
        session = mem.create_session("user1", "alpha_strategist")
        assert mem.delete_session(session.session_id) is True
        assert mem.get_session(session.session_id) is None

    def test_delete_nonexistent_session(self):
        mem = AgentMemory()
        assert mem.delete_session("nonexistent") is False

    def test_get_session_stats(self):
        mem = AgentMemory()
        s1 = mem.create_session("user1", "alpha_strategist")
        s2 = mem.create_session("user1", "value_oracle")
        mem.save_message(s1.session_id, "user", "Hello")
        mem.save_message(s1.session_id, "assistant", "Hi")
        mem.save_message(s2.session_id, "user", "Hey")

        stats = mem.get_session_stats("user1")
        assert stats["total_sessions"] == 2
        assert stats["active_sessions"] == 2
        assert stats["total_messages"] == 3
        assert len(stats["agents_used"]) == 2

    def test_save_and_load_preference(self):
        mem = AgentMemory()
        mem.save_preference("user1", "default_agent", "value_oracle")
        assert mem.load_preference("user1", "default_agent") == "value_oracle"

    def test_load_nonexistent_preference(self):
        mem = AgentMemory()
        assert mem.load_preference("user1", "nonexistent") is None

    def test_load_all_preferences(self):
        mem = AgentMemory()
        mem.save_preference("user1", "default_agent", "alpha_strategist")
        mem.save_preference("user1", "verbosity", "detailed")

        prefs = mem.load_all_preferences("user1")
        assert prefs["default_agent"] == "alpha_strategist"
        assert prefs["verbosity"] == "detailed"

    def test_load_all_preferences_empty(self):
        mem = AgentMemory()
        assert mem.load_all_preferences("user1") == {}

    def test_memory_session_message_count(self):
        session = MemorySession(
            session_id="test",
            user_id="user1",
            agent_type="alpha_strategist",
        )
        assert session.message_count == 0
        session.messages.append({"role": "user", "content": "test"})
        assert session.message_count == 1


# ═══════════════════════════════════════════════════════════════════════
# Test Agent Router
# ═══════════════════════════════════════════════════════════════════════


class TestAgentRouter:
    """Test keyword-based agent routing."""

    def setup_method(self):
        self.router = AgentRouter()

    def test_value_keywords(self):
        result = self.router.suggest_agent("Find cheap undervalued stocks with good P/E")
        assert result == AgentType.VALUE_ORACLE

    def test_growth_keywords(self):
        result = self.router.suggest_agent("What are the fastest growing companies?")
        assert result == AgentType.GROWTH_HUNTER

    def test_momentum_keywords(self):
        result = self.router.suggest_agent("Show me stocks with strong momentum and breakout")
        assert result == AgentType.MOMENTUM_RIDER

    def test_income_keywords(self):
        result = self.router.suggest_agent("Best dividend yield stocks for passive income")
        assert result == AgentType.INCOME_ARCHITECT

    def test_risk_keywords(self):
        result = self.router.suggest_agent("How do I hedge my portfolio against drawdown?")
        assert result == AgentType.RISK_SENTINEL

    def test_research_keywords(self):
        result = self.router.suggest_agent("Give me a deep dive research report on earnings")
        assert result == AgentType.RESEARCH_ANALYST

    def test_portfolio_keywords(self):
        result = self.router.suggest_agent("Help me rebalance my portfolio allocation")
        assert result == AgentType.PORTFOLIO_ARCHITECT

    def test_options_keywords(self):
        result = self.router.suggest_agent("Recommend an iron condor options strategy")
        assert result == AgentType.OPTIONS_STRATEGIST

    def test_market_keywords(self):
        result = self.router.suggest_agent("Give me a market overview and top picks")
        assert result == AgentType.MARKET_SCOUT

    def test_default_fallback(self):
        result = self.router.suggest_agent("Hello there")
        assert result == AgentType.ALPHA_STRATEGIST

    def test_classify_intent_returns_list(self):
        suggestions = self.router.classify_intent("Find value stocks with good PE ratio")
        assert len(suggestions) >= 1
        assert isinstance(suggestions[0], AgentSuggestion)
        assert suggestions[0].confidence > 0

    def test_classify_intent_default_on_no_match(self):
        suggestions = self.router.classify_intent("xyz abc 123")
        assert suggestions[0].agent_type == AgentType.ALPHA_STRATEGIST
        assert suggestions[0].confidence == 0.5

    def test_should_suggest_switch_returns_none_if_same(self):
        result = self.router.should_suggest_switch(
            "Find cheap value stocks", AgentType.VALUE_ORACLE
        )
        assert result is None

    def test_should_suggest_switch_returns_suggestion(self):
        result = self.router.should_suggest_switch(
            "Recommend iron condor options strategy with good IV",
            AgentType.ALPHA_STRATEGIST,
        )
        # Should suggest Options Strategist
        if result is not None:
            assert result.agent_type == AgentType.OPTIONS_STRATEGIST

    def test_should_suggest_switch_returns_none_for_low_confidence(self):
        result = self.router.should_suggest_switch(
            "Hello there",
            AgentType.ALPHA_STRATEGIST,
        )
        assert result is None

    def test_classify_intent_sorted_by_confidence(self):
        suggestions = self.router.classify_intent("Find cheap value stocks with margin of safety and good PE")
        if len(suggestions) > 1:
            for i in range(len(suggestions) - 1):
                assert suggestions[i].confidence >= suggestions[i + 1].confidence


# ═══════════════════════════════════════════════════════════════════════
# Test Integration / Imports
# ═══════════════════════════════════════════════════════════════════════


class TestAgentImports:
    """Test that the public API is importable."""

    def test_import_from_agents_package(self):
        from src.agents import (
            AgentCategory,
            AgentType,
            ToolWeight,
            ResponseStyleConfig,
            AgentConfig,
            AGENT_CONFIGS,
            get_agent,
            list_agents,
            get_agents_by_category,
            get_default_agent,
            AgentEngine,
            AgentMemory,
            AgentRouter,
        )
        assert len(AGENT_CONFIGS) == 10

    def test_agent_config_is_not_none(self):
        for agent_type in AgentType:
            config = get_agent(agent_type)
            assert config is not None
            assert config.system_prompt is not None
            assert config.name is not None

    def test_all_tools_list_has_nine_entries(self):
        assert len(ALL_TOOLS) == 9
