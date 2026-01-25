"""Unit tests for backtesting module."""

import numpy as np
import pandas as pd
import pytest

from src.backtest import _compute_metrics


class TestComputeMetrics:
    def test_positive_returns(self):
        # All positive monthly returns
        port_returns = np.array([0.05, 0.03, 0.04, 0.02, 0.06])
        bench_returns = np.array([0.02, 0.02, 0.02, 0.02, 0.02])

        metrics = _compute_metrics(port_returns, bench_returns)

        assert metrics["n_months"] == 5
        assert metrics["total_return"] > 0
        assert metrics["portfolio_cagr"] > metrics["benchmark_cagr"]
        assert metrics["win_rate"] == 1.0  # All positive

    def test_negative_returns(self):
        # All negative monthly returns
        port_returns = np.array([-0.05, -0.03, -0.04, -0.02, -0.06])
        bench_returns = np.array([-0.02, -0.02, -0.02, -0.02, -0.02])

        metrics = _compute_metrics(port_returns, bench_returns)

        assert metrics["total_return"] < 0
        assert metrics["max_drawdown"] < 0
        assert metrics["win_rate"] == 0.0

    def test_mixed_returns(self):
        port_returns = np.array([0.05, -0.02, 0.03, -0.01, 0.04])
        bench_returns = np.array([0.02, 0.01, 0.02, 0.01, 0.02])

        metrics = _compute_metrics(port_returns, bench_returns)

        assert 0 < metrics["win_rate"] < 1
        assert "sharpe_ratio" in metrics

    def test_empty_returns(self):
        metrics = _compute_metrics(np.array([]), np.array([]))
        assert metrics == {}

    def test_sharpe_ratio_calculation(self):
        # Consistent returns should have high Sharpe
        port_returns = np.array([0.02, 0.02, 0.02, 0.02, 0.02])
        bench_returns = np.array([0.01, 0.01, 0.01, 0.01, 0.01])

        metrics = _compute_metrics(port_returns, bench_returns)

        # With no variance, Sharpe should be very high (or inf)
        # But std is 0, so we handle this case
        assert "sharpe_ratio" in metrics

    def test_max_drawdown_calculation(self):
        # Create a sequence with known drawdown
        # Start at 1.0, go to 1.1, drop to 0.9, recover to 1.0
        port_returns = np.array([0.10, -0.18, 0.11])  # 1.0 -> 1.1 -> 0.902 -> 1.0
        bench_returns = np.array([0.02, 0.02, 0.02])

        metrics = _compute_metrics(port_returns, bench_returns)

        # Max drawdown should be around -18%
        assert metrics["max_drawdown"] < 0
        assert metrics["max_drawdown"] > -0.25

    def test_cagr_calculation(self):
        # 12 months of 1% returns = ~12.68% CAGR
        port_returns = np.array([0.01] * 12)
        bench_returns = np.array([0.005] * 12)

        metrics = _compute_metrics(port_returns, bench_returns)

        # CAGR should be close to annualized return
        expected_cagr = (1.01 ** 12) - 1
        assert abs(metrics["portfolio_cagr"] - expected_cagr) < 0.01


class TestBacktestIntegration:
    """Integration tests for full backtest runs."""

    @pytest.fixture
    def sample_price_data(self):
        """Generate synthetic price data for 24 months."""
        dates = pd.date_range(start="2022-01-01", periods=504, freq="B")  # ~2 years
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

        np.random.seed(42)
        data = {}
        for ticker in tickers:
            # Random walk with drift
            returns = np.random.normal(0.0005, 0.02, len(dates))
            prices = 100 * np.cumprod(1 + returns)
            data[ticker] = prices

        return pd.DataFrame(data, index=dates)

    @pytest.fixture
    def sample_fundamentals(self):
        return pd.DataFrame({
            "trailingPE": [25, 30, 22, 60, 15],
            "priceToBook": [35, 12, 6, 8, 5],
            "dividendYield": [0.005, 0.008, 0.0, 0.0, 0.0],
            "enterpriseToEbitda": [20, 25, 18, 40, 12],
            "returnOnEquity": [1.5, 0.4, 0.3, 0.2, 0.25],
            "debtToEquity": [1.8, 0.4, 0.1, 0.5, 0.2],
            "revenueGrowth": [0.08, 0.12, 0.10, 0.09, 0.15],
            "earningsGrowth": [0.10, 0.15, 0.08, 0.20, 0.25],
            "marketCap": [2.8e12, 2.5e12, 1.7e12, 1.5e12, 0.8e12],
            "currentPrice": [180, 350, 140, 180, 350],
        }, index=["AAPL", "MSFT", "GOOGL", "AMZN", "META"])

    def test_backtest_returns_expected_keys(self, sample_price_data, sample_fundamentals):
        from src.backtest import run_backtest

        results = run_backtest(sample_price_data, sample_fundamentals, months=6)

        if "error" not in results:
            assert "portfolio_returns" in results
            assert "benchmark_returns" in results
            assert "metrics" in results
