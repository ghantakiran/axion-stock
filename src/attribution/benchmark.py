"""Benchmark comparison analysis.

Computes tracking error, information ratio, capture ratios, and other
relative performance metrics.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.attribution.config import (
    TRADING_DAYS_PER_YEAR,
    RISK_FREE_RATE,
    AttributionConfig,
    DEFAULT_ATTRIBUTION_CONFIG,
)
from src.attribution.models import BenchmarkComparison

logger = logging.getLogger(__name__)


class BenchmarkAnalyzer:
    """Benchmark comparison analysis.

    Computes relative performance metrics between a portfolio
    and its benchmark.
    """

    def __init__(self, config: Optional[AttributionConfig] = None) -> None:
        self.config = config or DEFAULT_ATTRIBUTION_CONFIG

    def compare(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: pd.Series,
        benchmark_id: str = "SPY",
        benchmark_name: str = "S&P 500",
        portfolio_weights: Optional[dict[str, float]] = None,
        benchmark_weights: Optional[dict[str, float]] = None,
    ) -> BenchmarkComparison:
        """Compare portfolio to benchmark.

        Args:
            portfolio_returns: Portfolio daily returns.
            benchmark_returns: Benchmark daily returns.
            benchmark_id: Benchmark identifier.
            benchmark_name: Benchmark display name.
            portfolio_weights: Portfolio holdings weights (for active share).
            benchmark_weights: Benchmark holdings weights (for active share).

        Returns:
            BenchmarkComparison.
        """
        # Align
        common_idx = portfolio_returns.index.intersection(benchmark_returns.index)
        if len(common_idx) < 2:
            return BenchmarkComparison(
                benchmark_id=benchmark_id,
                benchmark_name=benchmark_name,
            )

        pr = portfolio_returns.loc[common_idx]
        br = benchmark_returns.loc[common_idx]
        n = len(common_idx)
        tdy = self.config.trading_days_per_year

        # Returns
        port_total = float((1 + pr).prod() - 1)
        bm_total = float((1 + br).prod() - 1)
        active = port_total - bm_total

        # Tracking error
        active_returns = pr - br
        te = float(active_returns.std() * np.sqrt(tdy))

        # Information ratio
        ir = float(active_returns.mean() / active_returns.std() * np.sqrt(tdy)) if active_returns.std() > 0 else 0.0

        # Beta and alpha
        cov_matrix = np.cov(pr, br)
        beta = float(cov_matrix[0, 1] / cov_matrix[1, 1]) if cov_matrix[1, 1] > 0 else 0.0

        rf_daily = (1 + self.config.risk_free_rate) ** (1 / tdy) - 1
        port_ann = float((1 + port_total) ** (tdy / n) - 1) if n > 0 else 0.0
        bm_ann = float((1 + bm_total) ** (tdy / n) - 1) if n > 0 else 0.0
        alpha = port_ann - (self.config.risk_free_rate + beta * (bm_ann - self.config.risk_free_rate))

        # Correlation
        correlation = float(np.corrcoef(pr, br)[0, 1]) if len(pr) > 1 else 0.0

        # Capture ratios
        up_capture = self._capture_ratio(pr, br, up=True)
        down_capture = self._capture_ratio(pr, br, up=False)

        # Active share
        active_share = 0.0
        if portfolio_weights and benchmark_weights:
            active_share = self._active_share(portfolio_weights, benchmark_weights)

        return BenchmarkComparison(
            benchmark_id=benchmark_id,
            benchmark_name=benchmark_name,
            portfolio_return=port_total,
            benchmark_return=bm_total,
            active_return=active,
            tracking_error=te,
            information_ratio=ir,
            active_share=active_share,
            up_capture=up_capture,
            down_capture=down_capture,
            beta=beta,
            alpha=alpha,
            correlation=correlation,
        )

    def _capture_ratio(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: pd.Series,
        up: bool = True,
    ) -> float:
        """Compute up or down capture ratio.

        Args:
            portfolio_returns: Portfolio daily returns.
            benchmark_returns: Benchmark daily returns.
            up: If True, compute up capture; else down capture.

        Returns:
            Capture ratio (1.0 = matches benchmark).
        """
        if up:
            mask = benchmark_returns > 0
        else:
            mask = benchmark_returns < 0

        bm_filtered = benchmark_returns[mask]
        pr_filtered = portfolio_returns[mask]

        if len(bm_filtered) == 0:
            return 0.0

        bm_cum = float((1 + bm_filtered).prod() - 1)
        pr_cum = float((1 + pr_filtered).prod() - 1)

        if abs(bm_cum) < 1e-10:
            return 0.0

        return pr_cum / bm_cum

    @staticmethod
    def _active_share(
        portfolio_weights: dict[str, float],
        benchmark_weights: dict[str, float],
    ) -> float:
        """Compute active share.

        Active share = 0.5 × Σ|wp_i - wb_i|

        Args:
            portfolio_weights: Security -> portfolio weight.
            benchmark_weights: Security -> benchmark weight.

        Returns:
            Active share (0 to 1).
        """
        all_securities = set(portfolio_weights) | set(benchmark_weights)
        total_diff = sum(
            abs(
                portfolio_weights.get(s, 0.0) - benchmark_weights.get(s, 0.0)
            )
            for s in all_securities
        )
        return 0.5 * total_diff
