"""PRD-175: Performance Snapshot — point-in-time analytics state.

Immutable dataclass capturing all performance metrics at a moment,
including breakdowns by signal type and strategy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class PerformanceSnapshot:
    """Point-in-time performance snapshot.

    Attributes:
        total_trades: Total trades since tracking began.
        winning_trades: Number of profitable trades.
        losing_trades: Number of losing trades.
        win_rate: Win rate as fraction 0.0-1.0.
        total_pnl: Total realized P&L.
        avg_pnl: Average P&L per trade.
        sharpe: Annualized Sharpe ratio.
        sortino: Annualized Sortino ratio.
        calmar: Calmar ratio.
        max_drawdown: Maximum drawdown in dollars.
        current_drawdown: Current drawdown from peak.
        by_signal: Performance breakdown by signal type.
        by_strategy: Performance breakdown by strategy.
        equity_curve: Recent equity values.
        timestamp: When the snapshot was taken.
    """

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    calmar: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    by_signal: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_strategy: dict[str, dict[str, Any]] = field(default_factory=dict)
    equity_curve: list[float] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 3),
            "total_pnl": round(self.total_pnl, 2),
            "avg_pnl": round(self.avg_pnl, 2),
            "sharpe": round(self.sharpe, 2),
            "sortino": round(self.sortino, 2),
            "calmar": round(self.calmar, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "current_drawdown": round(self.current_drawdown, 2),
            "by_signal": self.by_signal,
            "by_strategy": self.by_strategy,
            "equity_curve_len": len(self.equity_curve),
            "timestamp": self.timestamp.isoformat(),
        }
