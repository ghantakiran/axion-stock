"""Core engine for AI Trading Copilot."""

import re
import time
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone

from src.copilot.config import (
    CopilotConfig,
    AnalysisType,
    DEFAULT_COPILOT_CONFIG,
)
from src.copilot.models import (
    CopilotSession,
    CopilotMessage,
    CopilotPreferences,
    TradeIdea,
    PortfolioContext,
    MarketContext,
    AnalysisRequest,
    AnalysisResponse,
)
from src.copilot.prompts import PromptBuilder


class CopilotEngine:
    """Main engine for the AI Trading Copilot."""

    def __init__(self, config: Optional[CopilotConfig] = None):
        self.config = config or DEFAULT_COPILOT_CONFIG
        self.prompt_builder = PromptBuilder()
        self._sessions: dict[str, CopilotSession] = {}
        self._preferences: dict[str, CopilotPreferences] = {}

    def create_session(self, user_id: str, session_type: str = "chat") -> CopilotSession:
        """Create a new copilot session."""
        session = CopilotSession(
            user_id=user_id,
            session_type=session_type,
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[CopilotSession]:
        """Get an existing session."""
        return self._sessions.get(session_id)

    def get_user_sessions(self, user_id: str, active_only: bool = True) -> list[CopilotSession]:
        """Get all sessions for a user."""
        sessions = [s for s in self._sessions.values() if s.user_id == user_id]
        if active_only:
            sessions = [s for s in sessions if s.is_active]
        return sorted(sessions, key=lambda s: s.last_activity_at, reverse=True)

    def set_preferences(self, preferences: CopilotPreferences) -> None:
        """Set user preferences."""
        self._preferences[preferences.user_id] = preferences

    def get_preferences(self, user_id: str) -> CopilotPreferences:
        """Get user preferences, creating defaults if needed."""
        if user_id not in self._preferences:
            self._preferences[user_id] = CopilotPreferences(user_id=user_id)
        return self._preferences[user_id]

    def chat(
        self,
        session_id: str,
        user_message: str,
        portfolio: Optional[PortfolioContext] = None,
        market: Optional[MarketContext] = None,
    ) -> CopilotMessage:
        """Send a chat message and get a response."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        preferences = self.get_preferences(session.user_id)

        # Add user message
        session.add_message("user", user_message)

        # Build context
        system_prompt = self.prompt_builder.build_system_prompt(
            preferences=preferences,
            portfolio=portfolio,
            market=market,
        )

        # Generate response (simulated for now)
        start_time = time.time()
        response_content = self._generate_response(
            session=session,
            system_prompt=system_prompt,
            user_message=user_message,
            preferences=preferences,
        )
        elapsed_ms = (time.time() - start_time) * 1000

        # Extract metadata
        symbols = self.prompt_builder.extract_symbols(response_content)
        action = self.prompt_builder.extract_trade_action(response_content)
        actions = [action] if action else []

        # Add assistant response
        assistant_msg = session.add_message(
            role="assistant",
            content=response_content,
            model=self.config.model,
            tokens_used=len(response_content.split()) * 2,  # Rough estimate
            extracted_symbols=symbols,
            extracted_actions=actions,
        )

        # Update session title from first exchange
        if session.message_count == 2:
            session.title = self._generate_title(user_message)

        # Track active symbol if mentioned
        if symbols:
            session.active_symbol = symbols[0]

        return assistant_msg

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """Perform a specific analysis."""
        start_time = time.time()

        preferences = request.preferences or CopilotPreferences(user_id="anonymous")
        portfolio = request.portfolio_context or PortfolioContext()
        market = request.market_context or MarketContext()

        # Build prompts
        system_prompt = self.prompt_builder.build_system_prompt(
            preferences=preferences,
            portfolio=portfolio,
            market=market,
        )

        analysis_prompt = self._build_analysis_prompt(request)

        # Generate analysis
        content = self._generate_analysis(
            analysis_type=request.analysis_type,
            system_prompt=system_prompt,
            analysis_prompt=analysis_prompt,
            symbol=request.symbol,
        )

        # Extract data
        symbols = self.prompt_builder.extract_symbols(content)
        trade_ideas = self._extract_trade_ideas(content, request.symbol)

        elapsed_ms = (time.time() - start_time) * 1000

        return AnalysisResponse(
            content=content,
            analysis_type=request.analysis_type,
            symbols_mentioned=symbols,
            trade_ideas=trade_ideas,
            confidence_score=0.75,  # Placeholder
            tokens_used=len(content.split()) * 2,
            model=self.config.model,
            processing_time_ms=elapsed_ms,
        )

    def generate_trade_idea(
        self,
        user_id: str,
        preferences: Optional[CopilotPreferences] = None,
        portfolio: Optional[PortfolioContext] = None,
        market: Optional[MarketContext] = None,
        sector: Optional[str] = None,
    ) -> TradeIdea:
        """Generate a trade idea based on context."""
        prefs = preferences or self.get_preferences(user_id)

        # Simulate AI-generated trade idea
        # In production, this would call Claude API
        idea = self._generate_mock_trade_idea(prefs, sector)
        idea.user_id = user_id

        return idea

    def _generate_response(
        self,
        session: CopilotSession,
        system_prompt: str,
        user_message: str,
        preferences: CopilotPreferences,
    ) -> str:
        """Generate a response (simulated)."""
        # In production, this would call the Claude API
        # For now, generate contextual mock responses

        msg_lower = user_message.lower()

        if any(word in msg_lower for word in ['portfolio', 'holdings', 'positions']):
            return self._mock_portfolio_response(preferences)
        elif any(word in msg_lower for word in ['buy', 'sell', 'trade', 'idea']):
            return self._mock_trade_idea_response(preferences)
        elif any(word in msg_lower for word in ['market', 'outlook', 'today']):
            return self._mock_market_outlook_response()
        elif any(word in msg_lower for word in ['risk', 'hedge', 'protect']):
            return self._mock_risk_response()
        else:
            # Extract potential symbol
            symbols = self.prompt_builder.extract_symbols(user_message)
            if symbols:
                return self._mock_symbol_research_response(symbols[0])
            return self._mock_general_response()

    def _generate_analysis(
        self,
        analysis_type: AnalysisType,
        system_prompt: str,
        analysis_prompt: str,
        symbol: Optional[str] = None,
    ) -> str:
        """Generate analysis content (simulated)."""
        if analysis_type == AnalysisType.TRADE_IDEA:
            return self._mock_trade_idea_response(CopilotPreferences(user_id=""))
        elif analysis_type == AnalysisType.PORTFOLIO_REVIEW:
            return self._mock_portfolio_response(CopilotPreferences(user_id=""))
        elif analysis_type == AnalysisType.SYMBOL_RESEARCH and symbol:
            return self._mock_symbol_research_response(symbol)
        elif analysis_type == AnalysisType.MARKET_OUTLOOK:
            return self._mock_market_outlook_response()
        elif analysis_type == AnalysisType.RISK_CHECK:
            return self._mock_risk_response()
        else:
            return self._mock_general_response()

    def _build_analysis_prompt(self, request: AnalysisRequest) -> str:
        """Build the analysis prompt."""
        if request.analysis_type == AnalysisType.SYMBOL_RESEARCH:
            return self.prompt_builder.build_analysis_prompt(
                request.analysis_type,
                symbol=request.symbol,
            )
        elif request.analysis_type == AnalysisType.PORTFOLIO_REVIEW:
            holdings = ""
            if request.portfolio_context:
                holdings = request.portfolio_context.to_summary()
            return self.prompt_builder.build_analysis_prompt(
                request.analysis_type,
                holdings=holdings,
            )
        else:
            return self.prompt_builder.build_analysis_prompt(request.analysis_type)

    def _extract_trade_ideas(
        self,
        content: str,
        symbol: Optional[str] = None,
    ) -> list[TradeIdea]:
        """Extract trade ideas from response content."""
        ideas = []

        # Look for structured trade idea format
        if "SYMBOL:" in content and "ACTION:" in content:
            idea = TradeIdea(
                symbol=symbol or self._extract_field(content, "SYMBOL") or "N/A",
                action=self._extract_field(content, "ACTION") or "hold",
            )

            confidence = self._extract_field(content, "CONFIDENCE")
            if confidence:
                try:
                    idea.confidence = float(confidence) / 10
                except ValueError:
                    pass

            entry = self._extract_price(content, "ENTRY")
            if entry:
                idea.entry_price = entry

            target = self._extract_price(content, "TARGET")
            if target:
                idea.target_price = target

            stop = self._extract_price(content, "STOP_LOSS")
            if stop:
                idea.stop_loss = stop

            horizon = self._extract_field(content, "TIME_HORIZON")
            if horizon:
                idea.time_horizon = horizon.lower()

            rationale = self._extract_field(content, "RATIONALE")
            if rationale:
                idea.rationale = rationale

            ideas.append(idea)

        return ideas

    def _extract_field(self, content: str, field: str) -> Optional[str]:
        """Extract a field value from content."""
        pattern = rf'{field}:\s*(.+?)(?:\n|$)'
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _extract_price(self, content: str, field: str) -> Optional[float]:
        """Extract a price value from content."""
        value = self._extract_field(content, field)
        if value:
            # Remove $ and commas
            clean = re.sub(r'[$,]', '', value)
            try:
                return float(clean)
            except ValueError:
                pass
        return None

    def _generate_title(self, first_message: str) -> str:
        """Generate a session title from first message."""
        # Take first 50 chars, clean up
        title = first_message[:50].strip()
        if len(first_message) > 50:
            title += "..."
        return title

    def _generate_mock_trade_idea(
        self,
        preferences: CopilotPreferences,
        sector: Optional[str] = None,
    ) -> TradeIdea:
        """Generate a mock trade idea."""
        # Sample ideas based on style
        ideas_by_style = {
            "value": ("JPM", 195.0, 220.0, 180.0, "Strong value play with attractive dividend yield and solid fundamentals."),
            "growth": ("NVDA", 850.0, 1000.0, 780.0, "AI leader with exceptional growth trajectory and market dominance."),
            "momentum": ("META", 520.0, 580.0, 490.0, "Strong momentum with positive earnings revisions and technical breakout."),
            "income": ("VZ", 42.0, 48.0, 39.0, "High yield defensive play with stable cash flows."),
            "balanced": ("MSFT", 420.0, 470.0, 390.0, "Quality compounder with diversified revenue streams."),
        }

        style = preferences.investment_style.value
        symbol, entry, target, stop, rationale = ideas_by_style.get(
            style,
            ideas_by_style["balanced"]
        )

        return TradeIdea(
            symbol=symbol,
            action="buy",
            confidence=0.75,
            rationale=rationale,
            entry_price=entry,
            target_price=target,
            stop_loss=stop,
            time_horizon="medium",
        )

    # Mock response generators
    def _mock_portfolio_response(self, preferences: CopilotPreferences) -> str:
        return """Based on your portfolio analysis:

**Portfolio Health: Good**

**Strengths:**
1. Well-diversified across sectors
2. Reasonable position sizing
3. Quality holdings with strong fundamentals

**Areas for Improvement:**
1. Consider adding international exposure
2. Technology allocation slightly high at 35%
3. Cash position could be deployed opportunistically

**Recommendations:**
- Trim AAPL position by 2% to reduce single-stock risk
- Add VEA (Vanguard FTSE Developed Markets) for international diversification
- Consider adding a REIT position for income and inflation hedge

Overall, your portfolio is well-positioned for current market conditions."""

    def _mock_trade_idea_response(self, preferences: CopilotPreferences) -> str:
        return """Here's a trade idea based on your preferences:

SYMBOL: GOOGL
ACTION: BUY
CONFIDENCE: 8
ENTRY: $175.00
TARGET: $200.00
STOP_LOSS: $165.00
TIME_HORIZON: medium

RATIONALE: Google offers compelling value at current levels. The company is seeing strong growth in cloud services, AI integration across products is driving engagement, and the advertising business remains resilient. Technical setup shows a breakout above the 50-day moving average with increasing volume. Risk/reward is attractive at 2.4:1."""

    def _mock_market_outlook_response(self) -> str:
        return """**Market Outlook - February 2026**

**Current Assessment: Cautiously Bullish**

The market continues to show resilience with the S&P 500 holding above key support levels. Key observations:

**Positives:**
- Earnings season coming in better than expected
- Inflation trending toward Fed targets
- Strong employment data supporting consumer spending

**Concerns:**
- Valuations stretched in large-cap tech
- Geopolitical tensions remain elevated
- Credit spreads starting to widen

**Sector Views:**
- Overweight: Healthcare, Financials
- Neutral: Technology, Consumer Discretionary
- Underweight: Utilities, Real Estate

**Trading Stance:** Stay invested but be selective. Focus on quality companies with pricing power. Keep 5-10% in cash for opportunistic deployment."""

    def _mock_risk_response(self) -> str:
        return """**Portfolio Risk Assessment**

**Overall Risk Score: 6.5/10 (Moderate)**

**Key Risks Identified:**

1. **Concentration Risk (Medium)**
   - Top 5 positions = 42% of portfolio
   - Recommendation: Trim positions >10%

2. **Sector Risk (Medium)**
   - Tech overweight at 35% vs 28% benchmark
   - Consider rotating into underweight sectors

3. **Correlation Risk (Low)**
   - Position correlation = 0.45
   - Good diversification benefit

4. **Hedging Opportunities:**
   - Consider SPY puts for tail risk protection
   - VIX calls provide cheap portfolio insurance

**Priority Actions:**
1. Reduce NVDA position by 3%
2. Add defensive healthcare (UNH, JNJ)
3. Consider 2% allocation to short-term treasuries"""

    def _mock_symbol_research_response(self, symbol: str) -> str:
        return f"""**{symbol} Analysis**

**Company Overview:** Leading technology company with diversified revenue streams across multiple high-growth markets.

**Recent Performance:**
- YTD Return: +18.5%
- vs S&P 500: +6.2% outperformance
- 52-week range: $145 - $195

**Key Fundamentals:**
- P/E: 25.3x (vs sector 28.1x)
- Revenue Growth: +12% YoY
- Gross Margin: 45.2%
- Free Cash Flow Yield: 4.1%

**Technical Setup:**
- Trend: Bullish, above 50/200 DMA
- RSI: 58 (neutral)
- Support: $165 / $155
- Resistance: $190 / $200

**Sentiment:**
- Analyst consensus: 85% Buy
- Short interest: 2.1%
- Options flow: Bullish

**Upcoming Catalysts:**
- Earnings: Feb 15, 2026
- Product launch event: March 2026

**Recommendation: BUY**
Entry: $175-180 range
Target: $210 (12-month)
Stop: $160 (-8%)

Risk/Reward: 3.2:1"""

    def _mock_general_response(self) -> str:
        return """I'm your AI Trading Copilot, here to help with your investment decisions.

I can assist you with:
- **Portfolio Analysis**: Review your holdings and suggest improvements
- **Trade Ideas**: Generate buy/sell recommendations based on your preferences
- **Stock Research**: Deep dive analysis on any symbol
- **Market Outlook**: Current market conditions and sector views
- **Risk Assessment**: Identify and address portfolio risks

Just ask me about a specific stock, your portfolio, or any trading-related question!

For example, try:
- "What do you think about AAPL?"
- "Review my portfolio for risks"
- "Give me a trade idea in the tech sector"
- "What's the market outlook today?" """
