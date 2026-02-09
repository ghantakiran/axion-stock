"""Signal-type performance attribution.

Tracks which EMA signal types (cloud cross, cloud flip, bounce, etc.)
contribute most to P&L, enabling data-driven signal selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.backtesting.models import Trade


@dataclass
class SignalTypeStats:
    """Performance statistics for a single signal type."""

    signal_type: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    avg_pnl_pct: float = 0.0
    avg_hold_bars: float = 0.0
    avg_conviction: float = 0.0
    profit_factor: float = 0.0
    best_trade_pnl: float = 0.0
    worst_trade_pnl: float = 0.0

    def to_dict(self) -> dict:
        return {
            "signal_type": self.signal_type,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "total_pnl": round(self.total_pnl, 2),
            "avg_pnl": round(self.avg_pnl, 2),
            "avg_pnl_pct": round(self.avg_pnl_pct, 4),
            "avg_hold_bars": round(self.avg_hold_bars, 1),
            "avg_conviction": round(self.avg_conviction, 1),
            "profit_factor": round(self.profit_factor, 2),
            "best_trade_pnl": round(self.best_trade_pnl, 2),
            "worst_trade_pnl": round(self.worst_trade_pnl, 2),
        }


@dataclass
class AttributionReport:
    """Full attribution report across all signal types."""

    by_signal_type: dict[str, SignalTypeStats] = field(default_factory=dict)
    by_direction: dict[str, SignalTypeStats] = field(default_factory=dict)
    by_exit_reason: dict[str, SignalTypeStats] = field(default_factory=dict)
    total_signals_generated: int = 0
    total_signals_executed: int = 0
    conversion_rate: float = 0.0

    def get_best_signal_type(self) -> Optional[str]:
        """Return the signal type with the highest total PnL."""
        if not self.by_signal_type:
            return None
        return max(
            self.by_signal_type,
            key=lambda k: self.by_signal_type[k].total_pnl,
        )

    def get_worst_signal_type(self) -> Optional[str]:
        """Return the signal type with the lowest total PnL."""
        if not self.by_signal_type:
            return None
        return min(
            self.by_signal_type,
            key=lambda k: self.by_signal_type[k].total_pnl,
        )

    def to_dataframe(self) -> pd.DataFrame:
        """Convert attribution by signal type to DataFrame."""
        if not self.by_signal_type:
            return pd.DataFrame()
        rows = [stats.to_dict() for stats in self.by_signal_type.values()]
        return pd.DataFrame(rows).set_index("signal_type")


class SignalAttributor:
    """Compute signal-type-level performance attribution.

    Matches completed trades to their originating signal type
    using the strategy's signal log, then computes per-type
    performance statistics.
    """

    def compute(
        self, signal_log: list[dict], trades: list[Trade]
    ) -> AttributionReport:
        """Build attribution report from signal log and completed trades.

        Args:
            signal_log: List of dicts from EMACloudStrategy.get_signal_log()
            trades: List of Trade objects from backtest results.

        Returns:
            AttributionReport with stats grouped by signal type, direction, exit reason.
        """
        if not signal_log or not trades:
            return AttributionReport(
                total_signals_generated=len(signal_log),
                total_signals_executed=0,
                conversion_rate=0.0,
            )

        # Build lookup from signal log keyed by (symbol, entry_date)
        log_lookup: dict[tuple, dict] = {}
        for entry in signal_log:
            key = (entry["symbol"], entry.get("entry_date"))
            log_lookup[key] = entry

        # Match trades to signal log entries
        matched: list[tuple[Trade, dict]] = []
        for trade in trades:
            # Try exact match first
            key = (trade.symbol, trade.entry_date)
            log_entry = log_lookup.get(key)

            if not log_entry:
                # Fuzzy match: find closest entry date for this symbol
                log_entry = self._find_closest(trade.symbol, trade.entry_date, signal_log)

            if log_entry:
                matched.append((trade, log_entry))

        # Group by signal type
        by_signal_type = self._group_and_compute(
            matched, key_fn=lambda t, l: l.get("signal_type", "unknown")
        )

        # Group by direction
        by_direction = self._group_and_compute(
            matched, key_fn=lambda t, l: l.get("direction", "unknown")
        )

        # Group by exit reason
        by_exit_reason = self._group_and_compute(
            matched, key_fn=lambda t, l: l.get("exit_reason", "unknown")
        )

        conversion_rate = (
            len(matched) / len(signal_log) if signal_log else 0.0
        )

        return AttributionReport(
            by_signal_type=by_signal_type,
            by_direction=by_direction,
            by_exit_reason=by_exit_reason,
            total_signals_generated=len(signal_log),
            total_signals_executed=len(matched),
            conversion_rate=conversion_rate,
        )

    def _find_closest(
        self, symbol: str, entry_date, signal_log: list[dict]
    ) -> Optional[dict]:
        """Find the signal log entry closest in time for a given symbol."""
        candidates = [
            e for e in signal_log
            if e["symbol"] == symbol and e.get("entry_date") is not None
        ]
        if not candidates:
            return None

        return min(
            candidates,
            key=lambda e: abs((e["entry_date"] - entry_date).total_seconds())
            if hasattr(entry_date, 'total_seconds') or hasattr(e["entry_date"], 'total_seconds')
            else abs((e["entry_date"] - entry_date).days),
        )

    def _group_and_compute(
        self,
        matched: list[tuple[Trade, dict]],
        key_fn,
    ) -> dict[str, SignalTypeStats]:
        """Group matched trades by a key function and compute stats."""
        groups: dict[str, list[tuple[Trade, dict]]] = {}
        for trade, log_entry in matched:
            key = key_fn(trade, log_entry)
            groups.setdefault(key, []).append((trade, log_entry))

        result: dict[str, SignalTypeStats] = {}
        for key, items in groups.items():
            trades_in_group = [t for t, _ in items]
            convictions = [l.get("conviction", 0) for _, l in items]

            pnls = [t.pnl for t in trades_in_group]
            winners = [p for p in pnls if p > 0]
            losers = [p for p in pnls if p <= 0]

            gross_profit = sum(winners) if winners else 0.0
            gross_loss = abs(sum(losers)) if losers else 0.0

            result[key] = SignalTypeStats(
                signal_type=key,
                total_trades=len(trades_in_group),
                winning_trades=len(winners),
                losing_trades=len(losers),
                win_rate=len(winners) / len(trades_in_group) if trades_in_group else 0,
                total_pnl=sum(pnls),
                avg_pnl=sum(pnls) / len(pnls) if pnls else 0,
                avg_pnl_pct=(
                    sum(t.pnl_pct for t in trades_in_group) / len(trades_in_group)
                    if trades_in_group else 0
                ),
                avg_hold_bars=(
                    sum(t.hold_days for t in trades_in_group) / len(trades_in_group)
                    if trades_in_group else 0
                ),
                avg_conviction=(
                    sum(convictions) / len(convictions) if convictions else 0
                ),
                profit_factor=(
                    gross_profit / gross_loss if gross_loss > 0 else float("inf")
                ),
                best_trade_pnl=max(pnls) if pnls else 0,
                worst_trade_pnl=min(pnls) if pnls else 0,
            )

        return result
