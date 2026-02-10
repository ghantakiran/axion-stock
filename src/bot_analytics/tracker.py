"""PRD-175: Bot Performance Tracker — rolling equity and real-time metrics.

Records every trade close and maintains a rolling equity curve,
per-signal breakdowns, and per-strategy breakdowns. Produces
PerformanceSnapshot on demand.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.bot_analytics.metrics import calmar_ratio, max_drawdown, sharpe_ratio, sortino_ratio
from src.bot_analytics.snapshot import PerformanceSnapshot

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """A completed trade for analytics."""

    ticker: str
    direction: str
    pnl: float
    signal_type: str = "unknown"
    strategy: str = "unknown"
    entry_price: float = 0.0
    exit_price: float = 0.0
    shares: float = 0.0
    exit_reason: str = ""
    closed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BotPerformanceTracker:
    """Tracks real-time bot performance with per-signal and per-strategy breakdowns.

    Maintains a rolling equity curve and computes metrics on demand.

    Args:
        max_history: Maximum trade records to keep.
        starting_equity: Starting equity for equity curve baseline.
    """

    def __init__(
        self,
        max_history: int = 10_000,
        starting_equity: float = 100_000.0,
    ) -> None:
        self._trades: list[TradeRecord] = []
        self._max_history = max_history
        self._starting_equity = starting_equity
        self._equity = starting_equity
        self._peak_equity = starting_equity
        self._equity_curve: list[float] = [starting_equity]

        # Per-signal breakdown
        self._by_signal: dict[str, list[float]] = defaultdict(list)
        # Per-strategy breakdown
        self._by_strategy: dict[str, list[float]] = defaultdict(list)

    def record_trade(
        self,
        ticker: str,
        direction: str,
        pnl: float,
        signal_type: str = "unknown",
        strategy: str = "unknown",
        entry_price: float = 0.0,
        exit_price: float = 0.0,
        shares: float = 0.0,
        exit_reason: str = "",
    ) -> None:
        """Record a completed trade.

        Args:
            ticker: Symbol traded.
            direction: 'long' or 'short'.
            pnl: Realized P&L.
            signal_type: Signal type that triggered the trade.
            strategy: Strategy that produced the signal.
            entry_price: Entry price.
            exit_price: Exit price.
            shares: Number of shares.
            exit_reason: Why the position was closed.
        """
        record = TradeRecord(
            ticker=ticker,
            direction=direction,
            pnl=pnl,
            signal_type=signal_type,
            strategy=strategy,
            entry_price=entry_price,
            exit_price=exit_price,
            shares=shares,
            exit_reason=exit_reason,
        )
        self._trades.append(record)
        if len(self._trades) > self._max_history:
            self._trades = self._trades[-self._max_history:]

        # Update equity curve
        self._equity += pnl
        self._equity_curve.append(self._equity)
        if self._equity > self._peak_equity:
            self._peak_equity = self._equity

        # Track by signal type and strategy
        self._by_signal[signal_type].append(pnl)
        self._by_strategy[strategy].append(pnl)

    def get_snapshot(self) -> PerformanceSnapshot:
        """Generate a point-in-time performance snapshot."""
        pnls = [t.pnl for t in self._trades]
        n = len(pnls)

        if n == 0:
            return PerformanceSnapshot(equity_curve=list(self._equity_curve))

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        total_pnl = sum(pnls)

        # Breakdown by signal type
        by_signal = {}
        for sig_type, sig_pnls in self._by_signal.items():
            sig_wins = [p for p in sig_pnls if p > 0]
            by_signal[sig_type] = {
                "trades": len(sig_pnls),
                "wins": len(sig_wins),
                "win_rate": round(len(sig_wins) / max(len(sig_pnls), 1), 3),
                "total_pnl": round(sum(sig_pnls), 2),
                "avg_pnl": round(sum(sig_pnls) / max(len(sig_pnls), 1), 2),
                "sharpe": round(sharpe_ratio(sig_pnls), 2),
            }

        # Breakdown by strategy
        by_strategy = {}
        for strat, strat_pnls in self._by_strategy.items():
            strat_wins = [p for p in strat_pnls if p > 0]
            by_strategy[strat] = {
                "trades": len(strat_pnls),
                "wins": len(strat_wins),
                "win_rate": round(len(strat_wins) / max(len(strat_pnls), 1), 3),
                "total_pnl": round(sum(strat_pnls), 2),
                "avg_pnl": round(sum(strat_pnls) / max(len(strat_pnls), 1), 2),
                "sharpe": round(sharpe_ratio(strat_pnls), 2),
            }

        current_dd = self._peak_equity - self._equity

        return PerformanceSnapshot(
            total_trades=n,
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=len(wins) / max(n, 1),
            total_pnl=total_pnl,
            avg_pnl=total_pnl / max(n, 1),
            sharpe=sharpe_ratio(pnls),
            sortino=sortino_ratio(pnls),
            calmar=calmar_ratio(pnls),
            max_drawdown=max_drawdown(pnls),
            current_drawdown=current_dd,
            by_signal=by_signal,
            by_strategy=by_strategy,
            equity_curve=list(self._equity_curve[-500:]),
        )

    def get_equity(self) -> float:
        """Get current equity."""
        return self._equity

    def get_trade_count(self) -> int:
        """Get total trade count."""
        return len(self._trades)

    def get_recent_trades(self, limit: int = 20) -> list[dict]:
        """Get recent trade records."""
        return [
            {
                "ticker": t.ticker,
                "direction": t.direction,
                "pnl": round(t.pnl, 2),
                "signal_type": t.signal_type,
                "strategy": t.strategy,
                "exit_reason": t.exit_reason,
                "closed_at": t.closed_at.isoformat(),
            }
            for t in self._trades[-limit:]
        ]
