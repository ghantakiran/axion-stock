"""Momentum Factors - Identify stocks with positive price and earnings trends.

Factors:
1. 12-1 Month Momentum - Classic cross-sectional momentum (skip last month)
2. 6-1 Month Momentum - Medium-term trend
3. 3-Month Momentum - Short-term trend
4. 52-Week High Proximity - George & Hwang (2004) predictor
5. Earnings Momentum - Standardized Unexpected Earnings proxy
6. Revenue Momentum - Sales growth acceleration
"""

from typing import Optional

import numpy as np
import pandas as pd

from src.factors.base import (
    Factor,
    FactorCalculator,
    FactorCategory,
    FactorDirection,
)


class MomentumFactors(FactorCalculator):
    """Calculator for momentum factors."""
    
    # Trading days approximations
    DAYS_1M = 21
    DAYS_3M = 63
    DAYS_6M = 126
    DAYS_12M = 252
    
    def __init__(self):
        super().__init__()
        self.category = FactorCategory(
            name="momentum",
            description="Identify stocks with positive price and earnings trends",
            default_weight=0.25,  # Base weight, adjusted by regime
        )
        self._register_factors()
    
    def _register_factors(self) -> None:
        """Register all momentum factors."""
        self.category.factors = [
            Factor(
                name="momentum_12_1",
                description="12-month return excluding last month",
                direction=FactorDirection.POSITIVE,
                weight=0.25,
            ),
            Factor(
                name="momentum_6_1",
                description="6-month return excluding last month",
                direction=FactorDirection.POSITIVE,
                weight=0.25,
            ),
            Factor(
                name="momentum_3m",
                description="3-month return",
                direction=FactorDirection.POSITIVE,
                weight=0.15,
            ),
            Factor(
                name="high_52w_proximity",
                description="Price / 52-week high",
                direction=FactorDirection.POSITIVE,
                weight=0.15,
            ),
            Factor(
                name="earnings_momentum",
                description="Earnings growth trend (proxy for SUE)",
                direction=FactorDirection.POSITIVE,
                weight=0.10,
            ),
            Factor(
                name="revenue_momentum",
                description="Revenue growth acceleration",
                direction=FactorDirection.POSITIVE,
                weight=0.10,
            ),
        ]
    
    def compute(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        market_data: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Compute all momentum factors.
        
        Args:
            prices: Price DataFrame (dates x tickers)
            fundamentals: Fundamentals DataFrame with earningsGrowth, revenueGrowth
            market_data: Not used for momentum factors
            
        Returns:
            DataFrame with tickers as index, momentum factor scores as columns
        """
        # Get common tickers between prices and fundamentals
        price_tickers = set(prices.columns)
        fund_tickers = set(fundamentals.index)
        tickers = sorted(price_tickers | fund_tickers)
        
        scores = pd.DataFrame(index=tickers)
        
        # 1. 12-1 Month Momentum (skip last month to avoid reversal)
        if len(prices) >= self.DAYS_12M:
            prices_ex_1m = prices.iloc[:-self.DAYS_1M]
            ret_12_1 = self._compute_return(prices_ex_1m, self.DAYS_12M - self.DAYS_1M)
            ret_12_1 = self.winsorize(ret_12_1, 0.01, 0.99)
            scores["momentum_12_1"] = self.percentile_rank(ret_12_1, ascending=True)
        else:
            scores["momentum_12_1"] = 0.5
        
        # 2. 6-1 Month Momentum (skip last month)
        if len(prices) >= self.DAYS_6M:
            prices_ex_1m = prices.iloc[:-self.DAYS_1M]
            ret_6_1 = self._compute_return(prices_ex_1m, self.DAYS_6M - self.DAYS_1M)
            ret_6_1 = self.winsorize(ret_6_1, 0.01, 0.99)
            scores["momentum_6_1"] = self.percentile_rank(ret_6_1, ascending=True)
        else:
            scores["momentum_6_1"] = 0.5
        
        # 3. 3-Month Momentum (including recent month for short-term signal)
        if len(prices) >= self.DAYS_3M:
            ret_3m = self._compute_return(prices, self.DAYS_3M)
            ret_3m = self.winsorize(ret_3m, 0.01, 0.99)
            scores["momentum_3m"] = self.percentile_rank(ret_3m, ascending=True)
        else:
            scores["momentum_3m"] = 0.5
        
        # 4. 52-Week High Proximity
        if len(prices) >= self.DAYS_12M:
            high_52w = prices.iloc[-self.DAYS_12M:].max()
            current = prices.iloc[-1]
            proximity = current / high_52w
            proximity = proximity.replace([np.inf, -np.inf], np.nan)
            scores["high_52w_proximity"] = self.percentile_rank(proximity, ascending=True)
        else:
            scores["high_52w_proximity"] = 0.5
        
        # 5. Earnings Momentum (using earningsGrowth as proxy for SUE)
        if "earningsGrowth" in fundamentals.columns:
            eg = fundamentals["earningsGrowth"].replace([np.inf, -np.inf], np.nan)
            eg = self.winsorize(eg, 0.01, 0.99)
            scores["earnings_momentum"] = self.percentile_rank(eg, ascending=True)
        else:
            scores["earnings_momentum"] = 0.5
        
        # 6. Revenue Momentum
        if "revenueGrowth" in fundamentals.columns:
            rg = fundamentals["revenueGrowth"].replace([np.inf, -np.inf], np.nan)
            rg = self.winsorize(rg, 0.01, 0.99)
            scores["revenue_momentum"] = self.percentile_rank(rg, ascending=True)
        else:
            scores["revenue_momentum"] = 0.5
        
        # Reindex to ensure all tickers are present
        scores = scores.reindex(tickers).fillna(0.5)
        
        return scores
    
    def _compute_return(self, prices: pd.DataFrame, periods: int) -> pd.Series:
        """Compute returns over N periods for each ticker."""
        if len(prices) < periods:
            return pd.Series(dtype=float)
        
        end_prices = prices.iloc[-1]
        start_idx = max(0, len(prices) - periods)
        start_prices = prices.iloc[start_idx]
        
        # Avoid division by zero
        start_prices = start_prices.replace(0, np.nan)
        returns = (end_prices / start_prices - 1)
        return returns.replace([np.inf, -np.inf], np.nan)
    
    def get_composite_score(self, scores: pd.DataFrame) -> pd.Series:
        """Compute weighted composite momentum score."""
        weights = {f.name: f.weight for f in self.category.factors}
        return self.combine_subfactors(scores, weights)
