"""PRD-177: Base Strategy Protocol — interface all bot strategies must implement.

The BotStrategy Protocol requires a single `analyze()` method that
takes OHLCV bars and returns an optional TradeSignal.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from src.ema_signals.detector import TradeSignal


@runtime_checkable
class BotStrategy(Protocol):
    """Protocol for bot-compatible trading strategies.

    All strategies must implement `analyze()` which takes
    a ticker and OHLCV bars, returning a TradeSignal if a
    trade opportunity is detected, or None otherwise.
    """

    @property
    def name(self) -> str:
        """Strategy name for identification."""
        ...

    def analyze(
        self,
        ticker: str,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> Optional[TradeSignal]:
        """Analyze OHLCV bars and optionally generate a trade signal.

        Args:
            ticker: Symbol to analyze.
            opens: Open prices.
            highs: High prices.
            lows: Low prices.
            closes: Close prices.
            volumes: Volume data.

        Returns:
            TradeSignal if an opportunity is found, None otherwise.
        """
        ...
