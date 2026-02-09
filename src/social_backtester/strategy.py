"""Social Signal Backtesting Strategy.

Provides a simple long/short strategy driven by social signal scores.
Simulates portfolio management with position limits, stop losses,
and take profits.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StrategyConfig:
    """Configuration for social signal backtesting strategy."""

    min_score: float = 50.0
    direction_filter: str = "all"  # all, bullish, bearish
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    max_positions: int = 5
    position_weight: float = 0.1  # 10% per position


@dataclass
class SocialBacktestResult:
    """Result from a social signal backtest run."""

    total_return: float = 0.0
    trade_count: int = 0
    win_rate: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    equity_curve: list = field(default_factory=list)
    trades: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_return": round(self.total_return, 6),
            "trade_count": self.trade_count,
            "win_rate": round(self.win_rate, 4),
            "sharpe": round(self.sharpe, 3),
            "max_drawdown": round(self.max_drawdown, 6),
            "equity_curve_length": len(self.equity_curve),
            "sample_trades": [
                t if isinstance(t, dict) else t
                for t in self.trades[:20]
            ],
        }


class SocialSignalStrategy:
    """Backtesting strategy driven by social signal scores.

    For each signal:
    1. Check score >= min_score
    2. Check direction matches filter
    3. Check position count < max_positions
    4. Enter position, apply stop loss / take profit to subsequent bars
    """

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()

    def run(
        self,
        signals: list,
        prices: dict,
        initial_capital: float = 100_000.0,
    ) -> SocialBacktestResult:
        """Run backtest on archived signals against price data.

        Args:
            signals: List of ArchivedSignal objects (sorted by time).
            prices: Dict mapping ticker -> DataFrame with 'close'.
            initial_capital: Starting capital.

        Returns:
            SocialBacktestResult with performance metrics.
        """
        cfg = self.config
        capital = initial_capital
        positions: dict[str, dict] = {}  # ticker -> position info
        trades: list[dict] = []
        equity_curve = [capital]
        daily_returns: list[float] = []

        sorted_signals = sorted(signals, key=lambda s: s.signal_time)

        for sig in sorted_signals:
            # Filter by score
            if sig.composite_score < cfg.min_score:
                continue

            # Filter by direction
            if cfg.direction_filter != "all" and sig.direction != cfg.direction_filter:
                continue

            # Skip if already holding this ticker
            if sig.ticker in positions:
                continue

            # Check max positions
            if len(positions) >= cfg.max_positions:
                continue

            # Get price data
            price_df = prices.get(sig.ticker)
            if price_df is None or len(price_df) == 0:
                continue

            close_series = self._get_close_list(price_df)
            if not close_series:
                continue

            # Find entry index
            sig_date = sig.signal_time.date() if hasattr(sig.signal_time, 'date') else sig.signal_time
            entry_idx = self._find_date_index(close_series, sig_date)
            if entry_idx is None or entry_idx >= len(close_series) - 1:
                continue

            entry_price = close_series[entry_idx][1]
            position_size = capital * cfg.position_weight
            shares = position_size / entry_price if entry_price > 0 else 0

            if shares <= 0:
                continue

            # Simulate exit: scan forward for stop loss / take profit
            is_long = sig.direction != "bearish"
            exit_price = entry_price
            exit_reason = "end_of_data"

            for j in range(entry_idx + 1, min(entry_idx + 31, len(close_series))):
                bar_price = close_series[j][1]
                if is_long:
                    change = (bar_price - entry_price) / entry_price
                else:
                    change = (entry_price - bar_price) / entry_price

                if change <= -cfg.stop_loss_pct:
                    exit_price = bar_price
                    exit_reason = "stop_loss"
                    break
                elif change >= cfg.take_profit_pct:
                    exit_price = bar_price
                    exit_reason = "take_profit"
                    break
                exit_price = bar_price
            else:
                exit_reason = "time_exit"

            # Calculate P&L
            if is_long:
                pnl = (exit_price - entry_price) * shares
            else:
                pnl = (entry_price - exit_price) * shares

            capital += pnl
            equity_curve.append(capital)

            if capital > 0:
                daily_returns.append(pnl / (capital - pnl) if (capital - pnl) > 0 else 0)

            trade_record = {
                "ticker": sig.ticker,
                "direction": "long" if is_long else "short",
                "entry_price": round(entry_price, 4),
                "exit_price": round(exit_price, 4),
                "shares": round(shares, 2),
                "pnl": round(pnl, 2),
                "exit_reason": exit_reason,
                "score": sig.composite_score,
            }
            trades.append(trade_record)

        # Compute metrics
        win_count = sum(1 for t in trades if t["pnl"] > 0)
        total_return = (capital - initial_capital) / initial_capital if initial_capital > 0 else 0

        # Sharpe ratio
        sharpe = 0.0
        if len(daily_returns) >= 2:
            import statistics
            mean_r = statistics.mean(daily_returns)
            std_r = statistics.stdev(daily_returns)
            sharpe = (mean_r / std_r * (252 ** 0.5)) if std_r > 0 else 0.0

        # Max drawdown
        max_dd = 0.0
        peak = equity_curve[0] if equity_curve else initial_capital
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        return SocialBacktestResult(
            total_return=total_return,
            trade_count=len(trades),
            win_rate=win_count / len(trades) if trades else 0.0,
            sharpe=sharpe,
            max_drawdown=max_dd,
            equity_curve=equity_curve,
            trades=trades,
        )

    def _get_close_list(self, prices) -> Optional[list]:
        """Extract (date, close) from DataFrame."""
        try:
            if hasattr(prices, 'iterrows'):
                result = []
                for idx_val, row in prices.iterrows():
                    close = row.get('close', row.get('Close', None))
                    if close is not None:
                        result.append((idx_val, float(close)))
                return result if result else None
            return None
        except Exception:
            return None

    def _find_date_index(self, close_values: list, signal_date) -> Optional[int]:
        """Find index closest to signal_date."""
        for i, (d, _) in enumerate(close_values):
            d_date = d.date() if hasattr(d, 'date') else d
            if d_date >= signal_date:
                return i
        return len(close_values) - 1 if close_values else None


class SocialBacktestRunner:
    """Convenience wrapper for running social signal backtests."""

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig()
        self._strategy = SocialSignalStrategy(self.config)

    def run(
        self,
        archive,
        prices: dict,
        config: Optional[StrategyConfig] = None,
        initial_capital: float = 100_000.0,
    ) -> SocialBacktestResult:
        """Run backtest from an archive.

        Args:
            archive: SignalArchive instance.
            prices: Dict mapping ticker -> DataFrame.
            config: Optional override config.
            initial_capital: Starting capital.
        """
        if config:
            strategy = SocialSignalStrategy(config)
        else:
            strategy = self._strategy

        signals = list(archive.replay())
        return strategy.run(signals, prices, initial_capital)
