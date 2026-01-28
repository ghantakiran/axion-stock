"""Momentum factor category: Price trend and earnings momentum."""

import numpy as np
import pandas as pd

from src.factor_engine.factors.base import (
    FactorCategory,
    percentile_rank,
    safe_divide,
)


class MomentumFactors(FactorCategory):
    """Momentum factors: Stocks with strong price and earnings trends.

    Sub-factors:
    - 12-1 Month Momentum - classic Jegadeesh-Titman momentum (skip last month)
    - 6-1 Month Momentum - medium-term trend
    - 3-Month Momentum - short-term trend
    - 52-Week High Proximity - George & Hwang (2004)
    - Earnings Momentum (if available) - post-earnings drift
    - Revenue Momentum (if available) - sales trend acceleration

    Higher returns = higher momentum score.
    """

    name = "momentum"
    sub_factors = [
        "ret_12m",
        "ret_6m",
        "ret_3m",
        "high_52w_proximity",
        "earnings_momentum",
        "revenue_momentum",
    ]

    # Sub-factor weights (sum to 1.0)
    weights = {
        "ret_12m": 0.25,
        "ret_6m": 0.30,
        "ret_3m": 0.15,
        "high_52w_proximity": 0.15,
        "earnings_momentum": 0.10,
        "revenue_momentum": 0.05,
    }

    def compute(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        returns: pd.DataFrame,
    ) -> pd.Series:
        """Compute momentum factor score for all tickers."""
        sub_scores = self.compute_sub_factors(prices, fundamentals, returns)

        # Weighted average of available sub-factors
        score = pd.Series(0.0, index=returns.index)
        total_weight = 0.0

        for factor, weight in self.weights.items():
            if factor in sub_scores.columns:
                col = sub_scores[factor]
                valid_mask = col.notna()
                score = score.add(weight * col.fillna(0), fill_value=0)
                total_weight += weight * valid_mask.astype(float).fillna(0)

        # Normalize by actual weights used
        score = safe_divide(score, total_weight.replace(0, 1))
        return score.reindex(returns.index).fillna(0.5)

    def compute_sub_factors(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        returns: pd.DataFrame,
    ) -> pd.DataFrame:
        """Compute individual momentum sub-factor scores."""
        result = pd.DataFrame(index=returns.index)

        # Price momentum from returns DataFrame
        if "ret_12m" in returns.columns:
            result["ret_12m"] = percentile_rank(returns["ret_12m"])

        if "ret_6m" in returns.columns:
            result["ret_6m"] = percentile_rank(returns["ret_6m"])

        if "ret_3m" in returns.columns:
            result["ret_3m"] = percentile_rank(returns["ret_3m"])

        # 52-week high proximity: current price / 52-week high
        if not prices.empty and len(prices) >= 252:
            high_52w = prices.iloc[-252:].max()
            current_price = prices.iloc[-1]
            proximity = safe_divide(current_price, high_52w)
            # Reindex to match returns index
            proximity = proximity.reindex(returns.index)
            result["high_52w_proximity"] = percentile_rank(proximity)
        elif not prices.empty:
            # Use available data if less than 252 days
            high_52w = prices.max()
            current_price = prices.iloc[-1]
            proximity = safe_divide(current_price, high_52w)
            proximity = proximity.reindex(returns.index)
            result["high_52w_proximity"] = percentile_rank(proximity)

        # Earnings momentum from fundamentals (YoY growth)
        if "earningsGrowth" in fundamentals.columns:
            eg = fundamentals["earningsGrowth"].reindex(returns.index)
            result["earnings_momentum"] = percentile_rank(eg)

        # Revenue momentum from fundamentals (YoY growth)
        if "revenueGrowth" in fundamentals.columns:
            rg = fundamentals["revenueGrowth"].reindex(returns.index)
            result["revenue_momentum"] = percentile_rank(rg)

        return result
