"""Agent router — keyword-based intent classification to suggest agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.agents.config import AgentType


@dataclass
class AgentSuggestion:
    """A scored agent suggestion."""

    agent_type: AgentType
    confidence: float  # 0.0 – 1.0
    reason: str = ""


# ── Keyword groups mapped to agent types ──────────────────────────────

_KEYWORD_MAP: dict[AgentType, list[str]] = {
    AgentType.VALUE_ORACLE: [
        "value", "cheap", "undervalued", "PE", "PB", "P/E", "P/B",
        "margin of safety", "Buffett", "Graham", "intrinsic",
        "FCF", "free cash flow", "dividend", "moat", "bargain",
    ],
    AgentType.GROWTH_HUNTER: [
        "growth", "growing", "revenue growth", "TAM", "disrupt",
        "innovation", "high growth", "hyper growth", "10x",
        "fastest growing", "emerging", "next big",
    ],
    AgentType.MOMENTUM_RIDER: [
        "momentum", "trend", "breakout", "relative strength",
        "rotation", "sector rotation", "moving average",
        "52-week high", "technical", "rally", "surge",
    ],
    AgentType.INCOME_ARCHITECT: [
        "income", "dividend", "yield", "payout", "covered call",
        "cash flow", "passive income", "DRIP", "ex-div",
        "dividend aristocrat", "income stream",
    ],
    AgentType.RISK_SENTINEL: [
        "risk", "hedge", "protect", "VaR", "drawdown",
        "downside", "stop loss", "position sizing", "collar",
        "protective put", "volatility", "crash",
    ],
    AgentType.RESEARCH_ANALYST: [
        "research", "report", "deep dive", "earnings",
        "fundamental", "analysis", "bull case", "bear case",
        "competitive advantage", "catalyst",
    ],
    AgentType.PORTFOLIO_ARCHITECT: [
        "portfolio", "allocation", "diversify", "diversification",
        "rebalance", "weight", "sector balance", "correlation",
        "build portfolio", "allocate",
    ],
    AgentType.OPTIONS_STRATEGIST: [
        "options", "option", "calls", "puts", "iron condor",
        "spread", "straddle", "strangle", "Greeks", "IV",
        "implied volatility", "theta", "delta", "gamma",
    ],
    AgentType.MARKET_SCOUT: [
        "market overview", "market", "sector", "screening",
        "macro", "index", "S&P", "Nasdaq", "top picks",
        "scan", "what's moving", "broad market",
    ],
}

# Flatten for quick lookup
_KEYWORD_TO_AGENTS: dict[str, list[AgentType]] = {}
for _agent, _keywords in _KEYWORD_MAP.items():
    for _kw in _keywords:
        _lower = _kw.lower()
        if _lower not in _KEYWORD_TO_AGENTS:
            _KEYWORD_TO_AGENTS[_lower] = []
        _KEYWORD_TO_AGENTS[_lower].append(_agent)


class AgentRouter:
    """Suggests the best agent for a given query using keyword matching."""

    def classify_intent(self, query: str) -> list[AgentSuggestion]:
        """Return ranked list of (AgentType, confidence) for a query."""
        query_lower = query.lower()
        scores: dict[AgentType, float] = {}

        for keyword, agents in _KEYWORD_TO_AGENTS.items():
            if keyword in query_lower:
                for agent in agents:
                    scores[agent] = scores.get(agent, 0.0) + 1.0

        if not scores:
            return [AgentSuggestion(
                agent_type=AgentType.ALPHA_STRATEGIST,
                confidence=0.5,
                reason="Default: no strong keyword signal detected.",
            )]

        max_score = max(scores.values())
        suggestions = []
        for agent_type, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            confidence = min(score / max(max_score, 1.0), 1.0)
            name = agent_type.value.replace("_", " ").title()
            suggestions.append(AgentSuggestion(
                agent_type=agent_type,
                confidence=round(confidence, 2),
                reason=f"Matched keywords for {name}.",
            ))

        return suggestions

    def suggest_agent(self, query: str) -> AgentType:
        """Return the single best agent for a query."""
        suggestions = self.classify_intent(query)
        return suggestions[0].agent_type

    def should_suggest_switch(
        self,
        query: str,
        current_agent: AgentType,
    ) -> Optional[AgentSuggestion]:
        """Return a switch suggestion if a different agent is strongly recommended.

        Returns None if the current agent is already the best match.
        """
        suggestions = self.classify_intent(query)
        best = suggestions[0]

        if best.agent_type == current_agent:
            return None

        # Only suggest switch if confidence is significantly higher
        if best.confidence >= 0.7:
            return best

        return None
