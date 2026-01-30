"""Growth Factors - Identify companies with accelerating business growth.

Factors:
1. Revenue Growth (YoY) - Top-line growth
2. EPS Growth (YoY) - Bottom-line growth
3. FCF Growth - Cash flow growth (proxy)
4. Revenue Growth Acceleration - Improving growth trajectory
5. R&D Intensity - Innovation investment (proxy)
6. Asset Growth - Expansion rate (lower can be better per anomaly literature)
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


class GrowthFactors(FactorCalculator):
    """Calculator for growth factors."""
    
    def __init__(self):
        super().__init__()
        self.category = FactorCategory(
            name="growth",
            description="Identify companies with accelerating business growth",
            default_weight=0.15,  # Base weight, adjusted by regime
        )
        self._register_factors()
    
    def _register_factors(self) -> None:
        """Register all growth factors."""
        self.category.factors = [
            Factor(
                name="revenue_growth",
                description="Year-over-year revenue growth",
                direction=FactorDirection.POSITIVE,
                weight=0.25,
            ),
            Factor(
                name="eps_growth",
                description="Year-over-year EPS growth",
                direction=FactorDirection.POSITIVE,
                weight=0.25,
            ),
            Factor(
                name="fcf_growth",
                description="Free cash flow growth (proxy)",
                direction=FactorDirection.POSITIVE,
                weight=0.15,
            ),
            Factor(
                name="growth_acceleration",
                description="Revenue growth acceleration",
                direction=FactorDirection.POSITIVE,
                weight=0.15,
            ),
            Factor(
                name="rd_intensity",
                description="R&D intensity proxy (growth stocks)",
                direction=FactorDirection.POSITIVE,
                weight=0.10,
            ),
            Factor(
                name="asset_growth",
                description="Asset growth (lower may be better)",
                direction=FactorDirection.NEGATIVE,
                weight=0.10,
            ),
        ]
    
    def compute(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        market_data: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Compute all growth factors.
        
        Args:
            prices: Price DataFrame (dates x tickers)
            fundamentals: Fundamentals DataFrame with:
                - revenueGrowth, earningsGrowth
            market_data: Not used for growth factors
            
        Returns:
            DataFrame with tickers as index, growth factor scores as columns
        """
        tickers = fundamentals.index.tolist()
        scores = pd.DataFrame(index=tickers)
        
        # 1. Revenue Growth (YoY)
        if "revenueGrowth" in fundamentals.columns:
            rg = fundamentals["revenueGrowth"].replace([np.inf, -np.inf], np.nan)
            rg = self.winsorize(rg, 0.01, 0.99)
            scores["revenue_growth"] = self.percentile_rank(rg, ascending=True)
        else:
            scores["revenue_growth"] = 0.5
        
        # 2. EPS Growth (YoY)
        if "earningsGrowth" in fundamentals.columns:
            eg = fundamentals["earningsGrowth"].replace([np.inf, -np.inf], np.nan)
            eg = self.winsorize(eg, 0.01, 0.99)
            scores["eps_growth"] = self.percentile_rank(eg, ascending=True)
        else:
            scores["eps_growth"] = 0.5
        
        # 3. FCF Growth - Proxy using earnings growth combined with quality
        # Higher earnings growth + lower debt = better FCF growth
        if "earningsGrowth" in fundamentals.columns:
            eg = fundamentals["earningsGrowth"].fillna(0)
            de = fundamentals.get("debtToEquity", pd.Series(0, index=tickers)).fillna(0)
            de = de.clip(lower=0, upper=5)
            
            # FCF growth proxy: earnings growth discounted by leverage
            fcf_growth = eg / (1 + de * 0.2)
            fcf_growth = fcf_growth.replace([np.inf, -np.inf], np.nan)
            fcf_growth = self.winsorize(fcf_growth, 0.01, 0.99)
            scores["fcf_growth"] = self.percentile_rank(fcf_growth, ascending=True)
        else:
            scores["fcf_growth"] = 0.5
        
        # 4. Growth Acceleration
        # Proxy: High growth stocks with positive momentum are accelerating
        if "revenueGrowth" in fundamentals.columns and not prices.empty:
            rg = fundamentals["revenueGrowth"].fillna(0)
            
            # Price momentum as proxy for growth trajectory
            if len(prices) > 63:
                price_mom = (prices.iloc[-1] / prices.iloc[-63] - 1)
            else:
                price_mom = pd.Series(0, index=prices.columns)
            
            # Acceleration = revenue growth * positive momentum
            accel = pd.Series(index=tickers, dtype=float)
            for t in tickers:
                rg_val = rg.get(t, 0)
                mom_val = price_mom.get(t, 0)
                if pd.notna(rg_val) and pd.notna(mom_val):
                    accel[t] = rg_val * (1 + max(0, mom_val))
                else:
                    accel[t] = np.nan
            
            accel = self.winsorize(accel, 0.01, 0.99)
            scores["growth_acceleration"] = self.percentile_rank(accel, ascending=True)
        else:
            scores["growth_acceleration"] = 0.5
        
        # 5. R&D Intensity (proxy using growth characteristics)
        # High growth + high PE = R&D intensive (market paying for future growth)
        if "revenueGrowth" in fundamentals.columns and "trailingPE" in fundamentals.columns:
            rg = fundamentals["revenueGrowth"].fillna(0)
            pe = fundamentals["trailingPE"].fillna(15)
            pe = pe.clip(lower=5, upper=100)
            
            # R&D proxy: high growth stocks with premium valuations
            rd_proxy = rg * np.log(pe / 15 + 1)
            rd_proxy = rd_proxy.replace([np.inf, -np.inf], np.nan)
            rd_proxy = self.winsorize(rd_proxy, 0.01, 0.99)
            scores["rd_intensity"] = self.percentile_rank(rd_proxy, ascending=True)
        else:
            scores["rd_intensity"] = 0.5
        
        # 6. Asset Growth (lower is often better - asset growth anomaly)
        # Proxy: Companies growing assets rapidly may have lower future returns
        # Use market cap growth as proxy
        if not prices.empty and "marketCap" in fundamentals.columns:
            # Price change over 1 year as proxy for asset/market cap growth
            if len(prices) > 252:
                asset_growth = (prices.iloc[-1] / prices.iloc[-252] - 1)
            else:
                asset_growth = (prices.iloc[-1] / prices.iloc[0] - 1)
            
            asset_growth = asset_growth.replace([np.inf, -np.inf], np.nan)
            asset_growth = self.winsorize(asset_growth, 0.01, 0.99)
            # Lower asset growth is better (ascending=False)
            scores["asset_growth"] = self.percentile_rank(asset_growth, ascending=False)
        else:
            scores["asset_growth"] = 0.5
        
        return scores
    
    def get_composite_score(self, scores: pd.DataFrame) -> pd.Series:
        """Compute weighted composite growth score."""
        weights = {f.name: f.weight for f in self.category.factors}
        return self.combine_subfactors(scores, weights)
