"""Base classes for the Factor Engine v2.0."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd


class FactorDirection(Enum):
    """Whether higher raw values are better (POSITIVE) or worse (NEGATIVE)."""
    POSITIVE = "positive"  # Higher is better (e.g., ROE, momentum)
    NEGATIVE = "negative"  # Lower is better (e.g., P/E, debt ratio)


@dataclass
class Factor:
    """Individual factor definition."""
    name: str
    description: str
    direction: FactorDirection
    weight: float = 1.0  # Relative weight within category
    
    def __hash__(self):
        return hash(self.name)


@dataclass
class FactorCategory:
    """A category of related factors (e.g., Value, Momentum)."""
    name: str
    description: str
    factors: list[Factor] = field(default_factory=list)
    default_weight: float = 0.0  # Weight in composite score
    
    def add_factor(self, factor: Factor) -> None:
        """Add a factor to this category."""
        self.factors.append(factor)


class FactorCalculator(ABC):
    """Abstract base class for factor calculators."""
    
    def __init__(self):
        self.category: Optional[FactorCategory] = None
    
    @abstractmethod
    def compute(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        market_data: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Compute all factors in this category.
        
        Args:
            prices: DataFrame with dates as index, tickers as columns (adjusted close)
            fundamentals: DataFrame with tickers as index, fundamental fields as columns
            market_data: Optional market-level data (e.g., SPY prices for beta)
            
        Returns:
            DataFrame with tickers as index, factor names as columns (percentile scores 0-1)
        """
        pass
    
    @staticmethod
    def percentile_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
        """Convert raw values to percentile ranks in [0, 1].
        
        Args:
            series: Raw factor values
            ascending: If True, higher values get higher ranks (for positive factors)
                      If False, lower values get higher ranks (for negative factors like P/E)
        
        Returns:
            Percentile-ranked series with NaN filled with 0.5 (median)
        """
        if ascending:
            ranked = series.rank(pct=True, na_option='keep')
        else:
            # Invert: lower raw values get higher percentile scores
            ranked = 1.0 - series.rank(pct=True, na_option='keep')
        return ranked.fillna(0.5)
    
    @staticmethod
    def winsorize(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
        """Winsorize extreme values to reduce outlier impact.
        
        Args:
            series: Raw values
            lower: Lower percentile cutoff (values below are clipped)
            upper: Upper percentile cutoff (values above are clipped)
            
        Returns:
            Winsorized series
        """
        lower_bound = series.quantile(lower)
        upper_bound = series.quantile(upper)
        return series.clip(lower=lower_bound, upper=upper_bound)
    
    @staticmethod
    def zscore(series: pd.Series) -> pd.Series:
        """Standardize to z-scores (mean=0, std=1)."""
        mean = series.mean()
        std = series.std()
        if std == 0 or pd.isna(std):
            return pd.Series(0.0, index=series.index)
        return (series - mean) / std
    
    @staticmethod
    def compute_returns(prices: pd.DataFrame, periods: int) -> pd.Series:
        """Compute returns over N periods for each ticker.
        
        Args:
            prices: Price DataFrame (dates x tickers)
            periods: Number of trading days
            
        Returns:
            Series with tickers as index, returns as values
        """
        if len(prices) < periods:
            return pd.Series(dtype=float)
        
        end_prices = prices.iloc[-1]
        start_prices = prices.iloc[-periods] if periods <= len(prices) else prices.iloc[0]
        
        returns = (end_prices / start_prices - 1).replace([np.inf, -np.inf], np.nan)
        return returns
    
    def combine_subfactors(
        self,
        scores: pd.DataFrame,
        weights: Optional[dict[str, float]] = None,
    ) -> pd.Series:
        """Combine multiple sub-factor scores into a single category score.
        
        Args:
            scores: DataFrame with tickers as index, factor names as columns
            weights: Optional dict mapping factor names to weights (default: equal weight)
            
        Returns:
            Series with tickers as index, combined score as values
        """
        if scores.empty:
            return pd.Series(dtype=float)
        
        if weights is None:
            # Equal weight
            weights = {col: 1.0 / len(scores.columns) for col in scores.columns}
        
        # Normalize weights
        total_weight = sum(weights.get(col, 0) for col in scores.columns)
        if total_weight == 0:
            return pd.Series(0.5, index=scores.index)
        
        combined = pd.Series(0.0, index=scores.index)
        for col in scores.columns:
            w = weights.get(col, 0) / total_weight
            combined += w * scores[col].fillna(0.5)
        
        return combined
