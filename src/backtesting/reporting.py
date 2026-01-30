"""Tear Sheet Generation and Strategy Comparison.

Provides comprehensive visual reporting and head-to-head
strategy comparison framework.
"""

import logging
from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd

from src.backtesting.models import (
    BacktestResult, BacktestMetrics, Trade, MonteCarloResult, WalkForwardResult,
)

logger = logging.getLogger(__name__)


class TearSheetGenerator:
    """Generate comprehensive strategy tear sheets.

    Creates detailed performance reports including:
    - Performance summary (returns, risk, risk-adjusted)
    - Monthly returns heatmap
    - Trade analysis (by sector, by factor)
    - Drawdown analysis
    - Statistical significance (if MC results provided)
    """

    def generate(
        self,
        result: BacktestResult,
        strategy_name: str = "Strategy",
        mc_result: Optional[MonteCarloResult] = None,
        wf_result: Optional[WalkForwardResult] = None,
    ) -> str:
        """Generate text tear sheet.

        Args:
            result: Backtest result.
            strategy_name: Name for display.
            mc_result: Optional Monte Carlo results.
            wf_result: Optional walk-forward results.

        Returns:
            Formatted tear sheet string.
        """
        m = result.metrics
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append(f"STRATEGY TEAR SHEET: {strategy_name}")
        lines.append("=" * 60)

        # Period info
        if not result.equity_curve.empty:
            start = result.equity_curve.index[0].strftime("%b %Y")
            end = result.equity_curve.index[-1].strftime("%b %Y")
            initial = result.equity_curve.iloc[0]
            final = result.equity_curve.iloc[-1]
            lines.append(f"Period: {start} - {end}")
            lines.append(f"Initial Capital: ${initial:,.0f} → Final: ${final:,.0f}")
        lines.append("")

        # Returns and Risk side by side
        lines.append(f"{'RETURNS':<32}{'RISK'}")
        lines.append(f"Annual Return:    {m.cagr*100:>6.1f}%          Volatility:     {m.volatility*100:>6.1f}%")
        lines.append(f"Benchmark (SPY):  {m.benchmark_cagr*100:>6.1f}%         Downside Vol:   {m.downside_volatility*100:>6.1f}%")
        lines.append(f"Alpha:            {m.alpha*100:>6.1f}%         Max Drawdown:   {m.max_drawdown*100:>6.1f}%")
        lines.append(f"Best Month:       {m.best_month*100:>+6.1f}%         Avg Drawdown:   {m.avg_drawdown*100:>6.1f}%")
        lines.append(f"Worst Month:      {m.worst_month*100:>+6.1f}%")
        lines.append(f"Win Rate:         {m.win_rate*100:>6.1f}%")
        lines.append("")

        # Risk-adjusted and Costs
        lines.append(f"{'RISK-ADJUSTED':<32}{'COSTS'}")
        lines.append(f"Sharpe Ratio:     {m.sharpe_ratio:>6.2f}          Total Commission: ${m.total_commission:,.0f}")
        lines.append(f"Sortino Ratio:    {m.sortino_ratio:>6.2f}          Total Slippage:   ${m.total_slippage:,.0f}")
        lines.append(f"Calmar Ratio:     {m.calmar_ratio:>6.2f}          Total Turnover:   {m.turnover*100:,.0f}%")
        lines.append(f"Information Ratio:{m.information_ratio:>6.2f}")
        lines.append("")

        # Statistical Significance (if available)
        if mc_result and mc_result.n_simulations > 0:
            lines.append("STATISTICAL SIGNIFICANCE")
            lines.append(f"Monte Carlo 95% CI (Sharpe): [{mc_result.sharpe_95ci[0]:.2f}, {mc_result.sharpe_95ci[1]:.2f}]")
            lines.append(f"Monte Carlo 95% CI (CAGR):   [{mc_result.cagr_95ci[0]*100:.1f}%, {mc_result.cagr_95ci[1]*100:.1f}%]")
            lines.append(f"% Profitable (MC):           {mc_result.pct_profitable*100:.1f}%")
            if wf_result:
                lines.append(f"Walk-Forward Efficiency:     {wf_result.efficiency_ratio:.2f}")
            sig_text = "YES" if mc_result.is_significant else "NO"
            lines.append(f"Strategy Significant (p<0.05): {sig_text}")
            lines.append("")

        # Monthly Returns Heatmap
        if not result.monthly_returns.empty:
            lines.append("MONTHLY RETURNS HEATMAP")
            lines.append(self._format_monthly_heatmap(result.monthly_returns))
            lines.append("")

        # Trade Analysis
        if result.trades:
            lines.append("TRADE ANALYSIS")
            lines.append("=" * 40)
            lines.append(f"Total Trades:       {m.total_trades:,}")
            lines.append(f"Profitable:         {m.winning_trades:,} ({m.win_rate*100:.1f}%)")
            lines.append(f"Avg Win:            {m.avg_win:+,.0f}")
            lines.append(f"Avg Loss:           {m.avg_loss:,.0f}")
            lines.append(f"Win/Loss Ratio:     {abs(m.avg_win/m.avg_loss):.2f}" if m.avg_loss != 0 else "Win/Loss Ratio:     N/A")
            lines.append(f"Profit Factor:      {m.profit_factor:.2f}")
            lines.append(f"Avg Hold Period:    {m.avg_hold_days:.0f} days")
            lines.append("")

            # Largest trades
            lines.append("LARGEST TRADES")
            sorted_trades = sorted(result.trades, key=lambda t: abs(t.pnl), reverse=True)[:5]
            for trade in sorted_trades:
                sign = "+" if trade.pnl > 0 else ""
                lines.append(
                    f"{sign}${trade.pnl:,.0f}  {trade.symbol} "
                    f"(held {trade.hold_days} days)"
                )

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def _format_monthly_heatmap(self, monthly_returns: pd.Series) -> str:
        """Format monthly returns as text heatmap."""
        # Convert to year x month matrix
        df = monthly_returns.to_frame("return")
        df["year"] = df.index.year
        df["month"] = df.index.month

        pivot = df.pivot_table(
            values="return", index="year", columns="month", aggfunc="first"
        )

        # Header
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        header = "     " + "  ".join(f"{m:>5}" for m in months)

        lines = [header]

        # Each year
        for year in sorted(pivot.index, reverse=True):
            row = f"{year}"
            for month in range(1, 13):
                val = pivot.loc[year, month] if month in pivot.columns else np.nan
                if pd.isna(val):
                    row += "       "
                else:
                    row += f"  {val*100:+5.1f}"
            lines.append(row)

        return "\n".join(lines[:6])  # Limit to 5 years

    def generate_dict(
        self,
        result: BacktestResult,
        mc_result: Optional[MonteCarloResult] = None,
        wf_result: Optional[WalkForwardResult] = None,
    ) -> dict:
        """Generate tear sheet data as dictionary (for JSON/API).

        Args:
            result: Backtest result.
            mc_result: Optional Monte Carlo results.
            wf_result: Optional walk-forward results.

        Returns:
            Dictionary with all tear sheet data.
        """
        m = result.metrics

        data = {
            "metrics": m.to_dict(),
            "returns": {
                "total": m.total_return,
                "cagr": m.cagr,
                "benchmark_return": m.benchmark_return,
                "benchmark_cagr": m.benchmark_cagr,
                "alpha": m.alpha,
                "best_month": m.best_month,
                "worst_month": m.worst_month,
            },
            "risk": {
                "volatility": m.volatility,
                "downside_volatility": m.downside_volatility,
                "max_drawdown": m.max_drawdown,
                "avg_drawdown": m.avg_drawdown,
            },
            "risk_adjusted": {
                "sharpe": m.sharpe_ratio,
                "sortino": m.sortino_ratio,
                "calmar": m.calmar_ratio,
                "information_ratio": m.information_ratio,
            },
            "trading": {
                "total_trades": m.total_trades,
                "winning_trades": m.winning_trades,
                "losing_trades": m.losing_trades,
                "win_rate": m.win_rate,
                "profit_factor": m.profit_factor,
                "avg_trade_pnl": m.avg_trade_pnl,
                "avg_hold_days": m.avg_hold_days,
            },
            "costs": {
                "commission": m.total_commission,
                "slippage": m.total_slippage,
                "fees": m.total_fees,
                "total": m.total_costs,
                "turnover": m.turnover,
            },
        }

        # Add equity curve data
        if not result.equity_curve.empty:
            data["equity_curve"] = {
                "dates": [d.isoformat() for d in result.equity_curve.index],
                "values": result.equity_curve.tolist(),
            }

        # Add Monte Carlo data
        if mc_result:
            data["monte_carlo"] = {
                "n_simulations": mc_result.n_simulations,
                "sharpe_ci": mc_result.sharpe_95ci,
                "cagr_ci": mc_result.cagr_95ci,
                "max_dd_ci": mc_result.max_dd_95ci,
                "pct_profitable": mc_result.pct_profitable,
                "is_significant": mc_result.is_significant,
            }

        # Add walk-forward data
        if wf_result:
            data["walk_forward"] = {
                "efficiency_ratio": wf_result.efficiency_ratio,
                "is_sharpe_avg": wf_result.in_sample_sharpe_avg,
                "oos_sharpe": wf_result.out_of_sample_sharpe,
                "n_windows": len(wf_result.windows),
            }

        return data


