"""Performance Tracker — rolling metrics per signal source.

Tracks win rate, Sharpe ratio, and average P&L per signal source
over configurable rolling windows. Feeds into the weight adjuster.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TrackerConfig:
    """Configuration for the performance tracker.

    Attributes:
        rolling_window: Number of trades for rolling metrics.
        min_trades_for_stats: Minimum trades before stats are meaningful.
        decay_factor: Exponential decay for older trades (0-1).
        risk_free_rate: Annualized risk-free rate for Sharpe calculation.
    """

    rolling_window: int = 100
    min_trades_for_stats: int = 10
    decay_factor: float = 0.95
    risk_free_rate: float = 0.05


@dataclass
class SourcePerformance:
    """Performance metrics for a signal source.

    Attributes:
        source: Signal source name.
        trade_count: Total trades attributed to this source.
        win_count: Number of profitable trades.
        win_rate: Win rate as fraction (0-1).
        total_pnl: Total P&L from this source's signals.
        avg_pnl: Average P&L per trade.
        sharpe_ratio: Rolling Sharpe ratio (annualized).
        profit_factor: Sum of wins / abs(sum of losses).
        avg_conviction: Average conviction of signals from this source.
        last_updated: When metrics were last refreshed.
    """

    source: str = ""
    trade_count: int = 0
    win_count: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    avg_conviction: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "trade_count": self.trade_count,
            "win_count": self.win_count,
            "win_rate": round(self.win_rate, 3),
            "total_pnl": round(self.total_pnl, 2),
            "avg_pnl": round(self.avg_pnl, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "profit_factor": round(self.profit_factor, 2),
            "avg_conviction": round(self.avg_conviction, 1),
            "last_updated": self.last_updated.isoformat(),
        }


class PerformanceTracker:
    """Tracks rolling performance metrics per signal source.

    Records trade outcomes attributed to each source and maintains
    rolling statistics that the WeightAdjuster uses to modify fusion weights.

    Args:
        config: TrackerConfig with window and threshold settings.

    Example:
        tracker = PerformanceTracker()
        tracker.record_outcome("ema_cloud", pnl=150.0, conviction=82.0)
        tracker.record_outcome("social", pnl=-50.0, conviction=65.0)
        perf = tracker.get_performance("ema_cloud")
        print(f"EMA Sharpe: {perf.sharpe_ratio:.2f}")
    """

    def __init__(self, config: TrackerConfig | None = None) -> None:
        self.config = config or TrackerConfig()
        # Per-source trade history: list of (pnl, conviction)
        self._history: dict[str, list[tuple[float, float]]] = defaultdict(list)

    def record_outcome(
        self, source: str, pnl: float, conviction: float = 50.0
    ) -> None:
        """Record a trade outcome for a signal source.

        Args:
            source: Signal source name (e.g. "ema_cloud").
            pnl: Realized P&L from this trade.
            conviction: The conviction score of the signal that triggered it.
        """
        history = self._history[source]
        history.append((pnl, conviction))
        # Trim to rolling window
        if len(history) > self.config.rolling_window:
            self._history[source] = history[-self.config.rolling_window:]

    def get_performance(self, source: str) -> SourcePerformance:
        """Compute current performance metrics for a source.

        Args:
            source: Signal source name.

        Returns:
            SourcePerformance with rolling statistics.
        """
        history = self._history.get(source, [])
        if not history:
            return SourcePerformance(source=source)

        pnls = [h[0] for h in history]
        convictions = [h[1] for h in history]
        n = len(pnls)

        total_pnl = sum(pnls)
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        win_rate = len(wins) / max(n, 1)
        avg_pnl = total_pnl / max(n, 1)
        avg_conviction = sum(convictions) / max(n, 1)

        # Sharpe ratio
        sharpe = self._compute_sharpe(pnls)

        # Profit factor
        sum_wins = sum(wins) if wins else 0.0
        sum_losses = abs(sum(losses)) if losses else 0.0
        profit_factor = sum_wins / max(sum_losses, 0.01)

        return SourcePerformance(
            source=source,
            trade_count=n,
            win_count=len(wins),
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl=avg_pnl,
            sharpe_ratio=sharpe,
            profit_factor=profit_factor,
            avg_conviction=avg_conviction,
        )

    def get_all_performance(self) -> dict[str, SourcePerformance]:
        """Get performance for all tracked sources."""
        return {source: self.get_performance(source) for source in self._history}

    def get_ranked_sources(self) -> list[SourcePerformance]:
        """Get sources ranked by Sharpe ratio (highest first)."""
        all_perf = self.get_all_performance()
        ranked = sorted(
            all_perf.values(),
            key=lambda p: p.sharpe_ratio,
            reverse=True,
        )
        return ranked

    def _compute_sharpe(self, pnls: list[float]) -> float:
        """Compute annualized Sharpe ratio from P&L series."""
        if len(pnls) < self.config.min_trades_for_stats:
            return 0.0

        mean = sum(pnls) / len(pnls)
        variance = sum((p - mean) ** 2 for p in pnls) / len(pnls)
        std = math.sqrt(variance) if variance > 0 else 0.0

        if std < 1e-10:
            return 0.0

        # Daily Sharpe → annualized (approx 252 trading days)
        daily_sharpe = (mean - self.config.risk_free_rate / 252) / std
        return daily_sharpe * math.sqrt(252)
