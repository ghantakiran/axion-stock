"""PRD-173: Strategy Bridge — wraps StrategySelector for pipeline use.

Translates between the bot pipeline and the StrategySelector,
enabling ADX-gated strategy routing within the orchestrator.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.strategy_selector.selector import SelectorConfig, StrategyChoice, StrategySelector

logger = logging.getLogger(__name__)


@dataclass
class StrategyDecision:
    """Pipeline-friendly strategy decision."""

    ticker: str
    strategy: str  # 'ema_cloud' or 'mean_reversion'
    confidence: float
    adx_value: float
    reasoning: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "strategy": self.strategy,
            "confidence": round(self.confidence, 1),
            "adx_value": round(self.adx_value, 1),
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat(),
        }


class StrategyBridge:
    """Bridge between StrategySelector and the bot pipeline.

    Provides a simplified API for strategy selection and outcome recording.

    Args:
        config: SelectorConfig for the underlying selector.
    """

    def __init__(self, config: SelectorConfig | None = None) -> None:
        self._selector = StrategySelector(config)
        self._history: list[StrategyDecision] = []

    def select_strategy(
        self,
        ticker: str,
        highs: list[float],
        lows: list[float],
        closes: list[float],
        regime: str = "sideways",
    ) -> StrategyDecision:
        """Select the best strategy for the given market data.

        Args:
            ticker: Symbol to analyze.
            highs: High prices for ADX.
            lows: Low prices for ADX.
            closes: Close prices.
            regime: Current market regime.

        Returns:
            StrategyDecision with selected strategy.
        """
        choice = self._selector.select(ticker, highs, lows, closes, regime)

        decision = StrategyDecision(
            ticker=ticker,
            strategy=choice.selected_strategy,
            confidence=choice.confidence,
            adx_value=choice.adx_value,
            reasoning=choice.reasoning,
        )
        self._history.append(decision)
        if len(self._history) > 500:
            self._history = self._history[-500:]
        return decision

    def record_outcome(self, strategy: str, pnl: float) -> None:
        """Record a trade outcome for A/B tracking.

        Args:
            strategy: Which strategy was used.
            pnl: Realized P&L.
        """
        self._selector.record_outcome(strategy, pnl)

    def get_strategy_stats(self) -> dict[str, dict]:
        """Get strategy A/B comparison statistics."""
        return self._selector.get_strategy_stats()

    def get_decision_history(self, limit: int = 50) -> list[dict]:
        """Get recent strategy decisions."""
        return [d.to_dict() for d in self._history[-limit:]]
