"""Prompt building for AI Trading Copilot."""

from dataclasses import dataclass
from typing import Optional

from src.copilot.config import (
    AnalysisType,
    SYSTEM_PROMPT_TEMPLATE,
    TRADE_IDEA_PROMPT,
    PORTFOLIO_REVIEW_PROMPT,
    SYMBOL_RESEARCH_PROMPT,
)
from src.copilot.models import (
    CopilotPreferences,
    PortfolioContext,
    MarketContext,
)


class PromptBuilder:
    """Builds prompts for copilot interactions."""

    def __init__(self):
        self._system_template = SYSTEM_PROMPT_TEMPLATE
        self._analysis_prompts = {
            AnalysisType.TRADE_IDEA: TRADE_IDEA_PROMPT,
            AnalysisType.PORTFOLIO_REVIEW: PORTFOLIO_REVIEW_PROMPT,
            AnalysisType.SYMBOL_RESEARCH: SYMBOL_RESEARCH_PROMPT,
        }

    def build_system_prompt(
        self,
        preferences: Optional[CopilotPreferences] = None,
        portfolio: Optional[PortfolioContext] = None,
        market: Optional[MarketContext] = None,
    ) -> str:
        """Build the system prompt with context."""
        # Default values
        risk_tolerance = "Moderate"
        investment_style = "Balanced"
        time_horizon = "Medium-term"
        portfolio_summary = "No portfolio data available."
        market_context = "No market data available."

        if preferences:
            risk_tolerance = preferences.risk_tolerance.value.title()
            investment_style = preferences.investment_style.value.title()
            time_horizon = f"{preferences.time_horizon.title()}-term"

        if portfolio:
            portfolio_summary = portfolio.to_summary()

        if market:
            market_context = market.to_summary()

        return self._system_template.format(
            risk_tolerance=risk_tolerance,
            investment_style=investment_style,
            time_horizon=time_horizon,
            portfolio_summary=portfolio_summary,
            market_context=market_context,
        )

    def build_analysis_prompt(
        self,
        analysis_type: AnalysisType,
        symbol: Optional[str] = None,
        holdings: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Build analysis-specific prompt."""
        template = self._analysis_prompts.get(analysis_type, "")

        if analysis_type == AnalysisType.SYMBOL_RESEARCH and symbol:
            return template.format(symbol=symbol)
        elif analysis_type == AnalysisType.PORTFOLIO_REVIEW and holdings:
            return template.format(holdings=holdings)
        elif analysis_type == AnalysisType.TRADE_IDEA:
            return template

        return template

    def build_chat_prompt(
        self,
        user_message: str,
        context: Optional[dict] = None,
    ) -> str:
        """Build a prompt for general chat."""
        prompt = user_message

        if context:
            if context.get("active_symbol"):
                prompt = f"[Discussing {context['active_symbol']}] {prompt}"

        return prompt

    def build_market_outlook_prompt(self) -> str:
        """Build prompt for market outlook analysis."""
        return """Provide a market outlook analysis covering:

1. Overall Market Assessment
   - Current trend and momentum
   - Key support/resistance levels for major indices

2. Sector Rotation
   - Sectors showing strength
   - Sectors showing weakness
   - Rotation themes

3. Key Risks
   - Near-term concerns
   - Tail risks to monitor

4. Opportunities
   - Potential setups to watch
   - Themes with tailwinds

5. Trading Stance
   - Recommended positioning (risk-on/risk-off)
   - Position sizing guidance

Be specific with levels and actionable in recommendations."""

    def build_risk_check_prompt(self, portfolio: PortfolioContext) -> str:
        """Build prompt for portfolio risk check."""
        return f"""Perform a risk assessment of the portfolio:

{portfolio.to_summary()}

Analyze:
1. Concentration Risk - Any single positions too large?
2. Sector Risk - Overexposure to any sectors?
3. Correlation Risk - Are positions too correlated?
4. Market Risk - Beta and volatility concerns?
5. Liquidity Risk - Any illiquid positions?
6. Event Risk - Upcoming earnings/events for holdings?

For each identified risk:
- Severity: Low/Medium/High
- Specific concern
- Recommended action

Provide an overall risk score (1-10) and top 3 priority actions."""

    def build_earnings_preview_prompt(self, symbol: str) -> str:
        """Build prompt for earnings preview."""
        return f"""Provide an earnings preview for {symbol}:

1. Upcoming Earnings
   - Expected date
   - Consensus estimates (EPS, Revenue)
   - Whisper number if known

2. Key Metrics to Watch
   - Most important line items
   - Guidance factors

3. Historical Pattern
   - Recent beat/miss history
   - Post-earnings price action

4. Options Market View
   - Implied move
   - Put/call skew sentiment

5. Trading Strategy
   - Pre-earnings positioning
   - Post-earnings scenarios
   - Risk management

Be specific with numbers and price levels."""

    def extract_symbols(self, text: str) -> list[str]:
        """Extract stock symbols from text."""
        import re

        # Common stock symbol patterns
        # Look for $SYMBOL or standalone 1-5 letter uppercase words
        patterns = [
            r'\$([A-Z]{1,5})\b',  # $AAPL format
            r'\b([A-Z]{2,5})\b',   # Standalone symbols
        ]

        symbols = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            symbols.update(matches)

        # Filter out common words that aren't symbols
        common_words = {
            'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL',
            'CAN', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'BUY', 'SELL',
            'HOLD', 'LOW', 'HIGH', 'UP', 'DOWN', 'ETF', 'IPO', 'CEO',
            'CFO', 'EPS', 'PE', 'PB', 'ROE', 'ROA', 'EBITDA', 'GDP',
            'FED', 'FOMC', 'CPI', 'PPI', 'PMI', 'ISM', 'NFP', 'ATH',
            'YTD', 'QTD', 'MTD', 'WTD', 'EOD', 'EOW', 'EOM', 'EOQ',
        }

        return [s for s in symbols if s not in common_words]

    def extract_trade_action(self, text: str) -> Optional[str]:
        """Extract trade action from text."""
        text_lower = text.lower()

        if any(word in text_lower for word in ['strong buy', 'bullish', 'accumulate']):
            return 'buy'
        elif any(word in text_lower for word in ['buy', 'long', 'add']):
            return 'buy'
        elif any(word in text_lower for word in ['strong sell', 'bearish', 'avoid']):
            return 'sell'
        elif any(word in text_lower for word in ['sell', 'short', 'reduce', 'trim']):
            return 'sell'
        elif any(word in text_lower for word in ['hold', 'neutral', 'wait']):
            return 'hold'

        return None
