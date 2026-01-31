"""Performance metrics computation.

Comprehensive risk and return metrics, drawdown analysis, and rolling calculations.
"""

import logging
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from src.attribution.config import (
    TRADING_DAYS_PER_YEAR,
    RISK_FREE_RATE,
    AttributionConfig,
    DEFAULT_ATTRIBUTION_CONFIG,
)
from src.attribution.models import (
    PerformanceMetrics,
    DrawdownPeriod,
    MonthlyReturns,
)

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Computes comprehensive performance and risk metrics."""

    def __init__(self, config: Optional[AttributionConfig] = None) -> None:
        self.config = config or DEFAULT_ATTRIBUTION_CONFIG

    def compute(self, returns: pd.Series) -> PerformanceMetrics:
        """Compute all performance metrics from daily returns.

        Args:
            returns: Daily return series.

        Returns:
            PerformanceMetrics.
        """
        if len(returns) < 2:
            return PerformanceMetrics()

        tdy = self.config.trading_days_per_year
        rf = self.config.risk_free_rate
        n = len(returns)

        # Returns
        total_return = float((1 + returns).prod() - 1)
        ann_return = float((1 + total_return) ** (tdy / n) - 1) if n > 0 else 0.0

        # Volatility
        vol = float(returns.std() * np.sqrt(tdy))

        # Sharpe
        rf_daily = (1 + rf) ** (1 / tdy) - 1
        excess = returns - rf_daily
        sharpe = float(excess.mean() / returns.std() * np.sqrt(tdy)) if returns.std() > 0 else 0.0

        # Sortino (downside deviation)
        downside = returns[returns < 0]
        downside_std = float(downside.std() * np.sqrt(tdy)) if len(downside) > 1 else 0.0
        sortino = float(excess.mean() * np.sqrt(tdy) / downside_std) if downside_std > 0 else 0.0

        # Max drawdown
        cumulative = (1 + returns).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak
        max_dd = float(drawdown.min())

        # Calmar
        calmar = ann_return / abs(max_dd) if abs(max_dd) > 1e-10 else 0.0

        # Win rate
        positive = int((returns > 0).sum())
        negative = int((returns < 0).sum())
        win_rate = positive / n if n > 0 else 0.0

        # Distribution stats
        skew = float(returns.skew()) if n > 2 else 0.0
        kurt = float(returns.kurtosis()) if n > 3 else 0.0

        # VaR and CVaR (95%)
        sorted_returns = np.sort(returns.values)
        var_idx = int(0.05 * n)
        var_95 = float(sorted_returns[var_idx]) if var_idx < n else 0.0
        cvar_95 = float(sorted_returns[:max(var_idx, 1)].mean())

        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=ann_return,
            volatility=vol,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd,
            win_rate=win_rate,
            best_day=float(returns.max()),
            worst_day=float(returns.min()),
            avg_daily_return=float(returns.mean()),
            skewness=skew,
            kurtosis=kurt,
            var_95=var_95,
            cvar_95=cvar_95,
            positive_days=positive,
            negative_days=negative,
            total_days=n,
        )

    def compute_drawdowns(
        self,
        returns: pd.Series,
        top_n: int = 5,
    ) -> list[DrawdownPeriod]:
        """Identify top drawdown periods.

        Args:
            returns: Daily return series.
            top_n: Number of top drawdowns to return.

        Returns:
            List of DrawdownPeriod, sorted by depth.
        """
        if len(returns) < 2:
            return []

        cumulative = (1 + returns).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak

        # Find drawdown periods
        periods: list[DrawdownPeriod] = []
        in_drawdown = False
        start_idx = None
        trough_idx = None
        trough_val = 0.0

        for i in range(len(drawdown)):
            dd_val = drawdown.iloc[i]

            if dd_val < 0 and not in_drawdown:
                in_drawdown = True
                start_idx = i
                trough_idx = i
                trough_val = dd_val

            elif dd_val < trough_val and in_drawdown:
                trough_idx = i
                trough_val = dd_val

            elif dd_val >= 0 and in_drawdown:
                in_drawdown = False
                start_date = returns.index[start_idx]
                trough_date = returns.index[trough_idx]
                end_date = returns.index[i]

                if hasattr(start_date, 'date'):
                    start_date = start_date.date()
                if hasattr(trough_date, 'date'):
                    trough_date = trough_date.date()
                if hasattr(end_date, 'date'):
                    end_date = end_date.date()

                periods.append(DrawdownPeriod(
                    start_date=start_date,
                    trough_date=trough_date,
                    end_date=end_date,
                    depth=trough_val,
                    duration_days=i - start_idx,
                    recovery_days=i - trough_idx,
                ))

        # Handle ongoing drawdown
        if in_drawdown and start_idx is not None:
            start_date = returns.index[start_idx]
            trough_date = returns.index[trough_idx]
            if hasattr(start_date, 'date'):
                start_date = start_date.date()
            if hasattr(trough_date, 'date'):
                trough_date = trough_date.date()

            periods.append(DrawdownPeriod(
                start_date=start_date,
                trough_date=trough_date,
                end_date=None,
                depth=trough_val,
                duration_days=len(returns) - 1 - start_idx,
                recovery_days=0,
            ))

        # Sort by depth (most negative first)
        periods.sort(key=lambda p: p.depth)
        return periods[:top_n]

    def compute_monthly_returns(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
    ) -> list[MonthlyReturns]:
        """Compute monthly return summary.

        Args:
            portfolio_returns: Daily portfolio returns.
            benchmark_returns: Daily benchmark returns (optional).

        Returns:
            List of MonthlyReturns.
        """
        # Group by year-month
        port_monthly = (1 + portfolio_returns).groupby(
            [portfolio_returns.index.year, portfolio_returns.index.month]
        ).prod() - 1

        bm_monthly = None
        if benchmark_returns is not None:
            bm_monthly = (1 + benchmark_returns).groupby(
                [benchmark_returns.index.year, benchmark_returns.index.month]
            ).prod() - 1

        results: list[MonthlyReturns] = []
        for (year, month), port_ret in port_monthly.items():
            bm_ret = 0.0
            if bm_monthly is not None and (year, month) in bm_monthly.index:
                bm_ret = float(bm_monthly.loc[(year, month)])

            results.append(MonthlyReturns(
                year=int(year),
                month=int(month),
                portfolio_return=float(port_ret),
                benchmark_return=bm_ret,
                active_return=float(port_ret) - bm_ret,
            ))

        return results

    def compute_rolling(
        self,
        returns: pd.Series,
        window: Optional[int] = None,
    ) -> tuple[list[tuple[date, float]], list[tuple[date, float]]]:
        """Compute rolling Sharpe and volatility.

        Args:
            returns: Daily returns.
            window: Rolling window in days.

        Returns:
            Tuple of (rolling_sharpe, rolling_volatility) data points.
        """
        window = window or self.config.rolling_window_days
        tdy = self.config.trading_days_per_year
        rf_daily = (1 + self.config.risk_free_rate) ** (1 / tdy) - 1

        if len(returns) < window:
            return [], []

        rolling_vol = returns.rolling(window).std() * np.sqrt(tdy)
        rolling_mean = (returns - rf_daily).rolling(window).mean()
        rolling_std = returns.rolling(window).std()
        rolling_sharpe = rolling_mean / rolling_std * np.sqrt(tdy)

        sharpe_data = []
        vol_data = []

        for i in range(window - 1, len(returns)):
            idx = returns.index[i]
            d = idx.date() if hasattr(idx, 'date') else idx

            s_val = rolling_sharpe.iloc[i]
            v_val = rolling_vol.iloc[i]

            if not np.isnan(s_val):
                sharpe_data.append((d, float(s_val)))
            if not np.isnan(v_val):
                vol_data.append((d, float(v_val)))

        return sharpe_data, vol_data