class StrategyComparator:
    """Compare multiple strategies head-to-head.

    Provides comprehensive comparison including:
    - Returns and risk metrics
    - Strategy correlations
    - Rolling Sharpe comparison
    - Drawdown comparison
    - Winner by metric
    """

    def compare(
        self,
        results: dict[str, BacktestResult],
        benchmark_name: str = "SPY",
    ) -> dict:
        """Compare multiple strategy results.

        Args:
            results: Dict of strategy_name -> BacktestResult.
            benchmark_name: Name of benchmark.

        Returns:
            Comparison report dictionary.
        """
        if not results:
            return {}

        return {
            "returns_table": self._build_returns_table(results),
            "risk_table": self._build_risk_table(results),
            "correlation_matrix": self._strategy_correlations(results),
            "rolling_sharpe": self._rolling_sharpe_comparison(results),
            "drawdown_comparison": self._drawdown_comparison(results),
            "winner_by_metric": self._find_winners(results),
            "ranking": self._rank_strategies(results),
        }

    def _build_returns_table(self, results: dict[str, BacktestResult]) -> pd.DataFrame:
        """Build returns comparison table."""
        data = []
        for name, result in results.items():
            m = result.metrics
            data.append({
                "Strategy": name,
                "Total Return": m.total_return,
                "CAGR": m.cagr,
                "Alpha": m.alpha,
                "Best Month": m.best_month,
                "Worst Month": m.worst_month,
                "Win Rate": m.win_rate,
            })
        return pd.DataFrame(data).set_index("Strategy")

    def _build_risk_table(self, results: dict[str, BacktestResult]) -> pd.DataFrame:
        """Build risk comparison table."""
        data = []
        for name, result in results.items():
            m = result.metrics
            data.append({
                "Strategy": name,
                "Volatility": m.volatility,
                "Downside Vol": m.downside_volatility,
                "Max Drawdown": m.max_drawdown,
                "Sharpe": m.sharpe_ratio,
                "Sortino": m.sortino_ratio,
                "Calmar": m.calmar_ratio,
            })
        return pd.DataFrame(data).set_index("Strategy")

    def _strategy_correlations(self, results: dict[str, BacktestResult]) -> pd.DataFrame:
        """Calculate correlation matrix of strategy returns."""
        returns_dict = {}
        for name, result in results.items():
            if not result.daily_returns.empty:
                returns_dict[name] = result.daily_returns

        if not returns_dict:
            return pd.DataFrame()

        returns_df = pd.DataFrame(returns_dict)
        return returns_df.corr()

    def _rolling_sharpe_comparison(
        self,
        results: dict[str, BacktestResult],
        window: int = 63,  # ~3 months
    ) -> pd.DataFrame:
        """Calculate rolling Sharpe ratios for comparison."""
        rolling_sharpes = {}

        for name, result in results.items():
            returns = result.daily_returns
            if len(returns) < window:
                continue

            rf_daily = 0.05 / 252
            excess = returns - rf_daily

            rolling_mean = excess.rolling(window).mean() * 252
            rolling_std = returns.rolling(window).std() * np.sqrt(252)
            rolling_sharpes[name] = rolling_mean / rolling_std

        return pd.DataFrame(rolling_sharpes)

    def _drawdown_comparison(self, results: dict[str, BacktestResult]) -> pd.DataFrame:
        """Compare drawdown curves."""
        drawdowns = {}
        for name, result in results.items():
            if not result.drawdown_curve.empty:
                drawdowns[name] = result.drawdown_curve

        return pd.DataFrame(drawdowns) if drawdowns else pd.DataFrame()

    def _find_winners(self, results: dict[str, BacktestResult]) -> dict[str, str]:
        """Find winner for each metric."""
        if not results:
            return {}

        return {
            "sharpe": max(results.keys(), key=lambda s: results[s].metrics.sharpe_ratio),
            "cagr": max(results.keys(), key=lambda s: results[s].metrics.cagr),
            "sortino": max(results.keys(), key=lambda s: results[s].metrics.sortino_ratio),
            "max_drawdown": min(results.keys(), key=lambda s: abs(results[s].metrics.max_drawdown)),
            "win_rate": max(results.keys(), key=lambda s: results[s].metrics.win_rate),
            "profit_factor": max(results.keys(), key=lambda s: results[s].metrics.profit_factor),
        }

    def _rank_strategies(self, results: dict[str, BacktestResult]) -> list[dict]:
        """Rank strategies by composite score."""
        scores = []

        for name, result in results.items():
            m = result.metrics
            # Composite score: weighted average of key metrics
            score = (
                m.sharpe_ratio * 0.3 +
                m.sortino_ratio * 0.2 +
                m.cagr * 10 * 0.2 +  # Scale CAGR
                (1 + m.max_drawdown) * 0.15 +  # Lower drawdown is better
                m.win_rate * 0.15
            )
            scores.append({
                "strategy": name,
                "composite_score": score,
                "sharpe": m.sharpe_ratio,
                "cagr": m.cagr,
                "max_dd": m.max_drawdown,
            })

        return sorted(scores, key=lambda x: x["composite_score"], reverse=True)

    def format_comparison(
        self,
        comparison: dict,
        top_n: int = 5,
    ) -> str:
        """Format comparison as text report.

        Args:
            comparison: Comparison dictionary from compare().
            top_n: Number of top strategies to show.

        Returns:
            Formatted comparison string.
        """
        lines = []
        lines.append("=" * 70)
        lines.append("STRATEGY COMPARISON REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Returns comparison
        if "returns_table" in comparison:
            lines.append("RETURNS COMPARISON")
            lines.append("-" * 50)
            df = comparison["returns_table"]
            for col in ["Total Return", "CAGR", "Alpha", "Win Rate"]:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: f"{x*100:.1f}%")
            lines.append(df.to_string())
            lines.append("")

        # Risk comparison
        if "risk_table" in comparison:
            lines.append("RISK COMPARISON")
            lines.append("-" * 50)
            df = comparison["risk_table"]
            for col in ["Volatility", "Downside Vol", "Max Drawdown"]:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: f"{x*100:.1f}%")
            for col in ["Sharpe", "Sortino", "Calmar"]:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: f"{x:.2f}")
            lines.append(df.to_string())
            lines.append("")

        # Winners
        if "winner_by_metric" in comparison:
            lines.append("BEST BY METRIC")
            lines.append("-" * 50)
            for metric, winner in comparison["winner_by_metric"].items():
                lines.append(f"  {metric.upper():15s} → {winner}")
            lines.append("")

        # Rankings
        if "ranking" in comparison:
            lines.append("OVERALL RANKING (Composite Score)")
            lines.append("-" * 50)
            for i, entry in enumerate(comparison["ranking"][:top_n], 1):
                lines.append(
                    f"  {i}. {entry['strategy']:20s} "
                    f"Score: {entry['composite_score']:.2f}  "
                    f"Sharpe: {entry['sharpe']:.2f}  "
                    f"CAGR: {entry['cagr']*100:.1f}%"
                )

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)
