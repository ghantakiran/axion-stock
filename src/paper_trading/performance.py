"""Performance Tracker.

Real-time performance computation for paper trading sessions
including returns, risk metrics, trade statistics, and benchmark comparison.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.paper_trading.models import (
    PaperSession,
    SessionMetrics,
    SessionSnapshot,
    SessionTrade,
    SessionComparison,
)

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.045


class PerformanceTracker:
    """Computes performance metrics for paper trading sessions."""

    def compute(self, session: PaperSession) -> SessionMetrics:
        """Compute comprehensive metrics from session state.

        Args:
            session: Paper trading session.

        Returns:
            SessionMetrics with all computed values.
        """
        metrics = SessionMetrics()
        metrics.start_equity = session.initial_capital
        metrics.end_equity = session.equity

        # Returns
        metrics.total_return = session.total_return

        # Annualize if we have snapshots
        if len(session.snapshots) > 1:
            n_days = (session.snapshots[-1].timestamp - session.snapshots[0].timestamp).days
            metrics.total_days = max(n_days, 1)
            n_years = n_days / 365.25
            if n_years > 0:
                metrics.annualized_return = (1 + metrics.total_return) ** (1 / n_years) - 1

        # Risk from snapshot returns
        returns = self._get_returns_from_snapshots(session.snapshots)
        if len(returns) > 1:
            metrics.volatility = float(returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))

            # Sharpe
            rf_daily = RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
            excess = returns - rf_daily
            if metrics.volatility > 0:
                metrics.sharpe_ratio = float(
                    (excess.mean() * TRADING_DAYS_PER_YEAR) / metrics.volatility
                )

            # Sortino
            downside = returns[returns < 0]
            if len(downside) > 0:
                downside_vol = float(downside.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
                if downside_vol > 0:
                    metrics.sortino_ratio = float(
                        (excess.mean() * TRADING_DAYS_PER_YEAR) / downside_vol
                    )

        # Drawdown
        metrics.max_drawdown = min(
            (s.drawdown for s in session.snapshots), default=0.0
        )
        if abs(metrics.max_drawdown) > 0.001 and metrics.annualized_return != 0:
            metrics.calmar_ratio = metrics.annualized_return / abs(metrics.max_drawdown)

        # Drawdown duration
        if session.snapshots:
            metrics.max_drawdown_duration_days = self._max_drawdown_duration(
                session.snapshots
            )

        # Trade statistics
        closing_trades = [t for t in session.trades if t.pnl is not None]
        metrics.total_trades = len(closing_trades)

        if closing_trades:
            pnls = [t.pnl for t in closing_trades]
            winners = [p for p in pnls if p > 0]
            losers = [p for p in pnls if p <= 0]

            metrics.winning_trades = len(winners)
            metrics.losing_trades = len(losers)
            metrics.win_rate = len(winners) / len(closing_trades)
            metrics.avg_win = float(np.mean(winners)) if winners else 0.0
            metrics.avg_loss = float(np.mean(losers)) if losers else 0.0
            metrics.avg_trade_pnl = float(np.mean(pnls))

            gross_profit = sum(winners)
            gross_loss = abs(sum(losers))
            metrics.profit_factor = (
                gross_profit / gross_loss if gross_loss > 0 else float("inf")
            )

        # Costs
        metrics.total_commission = sum(t.commission for t in session.trades)
        metrics.total_slippage = sum(t.slippage for t in session.trades)
        metrics.total_costs = metrics.total_commission + metrics.total_slippage

        # Turnover
        if session.snapshots:
            total_volume = sum(t.notional for t in session.trades)
            avg_equity = np.mean([s.equity for s in session.snapshots])
            metrics.turnover = total_volume / avg_equity if avg_equity > 0 else 0.0

        return metrics

    def compute_with_benchmark(
        self,
        session: PaperSession,
        benchmark_returns: pd.Series,
    ) -> SessionMetrics:
        """Compute metrics including benchmark comparison.

        Args:
            session: Paper trading session.
            benchmark_returns: Daily benchmark returns.

        Returns:
            SessionMetrics with benchmark fields populated.
        """
        metrics = self.compute(session)

        if len(benchmark_returns) > 0:
            metrics.benchmark_return = float((1 + benchmark_returns).prod() - 1)
            metrics.active_return = metrics.total_return - metrics.benchmark_return

        return metrics

    def compare_sessions(
        self,
        sessions: dict[str, PaperSession],
    ) -> SessionComparison:
        """Compare multiple sessions.

        Args:
            sessions: Dict of name -> PaperSession.

        Returns:
            SessionComparison with metrics table and rankings.
        """
        comparison = SessionComparison()
        comparison.sessions = list(sessions.keys())

        # Compute metrics for each
        all_metrics = {}
        for name, session in sessions.items():
            m = self.compute(session)
            all_metrics[name] = m
            comparison.metrics_table.append({
                "session": name,
                "total_return": m.total_return,
                "sharpe_ratio": m.sharpe_ratio,
                "max_drawdown": m.max_drawdown,
                "win_rate": m.win_rate,
                "profit_factor": m.profit_factor,
                "total_trades": m.total_trades,
            })

        # Winners by metric
        if all_metrics:
            comparison.winner_by_metric = {
                "total_return": max(all_metrics, key=lambda n: all_metrics[n].total_return),
                "sharpe_ratio": max(all_metrics, key=lambda n: all_metrics[n].sharpe_ratio),
                "max_drawdown": min(all_metrics, key=lambda n: abs(all_metrics[n].max_drawdown)),
                "win_rate": max(all_metrics, key=lambda n: all_metrics[n].win_rate),
            }

            # Ranking by composite score
            for name, m in all_metrics.items():
                score = (
                    m.sharpe_ratio * 0.3
                    + m.total_return * 10 * 0.25
                    + (1 + m.max_drawdown) * 0.2
                    + m.win_rate * 0.15
                    + min(m.profit_factor, 5) / 5 * 0.1
                )
                comparison.ranking.append({
                    "session": name,
                    "score": score,
                    "sharpe": m.sharpe_ratio,
                    "return": m.total_return,
                    "max_dd": m.max_drawdown,
                })

            comparison.ranking.sort(key=lambda x: x["score"], reverse=True)

        return comparison

    def _get_returns_from_snapshots(
        self, snapshots: list[SessionSnapshot]
    ) -> pd.Series:
        """Extract daily returns from snapshots."""
        if len(snapshots) < 2:
            return pd.Series(dtype=float)

        equities = pd.Series(
            [s.equity for s in snapshots],
            index=[s.timestamp for s in snapshots],
        )
        return equities.pct_change().dropna()

    def _max_drawdown_duration(self, snapshots: list[SessionSnapshot]) -> int:
        """Compute maximum drawdown duration in days."""
        max_duration = 0
        current_duration = 0

        for snap in snapshots:
            if snap.drawdown < 0:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0

        return max_duration
