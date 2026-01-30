"""Walk-Forward Optimization and Monte Carlo Analysis.

Provides robust out-of-sample testing and statistical significance analysis
to prevent overfitting and validate strategy performance.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Type, Iterator
from itertools import product
import numpy as np
import pandas as pd

from src.backtesting.config import (
    BacktestConfig, WalkForwardConfig, MonteCarloConfig,
    DEFAULT_WALK_FORWARD, DEFAULT_MONTE_CARLO,
)
from src.backtesting.models import (
    BacktestResult, BacktestMetrics, Trade,
    WalkForwardWindow, WalkForwardResult, MonteCarloResult,
)
from src.backtesting.engine import BacktestEngine, Strategy

logger = logging.getLogger(__name__)


class WalkForwardOptimizer:
    """Walk-forward optimization framework.

    Prevents overfitting by:
    1. Splitting data into in-sample (training) and out-of-sample (test) periods
    2. Optimizing parameters on in-sample data
    3. Testing only on out-of-sample data
    4. Rolling forward through multiple windows
    5. Combining out-of-sample results for final performance

    The efficiency ratio (OOS Sharpe / IS Sharpe) measures how well
    in-sample performance translates to out-of-sample:
    - >0.5: Good - strategy is robust
    - 0.3-0.5: Acceptable - some overfitting
    - <0.3: Poor - likely overfit, do not deploy
    """

    def __init__(
        self,
        config: Optional[WalkForwardConfig] = None,
        backtest_config: Optional[BacktestConfig] = None,
    ):
        self.config = config or DEFAULT_WALK_FORWARD
        self.backtest_config = backtest_config or BacktestConfig()

    def run(
        self,
        strategy_class: Type[Strategy],
        param_grid: dict[str, list],
        price_data: pd.DataFrame,
        benchmark: Optional[pd.Series] = None,
    ) -> WalkForwardResult:
        """Run walk-forward optimization.

        Args:
            strategy_class: Strategy class to optimize.
            param_grid: Parameter grid (e.g., {"param1": [1,2,3], "param2": [0.1, 0.2]})
            price_data: Historical price data.
            benchmark: Optional benchmark prices.

        Returns:
            WalkForwardResult with combined out-of-sample performance.
        """
        logger.info(f"Starting walk-forward optimization with {self.config.n_windows} windows")

        # Generate windows
        windows = self._generate_windows(price_data.index)

        # Run optimization for each window
        oos_results = []
        param_history = []

        for window in windows:
            logger.info(f"Window {window.window_id}: IS {window.in_sample_start} to {window.in_sample_end}")

            # Get data for this window
            is_data = price_data.loc[window.in_sample_start:window.in_sample_end]
            oos_data = price_data.loc[window.out_of_sample_start:window.out_of_sample_end]

            # Optimize on in-sample
            best_params, is_sharpe = self._optimize_insample(
                strategy_class, param_grid, is_data, benchmark
            )
            window.best_params = best_params
            window.in_sample_sharpe = is_sharpe
            param_history.append(best_params)

            # Test on out-of-sample
            oos_result = self._backtest(
                strategy_class, best_params, oos_data, benchmark
            )
            window.out_of_sample_sharpe = oos_result.metrics.sharpe_ratio
            window.out_of_sample_result = oos_result

            oos_results.append(oos_result)
            logger.info(
                f"Window {window.window_id}: IS Sharpe={is_sharpe:.2f}, "
                f"OOS Sharpe={oos_result.metrics.sharpe_ratio:.2f}"
            )

        # Combine out-of-sample results
        combined = self._combine_results(oos_results)

        # Calculate metrics
        is_sharpe_avg = np.mean([w.in_sample_sharpe for w in windows])
        oos_sharpe = combined.sharpe_ratio
        efficiency = oos_sharpe / is_sharpe_avg if is_sharpe_avg > 0 else 0

        # Assess parameter stability
        param_stability = self._assess_param_stability(param_history)

        return WalkForwardResult(
            windows=windows,
            combined_equity_curve=self._combine_equity_curves(oos_results),
            in_sample_sharpe_avg=is_sharpe_avg,
            out_of_sample_sharpe=oos_sharpe,
            efficiency_ratio=efficiency,
            param_stability=param_stability,
            combined_metrics=combined,
        )

    def _generate_windows(self, dates: pd.DatetimeIndex) -> list[WalkForwardWindow]:
        """Generate walk-forward windows."""
        n_dates = len(dates)
        window_size = n_dates // self.config.n_windows

        windows = []
        for i in range(self.config.n_windows):
            # This window's total range
            start_idx = i * window_size
            end_idx = (i + 1) * window_size if i < self.config.n_windows - 1 else n_dates

            # Split into in-sample and out-of-sample
            total_days = end_idx - start_idx
            is_days = int(total_days * self.config.in_sample_pct)

            is_start = dates[start_idx]
            is_end = dates[start_idx + is_days - 1]
            oos_start = dates[start_idx + is_days]
            oos_end = dates[end_idx - 1]

            windows.append(WalkForwardWindow(
                window_id=i + 1,
                in_sample_start=is_start,
                in_sample_end=is_end,
                out_of_sample_start=oos_start,
                out_of_sample_end=oos_end,
            ))

        return windows

    def _optimize_insample(
        self,
        strategy_class: Type[Strategy],
        param_grid: dict[str, list],
        data: pd.DataFrame,
        benchmark: Optional[pd.Series],
    ) -> tuple[dict, float]:
        """Optimize parameters on in-sample data."""
        best_metric = float('-inf')
        best_params = {}

        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        for values in product(*param_values):
            params = dict(zip(param_names, values))

            # Run backtest with these parameters
            result = self._backtest(strategy_class, params, data, benchmark)

            # Get optimization metric
            if self.config.optimization_metric == "sharpe":
                metric = result.metrics.sharpe_ratio
            elif self.config.optimization_metric == "cagr":
                metric = result.metrics.cagr
            elif self.config.optimization_metric == "sortino":
                metric = result.metrics.sortino_ratio
            else:
                metric = result.metrics.sharpe_ratio

            # Check minimum trades
            if result.metrics.total_trades < self.config.min_trades_per_window:
                continue

            if metric > best_metric:
                best_metric = metric
                best_params = params

        return best_params, best_metric

    def _backtest(
        self,
        strategy_class: Type[Strategy],
        params: dict,
        data: pd.DataFrame,
        benchmark: Optional[pd.Series],
    ) -> BacktestResult:
        """Run a single backtest."""
        # Create config for this period
        config = BacktestConfig(
            start_date=data.index[0].date(),
            end_date=data.index[-1].date(),
            initial_capital=self.backtest_config.initial_capital,
            cost_model=self.backtest_config.cost_model,
            execution=self.backtest_config.execution,
            rebalance_frequency=self.backtest_config.rebalance_frequency,
        )

        engine = BacktestEngine(config)
        engine.load_data(data, benchmark)

        # Create strategy with parameters
        strategy = strategy_class(**params)

        return engine.run(strategy)

    def _combine_results(self, results: list[BacktestResult]) -> BacktestMetrics:
        """Combine out-of-sample results into aggregate metrics."""
        if not results:
            return BacktestMetrics()

        # Concatenate daily returns
        all_returns = pd.concat([r.daily_returns for r in results])
        all_returns = all_returns[~all_returns.index.duplicated(keep='first')]
        all_returns = all_returns.sort_index()

        # Calculate combined metrics
        metrics = BacktestMetrics()

        if len(all_returns) < 2:
            return metrics

        # Total return
        metrics.total_return = (1 + all_returns).prod() - 1

        # CAGR
        n_days = (all_returns.index[-1] - all_returns.index[0]).days
        n_years = n_days / 365.25
        if n_years > 0:
            metrics.cagr = (1 + metrics.total_return) ** (1 / n_years) - 1

        # Volatility and Sharpe
        metrics.volatility = all_returns.std() * np.sqrt(252)
        rf_daily = 0.05 / 252
        excess_returns = all_returns - rf_daily

        if metrics.volatility > 0:
            metrics.sharpe_ratio = (excess_returns.mean() * 252) / metrics.volatility

        # Drawdown
        cumulative = (1 + all_returns).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak
        metrics.max_drawdown = drawdown.min()

        # Trade stats
        all_trades = []
        for r in results:
            all_trades.extend(r.trades)

        metrics.total_trades = len(all_trades)
        if all_trades:
            pnls = [t.pnl for t in all_trades]
            winners = [p for p in pnls if p > 0]
            metrics.win_rate = len(winners) / len(all_trades)
            metrics.avg_trade_pnl = np.mean(pnls)

        return metrics

    def _combine_equity_curves(self, results: list[BacktestResult]) -> pd.Series:
        """Combine equity curves from multiple windows."""
        if not results:
            return pd.Series(dtype=float)

        # Chain equity curves
        combined = pd.Series(dtype=float)
        last_equity = self.backtest_config.initial_capital

        for result in results:
            if result.equity_curve.empty:
                continue

            # Scale to continue from last equity
            scale = last_equity / result.equity_curve.iloc[0]
            scaled = result.equity_curve * scale

            combined = pd.concat([combined, scaled])
            last_equity = scaled.iloc[-1]

        return combined[~combined.index.duplicated(keep='first')].sort_index()

    def _assess_param_stability(self, param_history: list[dict]) -> dict:
        """Assess parameter stability across windows."""
        if not param_history:
            return {}

        stability = {}
        param_names = param_history[0].keys()

        for param in param_names:
            values = [p.get(param) for p in param_history if p.get(param) is not None]
            if values:
                try:
                    # Numeric parameters
                    values = [float(v) for v in values]
                    stability[param] = {
                        "mean": np.mean(values),
                        "std": np.std(values),
                        "cv": np.std(values) / np.mean(values) if np.mean(values) != 0 else 0,
                        "values": values,
                    }
                except (ValueError, TypeError):
                    # Non-numeric parameters
                    stability[param] = {
                        "mode": max(set(values), key=values.count),
                        "values": values,
                    }

        return stability


class MonteCarloAnalyzer:
    """Monte Carlo analysis for statistical significance.

    Uses bootstrap resampling to estimate confidence intervals
    and random strategy comparison for significance testing.
    """

    def __init__(self, config: Optional[MonteCarloConfig] = None):
        self.config = config or DEFAULT_MONTE_CARLO
        self.rng = np.random.default_rng(42)

    def bootstrap_analysis(
        self,
        trades: list[Trade],
        initial_capital: float = 100_000,
    ) -> MonteCarloResult:
        """Bootstrap trade sequences to assess statistical significance.

        Resamples trade sequence with replacement to estimate
        distribution of performance metrics.

        Args:
            trades: List of completed trades.
            initial_capital: Starting capital for equity calculation.

        Returns:
            MonteCarloResult with confidence intervals.
        """
        if not trades:
            return MonteCarloResult()

        logger.info(f"Running {self.config.n_simulations} Monte Carlo simulations")

        sharpe_dist = []
        cagr_dist = []
        max_dd_dist = []

        for _ in range(self.config.n_simulations):
            # Resample trades with replacement
            sample_idx = self.rng.choice(len(trades), size=len(trades), replace=True)
            sample_trades = [trades[i] for i in sample_idx]

            # Build equity curve from resampled trades
            equity = self._build_equity_curve(sample_trades, initial_capital)

            if len(equity) < 2:
                continue

            # Calculate metrics
            sharpe = self._calc_sharpe(equity)
            cagr = self._calc_cagr(equity)
            max_dd = self._calc_max_drawdown(equity)

            sharpe_dist.append(sharpe)
            cagr_dist.append(cagr)
            max_dd_dist.append(max_dd)

        sharpe_arr = np.array(sharpe_dist)
        cagr_arr = np.array(cagr_dist)
        dd_arr = np.array(max_dd_dist)

        ci_low = (1 - self.config.confidence_level) / 2 * 100
        ci_high = (1 + self.config.confidence_level) / 2 * 100

        return MonteCarloResult(
            n_simulations=len(sharpe_dist),
            sharpe_mean=float(np.mean(sharpe_arr)),
            sharpe_std=float(np.std(sharpe_arr)),
            sharpe_95ci=(
                float(np.percentile(sharpe_arr, ci_low)),
                float(np.percentile(sharpe_arr, ci_high)),
            ),
            cagr_mean=float(np.mean(cagr_arr)),
            cagr_std=float(np.std(cagr_arr)),
            cagr_95ci=(
                float(np.percentile(cagr_arr, ci_low)),
                float(np.percentile(cagr_arr, ci_high)),
            ),
            max_dd_mean=float(np.mean(dd_arr)),
            max_dd_std=float(np.std(dd_arr)),
            max_dd_95ci=(
                float(np.percentile(dd_arr, ci_low)),
                float(np.percentile(dd_arr, ci_high)),
            ),
            pct_profitable=float(np.mean(cagr_arr > 0)),
            pct_beats_benchmark=float(np.mean(sharpe_arr > 0)),
            sharpe_distribution=sharpe_arr,
            cagr_distribution=cagr_arr,
            dd_distribution=dd_arr,
        )

    def test_significance(
        self,
        strategy_sharpe: float,
        price_data: pd.DataFrame,
        n_random: Optional[int] = None,
    ) -> tuple[bool, float]:
        """Test if strategy Sharpe is significantly better than random.

        Compares strategy against N random portfolios to assess
        whether performance could be due to luck.

        Args:
            strategy_sharpe: Strategy's Sharpe ratio.
            price_data: Price data for random portfolio construction.
            n_random: Number of random strategies to test against.

        Returns:
            Tuple of (is_significant, p_value).
        """
        n_random = n_random or self.config.random_strategy_tests

        logger.info(f"Testing significance against {n_random} random portfolios")

        random_sharpes = []
        n_stocks = min(30, len(price_data.columns))

        for _ in range(n_random):
            # Random portfolio weights
            weights = self.rng.dirichlet(np.ones(n_stocks))

            # Select random stocks
            symbols = self.rng.choice(
                price_data.columns, size=n_stocks, replace=False
            )

            # Calculate portfolio returns
            stock_returns = price_data[symbols].pct_change().dropna()
            port_returns = (stock_returns * weights).sum(axis=1)

            # Calculate Sharpe
            sharpe = self._calc_sharpe_from_returns(port_returns)
            random_sharpes.append(sharpe)

        random_sharpes = np.array(random_sharpes)

        # P-value: proportion of random strategies that beat the strategy
        p_value = (random_sharpes >= strategy_sharpe).mean()

        # Significant if strategy beats 95th percentile
        threshold = np.percentile(random_sharpes, 95)
        is_significant = strategy_sharpe > threshold

        logger.info(
            f"Strategy Sharpe: {strategy_sharpe:.2f}, "
            f"95th percentile: {threshold:.2f}, "
            f"p-value: {p_value:.3f}"
        )

        return is_significant, float(p_value)

    def _build_equity_curve(
        self,
        trades: list[Trade],
        initial_capital: float,
    ) -> pd.Series:
        """Build equity curve from trade sequence."""
        equity = [initial_capital]
        current = initial_capital

        for trade in trades:
            current += trade.pnl
            equity.append(current)

        return pd.Series(equity)

    def _calc_sharpe(self, equity: pd.Series) -> float:
        """Calculate annualized Sharpe ratio from equity curve."""
        returns = equity.pct_change().dropna()
        return self._calc_sharpe_from_returns(returns)

    def _calc_sharpe_from_returns(self, returns: pd.Series) -> float:
        """Calculate annualized Sharpe ratio from returns."""
        if len(returns) < 2 or returns.std() == 0:
            return 0.0

        rf_daily = 0.05 / 252
        excess = returns - rf_daily
        return float(excess.mean() / returns.std() * np.sqrt(252))

    def _calc_cagr(self, equity: pd.Series) -> float:
        """Calculate CAGR from equity curve."""
        if len(equity) < 2:
            return 0.0

        total_return = equity.iloc[-1] / equity.iloc[0] - 1
        # Assume ~252 trading days per year, one trade per day
        n_years = len(equity) / 252

        if n_years <= 0:
            return total_return

        return float((1 + total_return) ** (1 / n_years) - 1)

    def _calc_max_drawdown(self, equity: pd.Series) -> float:
        """Calculate max drawdown from equity curve."""
        peak = equity.cummax()
        drawdown = (equity - peak) / peak
        return float(drawdown.min())
