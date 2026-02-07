"""Analysis module for AI Trading Copilot."""

from dataclasses import dataclass
from typing import Optional

from src.copilot.config import AnalysisType
from src.copilot.models import (
    CopilotPreferences,
    PortfolioContext,
    MarketContext,
    TradeIdea,
    AnalysisRequest,
    AnalysisResponse,
)
from src.copilot.engine import CopilotEngine


class AnalysisModule:
    """High-level analysis functions for the copilot."""

    def __init__(self, engine: Optional[CopilotEngine] = None):
        self.engine = engine or CopilotEngine()

    def research_symbol(
        self,
        symbol: str,
        preferences: Optional[CopilotPreferences] = None,
        market: Optional[MarketContext] = None,
    ) -> AnalysisResponse:
        """Perform deep research on a symbol."""
        request = AnalysisRequest(
            analysis_type=AnalysisType.SYMBOL_RESEARCH,
            symbol=symbol.upper(),
            preferences=preferences,
            market_context=market,
        )
        return self.engine.analyze(request)

    def review_portfolio(
        self,
        portfolio: PortfolioContext,
        preferences: Optional[CopilotPreferences] = None,
        market: Optional[MarketContext] = None,
    ) -> AnalysisResponse:
        """Review and analyze a portfolio."""
        request = AnalysisRequest(
            analysis_type=AnalysisType.PORTFOLIO_REVIEW,
            preferences=preferences,
            portfolio_context=portfolio,
            market_context=market,
        )
        return self.engine.analyze(request)

    def generate_trade_ideas(
        self,
        preferences: CopilotPreferences,
        portfolio: Optional[PortfolioContext] = None,
        market: Optional[MarketContext] = None,
        count: int = 3,
    ) -> list[TradeIdea]:
        """Generate multiple trade ideas."""
        ideas = []
        sectors = ["Technology", "Healthcare", "Financials", "Consumer", "Energy"]

        for i in range(min(count, len(sectors))):
            idea = self.engine.generate_trade_idea(
                user_id=preferences.user_id,
                preferences=preferences,
                portfolio=portfolio,
                market=market,
                sector=sectors[i],
            )
            ideas.append(idea)

        return ideas

    def get_market_outlook(
        self,
        preferences: Optional[CopilotPreferences] = None,
        market: Optional[MarketContext] = None,
    ) -> AnalysisResponse:
        """Get market outlook analysis."""
        request = AnalysisRequest(
            analysis_type=AnalysisType.MARKET_OUTLOOK,
            preferences=preferences,
            market_context=market,
        )
        return self.engine.analyze(request)

    def check_portfolio_risks(
        self,
        portfolio: PortfolioContext,
        preferences: Optional[CopilotPreferences] = None,
    ) -> AnalysisResponse:
        """Check portfolio for risks."""
        request = AnalysisRequest(
            analysis_type=AnalysisType.RISK_CHECK,
            preferences=preferences,
            portfolio_context=portfolio,
        )
        return self.engine.analyze(request)

    def preview_earnings(
        self,
        symbol: str,
        preferences: Optional[CopilotPreferences] = None,
    ) -> AnalysisResponse:
        """Preview upcoming earnings for a symbol."""
        request = AnalysisRequest(
            analysis_type=AnalysisType.EARNINGS_PREVIEW,
            symbol=symbol.upper(),
            preferences=preferences,
        )
        return self.engine.analyze(request)

    def analyze_sector(
        self,
        sector: str,
        preferences: Optional[CopilotPreferences] = None,
        market: Optional[MarketContext] = None,
    ) -> AnalysisResponse:
        """Analyze a specific sector."""
        request = AnalysisRequest(
            analysis_type=AnalysisType.SECTOR_ANALYSIS,
            preferences=preferences,
            market_context=market,
            additional_context={"sector": sector},
        )
        return self.engine.analyze(request)

    def compare_symbols(
        self,
        symbols: list[str],
        preferences: Optional[CopilotPreferences] = None,
    ) -> dict:
        """Compare multiple symbols."""
        results = {}
        for symbol in symbols[:5]:  # Limit to 5
            response = self.research_symbol(symbol, preferences)
            results[symbol] = {
                "analysis": response.content,
                "confidence": response.confidence_score,
                "trade_ideas": [t.to_dict() for t in response.trade_ideas],
            }
        return results

    def quick_take(
        self,
        symbol: str,
        preferences: Optional[CopilotPreferences] = None,
    ) -> dict:
        """Get a quick take on a symbol (shorter analysis)."""
        response = self.research_symbol(symbol, preferences)

        # Extract key points
        content = response.content
        lines = content.split('\n')

        # Find recommendation
        recommendation = "Hold"
        for line in lines:
            if "Recommendation:" in line or "ACTION:" in line:
                if "BUY" in line.upper():
                    recommendation = "Buy"
                elif "SELL" in line.upper():
                    recommendation = "Sell"
                break

        return {
            "symbol": symbol,
            "recommendation": recommendation,
            "confidence": response.confidence_score,
            "summary": lines[0] if lines else "",
            "trade_idea": response.trade_ideas[0].to_dict() if response.trade_ideas else None,
        }
