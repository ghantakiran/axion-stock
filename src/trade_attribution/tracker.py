"""Rolling Signal Performance Tracker.

Maintains running statistics for each signal type across configurable
time windows. Supports regime-aware tracking and exponential decay.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict
import statistics


@dataclass
class RollingSignalStats:
    """Performance statistics for a signal type within a time window."""

    signal_type: str = ""
    window: str = "all_time"
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    avg_pnl_pct: float = 0.0
    profit_factor: float = 0.0
    avg_conviction: float = 0.0
    avg_hold_hours: float = 0.0
    avg_entry_score: float = 0.0
    avg_exit_score: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    sharpe_ratio: float = 0.0

    def to_dict(self) -> dict:
        return {
            "signal_type": self.signal_type,
            "window": self.window,
            "trade_count": self.trade_count,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": round(self.win_rate, 4),
            "total_pnl": round(self.total_pnl, 2),
            "avg_pnl": round(self.avg_pnl, 2),
            "avg_pnl_pct": round(self.avg_pnl_pct, 4),
            "profit_factor": round(self.profit_factor, 2),
            "avg_conviction": round(self.avg_conviction, 1),
            "avg_hold_hours": round(self.avg_hold_hours, 1),
            "avg_entry_score": round(self.avg_entry_score, 3),
            "avg_exit_score": round(self.avg_exit_score, 3),
            "best_trade": round(self.best_trade, 2),
            "worst_trade": round(self.worst_trade, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
        }


@dataclass
class TrackerSnapshot:
    """Point-in-time snapshot of all signal performance."""

    timestamp: Optional[datetime] = None
    by_signal_type: dict[str, list[RollingSignalStats]] = field(
        default_factory=dict
    )
    by_regime: dict[str, list[RollingSignalStats]] = field(default_factory=dict)
    overall: Optional[RollingSignalStats] = None

    def get_best_signal_type(self, window: str = "all_time") -> str:
        best_type = ""
        best_pf = 0.0
        for sig_type, stats_list in self.by_signal_type.items():
            for s in stats_list:
                if (
                    s.window == window
                    and s.profit_factor > best_pf
                    and s.trade_count >= 5
                ):
                    best_pf = s.profit_factor
                    best_type = sig_type
        return best_type

    def get_worst_signal_type(self, window: str = "all_time") -> str:
        worst_type = ""
        worst_pf = float("inf")
        for sig_type, stats_list in self.by_signal_type.items():
            for s in stats_list:
                if s.window == window and s.trade_count >= 5:
                    if s.profit_factor < worst_pf:
                        worst_pf = s.profit_factor
                        worst_type = sig_type
        return worst_type

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else "",
            "by_signal_type": {
                k: [s.to_dict() for s in v]
                for k, v in self.by_signal_type.items()
            },
            "by_regime": {
                k: [s.to_dict() for s in v]
                for k, v in self.by_regime.items()
            },
            "overall": self.overall.to_dict() if self.overall else {},
        }

    def to_dataframe(self):
        import pandas as pd

        rows = []
        for sig_type, stats_list in self.by_signal_type.items():
            for s in stats_list:
                rows.append(s.to_dict())
        return pd.DataFrame(rows) if rows else pd.DataFrame()


class SignalPerformanceTracker:
    """Tracks rolling performance of signal types with window support."""

    def __init__(self, config: Optional[AttributionConfig] = None):
        from src.trade_attribution.config import AttributionConfig, TimeWindow

        self.config = config or AttributionConfig()
        self._trades: list[dict] = []  # All linked trade data

    def record_trade(self, linked_trade) -> None:
        """Record a linked trade for tracking."""
        self._trades.append(
            {
                "signal_type": linked_trade.signal_type,
                "conviction": linked_trade.signal_conviction,
                "pnl": linked_trade.realized_pnl,
                "pnl_pct": linked_trade.realized_pnl_pct,
                "hold_hours": linked_trade.hold_duration_hours,
                "entry_score": getattr(linked_trade, "entry_score", 0.0),
                "exit_score": getattr(linked_trade, "exit_score", 0.0),
                "regime": linked_trade.regime_at_entry,
                "timestamp": linked_trade.exit_time or datetime.utcnow(),
                "is_winner": linked_trade.is_winner,
            }
        )

    def get_snapshot(self) -> TrackerSnapshot:
        """Generate a point-in-time performance snapshot."""
        from src.trade_attribution.config import TimeWindow

        now = datetime.utcnow()
        snapshot = TrackerSnapshot(timestamp=now)

        # Group by signal type
        by_type = defaultdict(list)
        for t in self._trades:
            by_type[t["signal_type"]].append(t)

        for sig_type, trades in by_type.items():
            stats_list = []
            for window in self.config.windows:
                filtered = self._filter_by_window(trades, window, now)
                if filtered:
                    stats = self._compute_stats(sig_type, window.value, filtered)
                    stats_list.append(stats)
            snapshot.by_signal_type[sig_type] = stats_list

        # By regime
        if self.config.track_by_regime:
            by_regime = defaultdict(list)
            for t in self._trades:
                regime = t.get("regime", "") or "unknown"
                by_regime[regime].append(t)
            for regime, trades in by_regime.items():
                stats = self._compute_stats(
                    f"all_{regime}", "all_time", trades
                )
                snapshot.by_regime[regime] = [stats]

        # Overall
        if self._trades:
            snapshot.overall = self._compute_stats(
                "all", "all_time", self._trades
            )

        return snapshot

    def _filter_by_window(
        self, trades: list[dict], window, now: datetime
    ) -> list[dict]:
        from src.trade_attribution.config import TimeWindow

        if window == TimeWindow.ALL_TIME:
            return trades

        count_windows = {
            TimeWindow.LAST_20: 20,
            TimeWindow.LAST_50: 50,
            TimeWindow.LAST_100: 100,
        }
        if window in count_windows:
            return trades[-count_windows[window] :]

        day_windows = {
            TimeWindow.LAST_7D: 7,
            TimeWindow.LAST_30D: 30,
            TimeWindow.LAST_90D: 90,
        }
        if window in day_windows:
            cutoff = now - timedelta(days=day_windows[window])
            return [
                t for t in trades if t.get("timestamp", now) >= cutoff
            ]

        return trades

    def _compute_stats(
        self, sig_type: str, window: str, trades: list[dict]
    ) -> RollingSignalStats:
        n = len(trades)
        if n == 0:
            return RollingSignalStats(signal_type=sig_type, window=window)

        wins = [t for t in trades if t["is_winner"]]
        losses = [t for t in trades if not t["is_winner"]]
        total_pnl = sum(t["pnl"] for t in trades)
        gross_profit = sum(t["pnl"] for t in wins) if wins else 0.0
        gross_loss = abs(sum(t["pnl"] for t in losses)) if losses else 0.0
        pnl_list = [t["pnl"] for t in trades]

        # Sharpe (annualized, assuming daily)
        if len(pnl_list) >= 2:
            mean_r = statistics.mean(pnl_list)
            std_r = statistics.stdev(pnl_list)
            sharpe = (mean_r / std_r * (252**0.5)) if std_r > 0 else 0.0
        else:
            sharpe = 0.0

        return RollingSignalStats(
            signal_type=sig_type,
            window=window,
            trade_count=n,
            win_count=len(wins),
            loss_count=len(losses),
            win_rate=len(wins) / n,
            total_pnl=total_pnl,
            avg_pnl=total_pnl / n,
            avg_pnl_pct=sum(t["pnl_pct"] for t in trades) / n,
            profit_factor=(
                gross_profit / gross_loss
                if gross_loss > 0
                else (999.0 if gross_profit > 0 else 0.0)
            ),
            avg_conviction=sum(t["conviction"] for t in trades) / n,
            avg_hold_hours=sum(t["hold_hours"] for t in trades) / n,
            avg_entry_score=sum(t.get("entry_score", 0) for t in trades) / n,
            avg_exit_score=sum(t.get("exit_score", 0) for t in trades) / n,
            best_trade=max(pnl_list),
            worst_trade=min(pnl_list),
            sharpe_ratio=sharpe,
        )

    def get_trade_count(self) -> int:
        return len(self._trades)

    def clear(self) -> None:
        self._trades.clear()
