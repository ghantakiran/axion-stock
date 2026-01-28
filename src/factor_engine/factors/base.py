"""Base class for factor categories."""

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class FactorCategory(ABC):
    """Abstract base class for a factor category (e.g., Value, Momentum)."""

    name: str = ""
    sub_factors: list[str] = []

    @abstractmethod
    def compute(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        returns: pd.DataFrame,
    ) -> pd.Series:
        """Compute the category score for all tickers.

        Args:
            prices: DataFrame[dates x tickers] of adjusted close prices
            fundamentals: DataFrame[tickers x fields] of fundamental data
            returns: DataFrame[tickers x {ret_3m, ret_6m, ret_12m}] of momentum returns

        Returns:
            Series[tickers] with scores in [0, 1] range
        """
        pass

    def compute_sub_factors(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        returns: pd.DataFrame,
    ) -> pd.DataFrame:
        """Compute individual sub-factor scores.

        Returns DataFrame[tickers x sub_factors] with each sub-factor score.
        Default implementation returns empty DataFrame; override for detailed breakdown.
        """
        return pd.DataFrame(index=fundamentals.index)


def percentile_rank(series: pd.Series) -> pd.Series:
    """Rank values as percentiles in [0, 1]. NaN → 0.5 (median)."""
    ranked = series.rank(pct=True)
    return ranked.fillna(0.5)


def invert_rank(series: pd.Series) -> pd.Series:
    """Lower raw values → higher score (for PE, PB, debt, volatility, etc.)."""
    return 1.0 - percentile_rank(series)


def winsorize(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """Winsorize extreme values to percentile bounds."""
    low_val = series.quantile(lower)
    high_val = series.quantile(upper)
    return series.clip(lower=low_val, upper=high_val)


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Safe division handling zeros and NaNs."""
    with np.errstate(divide="ignore", invalid="ignore"):
        result = numerator / denominator
        result = result.replace([np.inf, -np.inf], np.nan)
    return result
