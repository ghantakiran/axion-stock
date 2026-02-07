"""Configuration for AI Trading Copilot."""

import enum
from dataclasses import dataclass, field


class RiskTolerance(enum.Enum):
    """Risk tolerance levels."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class InvestmentStyle(enum.Enum):
    """Investment style preferences."""
    VALUE = "value"
    GROWTH = "growth"
    MOMENTUM = "momentum"
    INCOME = "income"
    BALANCED = "balanced"


class ResponseStyle(enum.Enum):
    """Response verbosity preference."""
    CONCISE = "concise"
    BALANCED = "balanced"
    DETAILED = "detailed"


class AnalysisType(enum.Enum):
    """Types of analysis the copilot can perform."""
    TRADE_IDEA = "trade_idea"
    SYMBOL_RESEARCH = "symbol_research"
    PORTFOLIO_REVIEW = "portfolio_review"
    MARKET_OUTLOOK = "market_outlook"
    RISK_CHECK = "risk_check"
    EARNINGS_PREVIEW = "earnings_preview"
    SECTOR_ANALYSIS = "sector_analysis"


class IdeaStatus(enum.Enum):
    """Status of a saved trade idea."""
    ACTIVE = "active"
    EXECUTED = "executed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class IdeaOutcome(enum.Enum):
    """Outcome of an executed trade idea."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


@dataclass
class CopilotConfig:
    """Configuration for the copilot engine."""

    # Model settings
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 2000
    temperature: float = 0.7

    # Context limits
    max_context_messages: int = 20
    max_portfolio_positions: int = 50

    # Rate limits
    max_requests_per_minute: int = 30
    max_tokens_per_day: int = 100000

    # Timeouts
    request_timeout_seconds: int = 30

    # Features
    enable_trade_execution: bool = False  # Safety: disabled by default
    enable_real_time_data: bool = True
    enable_sentiment_analysis: bool = True

    # Defaults
    default_risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    default_investment_style: InvestmentStyle = InvestmentStyle.BALANCED
    default_response_style: ResponseStyle = ResponseStyle.BALANCED


DEFAULT_COPILOT_CONFIG = CopilotConfig()


# Prompt templates
SYSTEM_PROMPT_TEMPLATE = """You are an expert financial analyst and trading advisor for the Axion trading platform.
You help users make informed investment decisions based on their preferences and market conditions.

User Profile:
- Risk Tolerance: {risk_tolerance}
- Investment Style: {investment_style}
- Time Horizon: {time_horizon}

Current Portfolio Summary:
{portfolio_summary}

Market Context:
{market_context}

Guidelines:
1. Provide specific, actionable advice with clear rationale
2. Always consider the user's risk tolerance and investment style
3. Include relevant price levels (entry, target, stop-loss) when suggesting trades
4. Highlight key risks and potential downsides
5. Reference current market conditions and relevant news
6. Be concise but thorough based on user's response style preference

Do not provide advice on options, futures, or derivatives unless specifically asked.
Always remind users that past performance doesn't guarantee future results."""


TRADE_IDEA_PROMPT = """Generate a trade idea for the user based on their preferences.

Requirements:
1. Suggest a specific stock (symbol)
2. Recommend action: BUY, SELL, or HOLD
3. Provide confidence level (1-10)
4. Explain the rationale (2-3 key points)
5. Include entry price, target price, and stop-loss
6. Specify time horizon (short: <1 month, medium: 1-6 months, long: >6 months)

Format your response as:
SYMBOL: [ticker]
ACTION: [BUY/SELL/HOLD]
CONFIDENCE: [1-10]
ENTRY: $[price]
TARGET: $[price]
STOP_LOSS: $[price]
TIME_HORIZON: [short/medium/long]
RATIONALE: [explanation]"""


PORTFOLIO_REVIEW_PROMPT = """Analyze the user's current portfolio and provide recommendations.

Focus on:
1. Portfolio composition and diversification
2. Sector/industry concentration
3. Risk assessment
4. Top 3 strengths
5. Top 3 areas for improvement
6. Specific rebalancing suggestions

Current Holdings:
{holdings}

Be specific about which positions to adjust and why."""


SYMBOL_RESEARCH_PROMPT = """Provide a comprehensive analysis of {symbol}.

Include:
1. Company overview (1-2 sentences)
2. Recent performance summary
3. Key fundamentals (P/E, revenue growth, margins)
4. Technical setup (trend, support/resistance)
5. Sentiment indicators
6. Upcoming catalysts (earnings, events)
7. Bull case vs Bear case
8. Overall recommendation

Keep the analysis focused and actionable."""
