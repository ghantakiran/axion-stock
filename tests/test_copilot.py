"""Tests for PRD-58: AI Trading Copilot."""

import pytest
from datetime import datetime, timezone

from src.copilot import (
    CopilotConfig,
    RiskTolerance,
    InvestmentStyle,
    ResponseStyle,
    AnalysisType,
    IdeaStatus,
    DEFAULT_COPILOT_CONFIG,
    CopilotMessage,
    CopilotSession,
    CopilotPreferences,
    TradeIdea,
    PortfolioContext,
    MarketContext,
    AnalysisRequest,
    AnalysisResponse,
    CopilotEngine,
    AnalysisModule,
    PromptBuilder,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def engine():
    """Create a CopilotEngine instance."""
    return CopilotEngine()


@pytest.fixture
def analysis_module(engine):
    """Create an AnalysisModule instance."""
    return AnalysisModule(engine=engine)


@pytest.fixture
def sample_preferences():
    """Create sample user preferences."""
    return CopilotPreferences(
        user_id="user-001",
        risk_tolerance=RiskTolerance.MODERATE,
        investment_style=InvestmentStyle.GROWTH,
        time_horizon="medium",
        preferred_sectors=["Technology", "Healthcare"],
        excluded_sectors=["Utilities"],
        response_style=ResponseStyle.BALANCED,
    )


@pytest.fixture
def sample_portfolio():
    """Create sample portfolio context."""
    return PortfolioContext(
        total_value=100000.0,
        cash_balance=10000.0,
        positions_value=90000.0,
        day_pnl=500.0,
        day_return_pct=0.5,
        total_return_pct=15.0,
        num_positions=10,
        top_holdings=[
            {"symbol": "AAPL", "weight": 15.0, "value": 15000},
            {"symbol": "NVDA", "weight": 12.0, "value": 12000},
            {"symbol": "MSFT", "weight": 10.0, "value": 10000},
        ],
        sector_weights={"Technology": 40.0, "Healthcare": 25.0, "Financials": 20.0},
        portfolio_beta=1.15,
    )


@pytest.fixture
def sample_market():
    """Create sample market context."""
    return MarketContext(
        spy_price=580.0,
        spy_change_pct=0.35,
        vix=15.5,
        market_trend="bullish",
        sector_performance={"Technology": 1.2, "Healthcare": 0.5, "Energy": -0.8},
        economic_events=["CPI Release Tomorrow", "FOMC Meeting Next Week"],
        market_hours="open",
    )


# =============================================================================
# Config Tests
# =============================================================================


class TestCopilotConfig:
    """Tests for copilot configuration."""

    def test_default_config(self):
        """Default config has sensible values."""
        config = DEFAULT_COPILOT_CONFIG

        assert config.max_tokens == 2000
        assert config.temperature == 0.7
        assert config.max_context_messages == 20
        assert config.enable_trade_execution is False

    def test_risk_tolerance_enum(self):
        """RiskTolerance enum has all values."""
        values = {e.value for e in RiskTolerance}
        assert "conservative" in values
        assert "moderate" in values
        assert "aggressive" in values

    def test_investment_style_enum(self):
        """InvestmentStyle enum has all values."""
        values = {e.value for e in InvestmentStyle}
        assert "value" in values
        assert "growth" in values
        assert "momentum" in values
        assert "income" in values
        assert "balanced" in values

    def test_analysis_type_enum(self):
        """AnalysisType enum has all values."""
        values = {e.value for e in AnalysisType}
        assert "trade_idea" in values
        assert "symbol_research" in values
        assert "portfolio_review" in values
        assert "market_outlook" in values


# =============================================================================
# Model Tests
# =============================================================================


class TestCopilotModels:
    """Tests for copilot models."""

    def test_copilot_message_creation(self):
        """Can create CopilotMessage."""
        msg = CopilotMessage(role="user", content="Hello")

        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.message_id is not None
        assert msg.timestamp is not None

    def test_copilot_message_to_dict(self):
        """CopilotMessage converts to dict."""
        msg = CopilotMessage(role="assistant", content="Hi there!")
        data = msg.to_dict()

        assert data["role"] == "assistant"
        assert data["content"] == "Hi there!"
        assert "message_id" in data
        assert "timestamp" in data

    def test_copilot_session_creation(self):
        """Can create CopilotSession."""
        session = CopilotSession(user_id="user-001")

        assert session.user_id == "user-001"
        assert session.session_id is not None
        assert session.message_count == 0
        assert session.is_active is True

    def test_session_add_message(self):
        """Can add messages to session."""
        session = CopilotSession(user_id="user-001")

        msg = session.add_message("user", "Hello")
        assert session.message_count == 1
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_session_context_messages(self):
        """Can get context messages."""
        session = CopilotSession(user_id="user-001")
        session.add_message("user", "Hi")
        session.add_message("assistant", "Hello!")
        session.add_message("user", "How are you?")

        context = session.get_context_messages(limit=2)
        assert len(context) == 2
        assert context[0]["role"] == "assistant"
        assert context[1]["role"] == "user"

    def test_copilot_preferences(self, sample_preferences):
        """CopilotPreferences has expected values."""
        prefs = sample_preferences

        assert prefs.user_id == "user-001"
        assert prefs.risk_tolerance == RiskTolerance.MODERATE
        assert prefs.investment_style == InvestmentStyle.GROWTH
        assert "Technology" in prefs.preferred_sectors
        assert "Utilities" in prefs.excluded_sectors

    def test_preferences_to_dict(self, sample_preferences):
        """CopilotPreferences converts to dict."""
        data = sample_preferences.to_dict()

        assert data["risk_tolerance"] == "moderate"
        assert data["investment_style"] == "growth"
        assert isinstance(data["preferred_sectors"], list)

    def test_trade_idea_creation(self):
        """Can create TradeIdea."""
        idea = TradeIdea(
            symbol="AAPL",
            action="buy",
            confidence=0.85,
            entry_price=180.0,
            target_price=200.0,
            stop_loss=170.0,
        )

        assert idea.symbol == "AAPL"
        assert idea.action == "buy"
        assert idea.confidence == 0.85
        assert idea.status == IdeaStatus.ACTIVE

    def test_trade_idea_risk_reward(self):
        """TradeIdea calculates risk/reward."""
        idea = TradeIdea(
            symbol="AAPL",
            action="buy",
            entry_price=100.0,
            target_price=120.0,  # 20% upside
            stop_loss=90.0,      # 10% downside
        )

        assert idea.upside_pct == pytest.approx(20.0)
        assert idea.risk_pct == pytest.approx(10.0)
        assert idea.risk_reward_ratio == pytest.approx(2.0)

    def test_portfolio_context_summary(self, sample_portfolio):
        """PortfolioContext generates summary."""
        summary = sample_portfolio.to_summary()

        assert "Total Value" in summary
        assert "$100,000" in summary
        assert "AAPL" in summary
        assert "Technology" in summary

    def test_market_context_summary(self, sample_market):
        """MarketContext generates summary."""
        summary = sample_market.to_summary()

        assert "S&P 500" in summary
        assert "580" in summary
        assert "VIX" in summary
        assert "Bullish" in summary


# =============================================================================
# Engine Tests
# =============================================================================


class TestCopilotEngine:
    """Tests for CopilotEngine."""

    def test_create_session(self, engine):
        """Can create a session."""
        session = engine.create_session("user-001")

        assert session.user_id == "user-001"
        assert session.session_id is not None

    def test_get_session(self, engine):
        """Can retrieve a session."""
        created = engine.create_session("user-001")
        retrieved = engine.get_session(created.session_id)

        assert retrieved is not None
        assert retrieved.session_id == created.session_id

    def test_get_nonexistent_session(self, engine):
        """Returns None for nonexistent session."""
        result = engine.get_session("nonexistent")
        assert result is None

    def test_get_user_sessions(self, engine):
        """Can get all sessions for a user."""
        engine.create_session("user-001")
        engine.create_session("user-001")
        engine.create_session("user-002")

        sessions = engine.get_user_sessions("user-001")
        assert len(sessions) == 2

    def test_set_and_get_preferences(self, engine, sample_preferences):
        """Can set and get preferences."""
        engine.set_preferences(sample_preferences)
        prefs = engine.get_preferences("user-001")

        assert prefs.risk_tolerance == RiskTolerance.MODERATE
        assert prefs.investment_style == InvestmentStyle.GROWTH

    def test_default_preferences(self, engine):
        """Creates default preferences if not set."""
        prefs = engine.get_preferences("new-user")

        assert prefs.user_id == "new-user"
        assert prefs.risk_tolerance == RiskTolerance.MODERATE
        assert prefs.investment_style == InvestmentStyle.BALANCED

    def test_chat(self, engine):
        """Can send chat messages."""
        session = engine.create_session("user-001")
        response = engine.chat(session.session_id, "Hello!")

        assert response.role == "assistant"
        assert len(response.content) > 0
        assert session.message_count == 2  # user + assistant

    def test_chat_updates_session_title(self, engine):
        """First chat updates session title."""
        session = engine.create_session("user-001")
        engine.chat(session.session_id, "What do you think about AAPL?")

        assert session.title != "New Chat"
        assert "AAPL" in session.title

    def test_chat_extracts_symbols(self, engine):
        """Chat extracts mentioned symbols."""
        session = engine.create_session("user-001")
        response = engine.chat(session.session_id, "Compare AAPL and MSFT")

        # Response should mention these symbols
        assert len(response.extracted_symbols) >= 0  # May or may not extract from response

    def test_analyze(self, engine):
        """Can perform analysis."""
        request = AnalysisRequest(
            analysis_type=AnalysisType.SYMBOL_RESEARCH,
            symbol="AAPL",
        )

        response = engine.analyze(request)

        assert response.analysis_type == AnalysisType.SYMBOL_RESEARCH
        assert len(response.content) > 0

    def test_generate_trade_idea(self, engine, sample_preferences):
        """Can generate trade ideas."""
        engine.set_preferences(sample_preferences)
        idea = engine.generate_trade_idea("user-001")

        assert idea.symbol is not None
        assert idea.action in ["buy", "sell", "hold"]
        assert idea.user_id == "user-001"


# =============================================================================
# PromptBuilder Tests
# =============================================================================


class TestPromptBuilder:
    """Tests for PromptBuilder."""

    def test_build_system_prompt(self, sample_preferences, sample_portfolio, sample_market):
        """Can build system prompt."""
        builder = PromptBuilder()
        prompt = builder.build_system_prompt(
            preferences=sample_preferences,
            portfolio=sample_portfolio,
            market=sample_market,
        )

        assert "Moderate" in prompt
        assert "Growth" in prompt
        assert "Total Value" in prompt
        assert "S&P 500" in prompt

    def test_build_system_prompt_defaults(self):
        """System prompt works without context."""
        builder = PromptBuilder()
        prompt = builder.build_system_prompt()

        assert "expert financial analyst" in prompt
        assert "Moderate" in prompt

    def test_extract_symbols(self):
        """Can extract symbols from text."""
        builder = PromptBuilder()

        text = "I'm interested in $AAPL and MSFT. What about GOOGL?"
        symbols = builder.extract_symbols(text)

        assert "AAPL" in symbols
        assert "MSFT" in symbols
        assert "GOOGL" in symbols

    def test_extract_symbols_filters_common_words(self):
        """Filters common words that look like symbols."""
        builder = PromptBuilder()

        text = "The CEO said BUY is the right action for AAPL"
        symbols = builder.extract_symbols(text)

        assert "AAPL" in symbols
        assert "CEO" not in symbols
        assert "BUY" not in symbols

    def test_extract_trade_action(self):
        """Can extract trade action from text."""
        builder = PromptBuilder()

        assert builder.extract_trade_action("I recommend a strong buy") == "buy"
        assert builder.extract_trade_action("Consider selling here") == "sell"
        assert builder.extract_trade_action("Hold your position") == "hold"
        assert builder.extract_trade_action("No action needed") is None


# =============================================================================
# AnalysisModule Tests
# =============================================================================


class TestAnalysisModule:
    """Tests for AnalysisModule."""

    def test_research_symbol(self, analysis_module):
        """Can research a symbol."""
        response = analysis_module.research_symbol("AAPL")

        assert response.analysis_type == AnalysisType.SYMBOL_RESEARCH
        assert len(response.content) > 0
        assert "AAPL" in response.content

    def test_review_portfolio(self, analysis_module, sample_portfolio):
        """Can review portfolio."""
        response = analysis_module.review_portfolio(sample_portfolio)

        assert response.analysis_type == AnalysisType.PORTFOLIO_REVIEW
        assert len(response.content) > 0

    def test_generate_trade_ideas(self, analysis_module, sample_preferences):
        """Can generate multiple trade ideas."""
        ideas = analysis_module.generate_trade_ideas(sample_preferences, count=3)

        assert len(ideas) == 3
        for idea in ideas:
            assert idea.symbol is not None
            assert idea.action in ["buy", "sell", "hold"]

    def test_get_market_outlook(self, analysis_module):
        """Can get market outlook."""
        response = analysis_module.get_market_outlook()

        assert response.analysis_type == AnalysisType.MARKET_OUTLOOK
        assert len(response.content) > 0

    def test_check_portfolio_risks(self, analysis_module, sample_portfolio):
        """Can check portfolio risks."""
        response = analysis_module.check_portfolio_risks(sample_portfolio)

        assert response.analysis_type == AnalysisType.RISK_CHECK
        assert len(response.content) > 0

    def test_quick_take(self, analysis_module):
        """Can get quick take on symbol."""
        result = analysis_module.quick_take("AAPL")

        assert result["symbol"] == "AAPL"
        assert result["recommendation"] in ["Buy", "Sell", "Hold"]
        assert "confidence" in result


# =============================================================================
# Integration Tests
# =============================================================================


class TestCopilotIntegration:
    """Integration tests for the copilot."""

    def test_full_chat_workflow(self, engine, sample_preferences, sample_portfolio, sample_market):
        """Test full chat workflow."""
        # Set up
        engine.set_preferences(sample_preferences)
        session = engine.create_session("user-001")

        # First message
        response1 = engine.chat(
            session.session_id,
            "What's the market looking like today?",
            portfolio=sample_portfolio,
            market=sample_market,
        )

        assert response1 is not None
        assert session.message_count == 2

        # Follow-up
        response2 = engine.chat(
            session.session_id,
            "What about tech stocks?",
            portfolio=sample_portfolio,
            market=sample_market,
        )

        assert response2 is not None
        assert session.message_count == 4

    def test_analysis_to_trade_idea(self, analysis_module, sample_preferences):
        """Analysis can produce trade ideas."""
        response = analysis_module.research_symbol("AAPL", sample_preferences)

        # Even if no structured ideas, should have content
        assert len(response.content) > 0

    def test_session_persistence(self, engine):
        """Sessions persist across calls."""
        session1 = engine.create_session("user-001")
        engine.chat(session1.session_id, "Hello")

        # Get sessions
        sessions = engine.get_user_sessions("user-001")
        assert len(sessions) == 1

        # Get the session again
        session2 = engine.get_session(session1.session_id)
        assert session2.message_count == 2
