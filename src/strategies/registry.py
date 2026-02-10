"""PRD-177: Strategy Registry — register, discover, and swap strategies.

Provides a central registry for all bot-compatible strategies,
supporting dynamic registration and strategy discovery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.ema_signals.detector import TradeSignal
from src.strategies.base import BotStrategy

logger = logging.getLogger(__name__)


@dataclass
class StrategyInfo:
    """Metadata about a registered strategy."""

    name: str
    description: str = ""
    category: str = "general"
    enabled: bool = True
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "enabled": self.enabled,
            "registered_at": self.registered_at.isoformat(),
        }


class StrategyRegistry:
    """Central registry for bot trading strategies.

    Supports dynamic registration, enabling/disabling, and batch analysis.

    Example:
        registry = StrategyRegistry()
        registry.register(VWAPStrategy(), description="VWAP mean-reversion")
        registry.register(ORBStrategy(), description="Opening range breakout")

        signals = registry.analyze_all("AAPL", opens, highs, lows, closes, volumes)
    """

    def __init__(self) -> None:
        self._strategies: dict[str, BotStrategy] = {}
        self._info: dict[str, StrategyInfo] = {}

    def register(
        self,
        strategy: BotStrategy,
        description: str = "",
        category: str = "general",
    ) -> None:
        """Register a strategy.

        Args:
            strategy: Strategy instance implementing BotStrategy protocol.
            description: Human-readable description.
            category: Strategy category for grouping.
        """
        name = strategy.name
        self._strategies[name] = strategy
        self._info[name] = StrategyInfo(
            name=name,
            description=description,
            category=category,
        )
        logger.info("Strategy registered: %s (%s)", name, category)

    def unregister(self, name: str) -> bool:
        """Remove a strategy from the registry.

        Returns:
            True if the strategy was found and removed.
        """
        if name in self._strategies:
            del self._strategies[name]
            del self._info[name]
            return True
        return False

    def enable(self, name: str) -> bool:
        """Enable a strategy."""
        if name in self._info:
            self._info[name].enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a strategy."""
        if name in self._info:
            self._info[name].enabled = False
            return True
        return False

    def get_strategy(self, name: str) -> Optional[BotStrategy]:
        """Get a strategy by name."""
        return self._strategies.get(name)

    def get_enabled_strategies(self) -> list[BotStrategy]:
        """Get all enabled strategies."""
        return [
            self._strategies[name]
            for name, info in self._info.items()
            if info.enabled and name in self._strategies
        ]

    def list_strategies(self) -> list[dict]:
        """List all registered strategies with metadata."""
        return [info.to_dict() for info in self._info.values()]

    def analyze_all(
        self,
        ticker: str,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> list[tuple[str, TradeSignal]]:
        """Run all enabled strategies and collect signals.

        Args:
            ticker: Symbol to analyze.
            opens/highs/lows/closes/volumes: OHLCV data.

        Returns:
            List of (strategy_name, TradeSignal) for strategies that fired.
        """
        results = []
        for strategy in self.get_enabled_strategies():
            try:
                signal = strategy.analyze(ticker, opens, highs, lows, closes, volumes)
                if signal is not None:
                    results.append((strategy.name, signal))
            except Exception as e:
                logger.warning("Strategy %s failed on %s: %s", strategy.name, ticker, e)
        return results

    def get_strategy_count(self) -> int:
        """Get total number of registered strategies."""
        return len(self._strategies)
