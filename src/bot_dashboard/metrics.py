"""Performance metrics calculator for the trading bot.

Computes win rate, profit factor, Sharpe ratio, max drawdown,
expectancy, and breakdowns by ticker/conviction/time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional


@dataclass
class DailyMetrics:
    """Computed metrics for a single trading day."""

    date: date
    total_trades: int
    winners: int
    losers: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    net_pnl: float
    profit_factor: float
    avg_winner: float
    avg_loser: float
    largest_winner: float
    largest_loser: float
    avg_hold_minutes: float

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate, 4),
            "net_pnl": round(self.net_pnl, 2),
            "profit_factor": round(self.profit_factor, 2),
        }


class PerformanceMetrics:
    """Compute trading performance metrics from trade records."""

    def daily_metrics(self, trades: list) -> DailyMetrics:
        """Compute metrics for a list of trades (assumed same day)."""
        if not trades:
            return DailyMetrics(
                date=date.today(), total_trades=0, winners=0, losers=0,
                win_rate=0.0, gross_profit=0.0, gross_loss=0.0,
                net_pnl=0.0, profit_factor=0.0, avg_winner=0.0,
                avg_loser=0.0, largest_winner=0.0, largest_loser=0.0,
                avg_hold_minutes=0.0,
            )

        winners = [t for t in trades if self._get_pnl(t) > 0]
        losers = [t for t in trades if self._get_pnl(t) <= 0]

        gross_profit = sum(self._get_pnl(t) for t in winners)
        gross_loss = sum(self._get_pnl(t) for t in losers)

        hold_minutes = []
        for t in trades:
            entry = getattr(t, "entry_time", None)
            exit_ = getattr(t, "exit_time", None)
            if entry and exit_:
                hold_minutes.append((exit_ - entry).total_seconds() / 60)

        return DailyMetrics(
            date=date.today(),
            total_trades=len(trades),
            winners=len(winners),
            losers=len(losers),
            win_rate=len(winners) / len(trades) if trades else 0.0,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_pnl=gross_profit + gross_loss,
            profit_factor=abs(gross_profit / gross_loss) if gross_loss != 0 else float("inf"),
            avg_winner=gross_profit / len(winners) if winners else 0.0,
            avg_loser=gross_loss / len(losers) if losers else 0.0,
            largest_winner=max((self._get_pnl(t) for t in winners), default=0.0),
            largest_loser=min((self._get_pnl(t) for t in losers), default=0.0),
            avg_hold_minutes=sum(hold_minutes) / len(hold_minutes) if hold_minutes else 0.0,
        )

    def win_rate_by_ticker(self, trades: list) -> dict[str, float]:
        """Compute win rate grouped by ticker."""
        tickers: dict[str, list] = {}
        for t in trades:
            ticker = self._get_field(t, "ticker", "UNKNOWN")
            tickers.setdefault(ticker, []).append(t)

        result = {}
        for ticker, ticker_trades in tickers.items():
            winners = sum(1 for t in ticker_trades if self._get_pnl(t) > 0)
            result[ticker] = winners / len(ticker_trades) if ticker_trades else 0.0
        return result

    def win_rate_by_conviction(self, trades: list) -> dict[str, float]:
        """Compute win rate grouped by conviction level."""
        buckets = {"high": [], "medium": [], "low": []}
        for t in trades:
            conv = self._get_field(t, "conviction", 0)
            if conv >= 75:
                buckets["high"].append(t)
            elif conv >= 50:
                buckets["medium"].append(t)
            else:
                buckets["low"].append(t)

        result = {}
        for level, level_trades in buckets.items():
            if level_trades:
                winners = sum(1 for t in level_trades if self._get_pnl(t) > 0)
                result[level] = winners / len(level_trades)
            else:
                result[level] = 0.0
        return result

    def profit_factor(self, trades: list) -> float:
        """Gross profit / abs(gross loss)."""
        gross_profit = sum(self._get_pnl(t) for t in trades if self._get_pnl(t) > 0)
        gross_loss = sum(self._get_pnl(t) for t in trades if self._get_pnl(t) <= 0)
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return abs(gross_profit / gross_loss)

    def expectancy(self, trades: list) -> float:
        """Expected P&L per trade: (win_rate * avg_win) - (loss_rate * avg_loss)."""
        if not trades:
            return 0.0
        winners = [t for t in trades if self._get_pnl(t) > 0]
        losers = [t for t in trades if self._get_pnl(t) <= 0]

        win_rate = len(winners) / len(trades)
        loss_rate = 1 - win_rate

        avg_win = sum(self._get_pnl(t) for t in winners) / len(winners) if winners else 0
        avg_loss = abs(sum(self._get_pnl(t) for t in losers) / len(losers)) if losers else 0

        return (win_rate * avg_win) - (loss_rate * avg_loss)

    def sharpe_ratio(self, daily_returns: list[float], risk_free_rate: float = 0.0) -> float:
        """Annualized Sharpe ratio from daily returns."""
        if len(daily_returns) < 2:
            return 0.0
        mean_r = sum(daily_returns) / len(daily_returns)
        var = sum((r - mean_r) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        std = math.sqrt(var) if var > 0 else 0
        if std == 0:
            return 0.0
        return (mean_r - risk_free_rate) * math.sqrt(252) / std

    def max_drawdown(self, equity_values: list[float]) -> float:
        """Maximum drawdown from equity curve."""
        if not equity_values:
            return 0.0
        peak = equity_values[0]
        max_dd = 0.0
        for val in equity_values:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        return max_dd

    @staticmethod
    def _get_field(trade, field: str, default=None):
        """Extract a field from a trade record (dict or object)."""
        if isinstance(trade, dict):
            return trade.get(field, default)
        return getattr(trade, field, default)

    @staticmethod
    def _get_pnl(trade) -> float:
        """Extract P&L from a trade record (dict or object)."""
        if isinstance(trade, dict):
            return trade.get("pnl", 0.0)
        return getattr(trade, "pnl", 0.0)
