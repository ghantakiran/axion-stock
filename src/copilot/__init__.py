"""AI Trading Copilot - Claude-powered trading assistant.

Provides personalized trade ideas, research summaries, portfolio analysis,
and natural language interaction for trading decisions.
"""

from src.copilot.config import (
    CopilotConfig,
    RiskTolerance,
    InvestmentStyle,
    ResponseStyle,
    AnalysisType,
    IdeaStatus,
    DEFAULT_COPILOT_CONFIG,
)
from src.copilot.models import (
    CopilotMessage,
    CopilotSession,
    CopilotPreferences,
    TradeIdea,
    PortfolioContext,
    MarketContext,
    AnalysisRequest,
    AnalysisResponse,
)
from src.copilot.engine import CopilotEngine
from src.copilot.analysis import AnalysisModule
from src.copilot.prompts import PromptBuilder


__all__ = [
    # Config
    "CopilotConfig",
    "RiskTolerance",
    "InvestmentStyle",
    "ResponseStyle",
    "AnalysisType",
    "IdeaStatus",
    "DEFAULT_COPILOT_CONFIG",
    # Models
    "CopilotMessage",
    "CopilotSession",
    "CopilotPreferences",
    "TradeIdea",
    "PortfolioContext",
    "MarketContext",
    "AnalysisRequest",
    "AnalysisResponse",
    # Core
    "CopilotEngine",
    "AnalysisModule",
    "PromptBuilder",
]
