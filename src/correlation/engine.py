"""Correlation Computation Engine.

Computes correlation matrices, rolling correlations,
and identifies correlated/uncorrelated pairs.
"""

import logging
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from src.correlation.config import (
    CorrelationConfig,
    RollingConfig,
    CorrelationMethod,
    WindowType,
    DEFAULT_CORRELATION_CONFIG,
    DEFAULT_ROLLING_CONFIG,
)
from src.correlation.models import (
    CorrelationMatrix,
    CorrelationPair,
    RollingCorrelation,
)

logger = logging.getLogger(__name__)


class CorrelationEngine:
    """Computes correlation matrices and pair analysis.

    Supports Pearson, Spearman, and Kendall methods with
    rolling window and pair identification capabilities.
    """

    def __init__(
        self,
        config: Optional[CorrelationConfig] = None,
        rolling_config: Optional[RollingConfig] = None,
    ) -> None:
        self.config = config or DEFAULT_CORRELATION_CONFIG
        self.rolling_config = rolling_config or DEFAULT_ROLLING_CONFIG

    def compute_matrix(
        self,
        returns: pd.DataFrame,
        method: Optional[CorrelationMethod] = None,
    ) -> CorrelationMatrix:
        """Compute correlation matrix from returns data.

        Args:
            returns: DataFrame with DatetimeIndex/date index, columns are symbols.
            method: Correlation method override.

        Returns:
            CorrelationMatrix with N×N values.
        """
        method = method or self.config.method
        symbols = list(returns.columns)

        if self.config.handle_missing == "dropna":
            returns = returns.dropna()

        corr_df = returns.corr(method=method.value, min_periods=self.config.min_periods)
        values = corr_df.values

        start_date = None
        end_date = None
        if len(returns.index) > 0:
            idx = returns.index
            start_date = idx[0] if isinstance(idx[0], date) else idx[0].date()
            end_date = idx[-1] if isinstance(idx[-1], date) else idx[-1].date()

        return CorrelationMatrix(
            symbols=symbols,
            values=values,
            method=method,
            n_periods=len(returns),
            start_date=start_date,
            end_date=end_date,
        )

    def get_top_pairs(
        self,
        matrix: CorrelationMatrix,
        n: int = 10,
        ascending: bool = False,
    ) -> list[CorrelationPair]:
        """Get top N correlated or least correlated pairs.

        Args:
            matrix: Computed correlation matrix.
            n: Number of pairs to return.
            ascending: If True, return least correlated pairs.

        Returns:
            List of CorrelationPair sorted by correlation.
        """
        if matrix.values is None or matrix.n_assets < 2:
            return []

        pairs: list[CorrelationPair] = []
        for i in range(matrix.n_assets):
            for j in range(i + 1, matrix.n_assets):
                pairs.append(CorrelationPair(
                    symbol_a=matrix.symbols[i],
                    symbol_b=matrix.symbols[j],
                    correlation=round(float(matrix.values[i, j]), 4),
                    method=matrix.method,
                    n_periods=matrix.n_periods,
                ))

        pairs.sort(key=lambda p: p.correlation, reverse=not ascending)
        return pairs[:n]

    def get_highly_correlated(
        self,
        matrix: CorrelationMatrix,
        threshold: float = 0.70,
    ) -> list[CorrelationPair]:
        """Get all pairs above correlation threshold.

        Args:
            matrix: Computed correlation matrix.
            threshold: Absolute correlation threshold.

        Returns:
            Pairs with |correlation| >= threshold.
        """
        if matrix.values is None or matrix.n_assets < 2:
            return []

        pairs: list[CorrelationPair] = []
        for i in range(matrix.n_assets):
            for j in range(i + 1, matrix.n_assets):
                corr = float(matrix.values[i, j])
                if abs(corr) >= threshold:
                    pairs.append(CorrelationPair(
                        symbol_a=matrix.symbols[i],
                        symbol_b=matrix.symbols[j],
                        correlation=round(corr, 4),
                        method=matrix.method,
                        n_periods=matrix.n_periods,
                    ))

        pairs.sort(key=lambda p: abs(p.correlation), reverse=True)
        return pairs

    def compute_rolling(
        self,
        returns: pd.DataFrame,
        symbol_a: str,
        symbol_b: str,
        window: Optional[int] = None,
    ) -> RollingCorrelation:
        """Compute rolling correlation between two assets.

        Args:
            returns: DataFrame of returns.
            symbol_a: First symbol.
            symbol_b: Second symbol.
            window: Rolling window size override.

        Returns:
            RollingCorrelation time series.
        """
        window = window or self.rolling_config.window
        min_periods = self.rolling_config.min_periods

        if symbol_a not in returns.columns or symbol_b not in returns.columns:
            return RollingCorrelation(symbol_a=symbol_a, symbol_b=symbol_b, window=window)

        a = returns[symbol_a]
        b = returns[symbol_b]

        if self.rolling_config.window_type == WindowType.EXPONENTIAL:
            rolling_corr = a.ewm(halflife=self.rolling_config.half_life, min_periods=min_periods).corr(b)
        elif self.rolling_config.window_type == WindowType.EXPANDING:
            rolling_corr = a.expanding(min_periods=min_periods).corr(b)
        else:
            rolling_corr = a.rolling(window=window, min_periods=min_periods).corr(b)

        rolling_corr = rolling_corr.dropna()

        dates = []
        for idx in rolling_corr.index:
            if isinstance(idx, date):
                dates.append(idx)
            elif hasattr(idx, 'date'):
                dates.append(idx.date())
            else:
                dates.append(idx)

        return RollingCorrelation(
            symbol_a=symbol_a,
            symbol_b=symbol_b,
            dates=dates,
            values=[round(float(v), 4) for v in rolling_corr.values],
            window=window,
        )

    def compute_eigenvalues(self, matrix: CorrelationMatrix) -> np.ndarray:
        """Compute eigenvalues of the correlation matrix.

        Args:
            matrix: Correlation matrix.

        Returns:
            Sorted eigenvalues (descending).
        """
        if matrix.values is None:
            return np.array([])

        eigenvalues = np.linalg.eigvalsh(matrix.values)
        return np.sort(eigenvalues)[::-1]
