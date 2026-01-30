"""Quality Factors - Identify companies with strong fundamentals and low risk.

Factors:
1. Return on Equity (ROE) - Profitability measure
2. Return on Assets (ROA) - Asset efficiency (approximated)
3. Return on Invested Capital (ROIC) - True returns on capital (approximated)
4. Gross Profit / Assets - Novy-Marx quality factor (approximated)
5. Accruals - Earnings quality (lower is better)
6. Debt/Equity - Leverage risk (lower is better)
7. Interest Coverage - Debt service ability (approximated)
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


class QualityFactors(FactorCalculator):
    """Calculator for quality factors."""
    
    def __init__(self):
        super().__init__()
        self.category = FactorCategory(
            name="quality",
            description="Identify companies with strong fundamentals and low risk",
            default_weight=0.25,  # Base weight, adjusted by regime
        )
        self._register_factors()
    
    def _register_factors(self) -> None:
        """Register all quality factors."""
        self.category.factors = [
            Factor(
                name="roe",
                description="Return on Equity",
                direction=FactorDirection.POSITIVE,
                weight=0.20,
            ),
            Factor(
                name="roa",
                description="Return on Assets (proxy)",
                direction=FactorDirection.POSITIVE,
                weight=0.15,
            ),
            Factor(
                name="roic",
                description="Return on Invested Capital (proxy)",
                direction=FactorDirection.POSITIVE,
                weight=0.15,
            ),
            Factor(
                name="gross_profit_assets",
                description="Gross Profit / Assets (Novy-Marx proxy)",
                direction=FactorDirection.POSITIVE,
                weight=0.15,
            ),
            Factor(
                name="accruals",
                description="Earnings quality via accruals (lower is better)",
                direction=FactorDirection.NEGATIVE,
                weight=0.10,
            ),
            Factor(
                name="debt_equity",
                description="Debt to Equity ratio (lower is better)",
                direction=FactorDirection.NEGATIVE,
                weight=0.15,
            ),
            Factor(
                name="interest_coverage",
                description="Interest coverage proxy",
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
        """Compute all quality factors.
        
        Args:
            prices: Price DataFrame (dates x tickers) - used for some calculations
            fundamentals: Fundamentals DataFrame with:
                - returnOnEquity, debtToEquity
            market_data: Not used for quality factors
            
        Returns:
            DataFrame with tickers as index, quality factor scores as columns
        """
        tickers = fundamentals.index.tolist()
        scores = pd.DataFrame(index=tickers)
        
        # 1. Return on Equity (ROE)
        if "returnOnEquity" in fundamentals.columns:
            roe = fundamentals["returnOnEquity"].replace([np.inf, -np.inf], np.nan)
            roe = self.winsorize(roe, 0.01, 0.99)
            scores["roe"] = self.percentile_rank(roe, ascending=True)
        else:
            scores["roe"] = 0.5
        
        # 2. ROA - Approximate using ROE and leverage
        # ROA ≈ ROE / (1 + D/E)
        if "returnOnEquity" in fundamentals.columns and "debtToEquity" in fundamentals.columns:
            roe = fundamentals["returnOnEquity"]
            de = fundamentals["debtToEquity"].fillna(0).clip(lower=0)
            # ROA approximation
            roa = roe / (1 + de)
            roa = roa.replace([np.inf, -np.inf], np.nan)
            roa = self.winsorize(roa, 0.01, 0.99)
            scores["roa"] = self.percentile_rank(roa, ascending=True)
        else:
            scores["roa"] = 0.5
        
        # 3. ROIC - Approximate as adjusted ROE
        # True ROIC = NOPAT / Invested Capital, but we approximate with ROE adjustment
        if "returnOnEquity" in fundamentals.columns:
            roe = fundamentals["returnOnEquity"]
            # ROIC proxy: ROE adjusted down slightly (typically ROIC < ROE)
            roic = roe * 0.85
            roic = roic.replace([np.inf, -np.inf], np.nan)
            roic = self.winsorize(roic, 0.01, 0.99)
            scores["roic"] = self.percentile_rank(roic, ascending=True)
        else:
            scores["roic"] = 0.5
        
        # 4. Gross Profit / Assets (Novy-Marx quality factor)
        # Proxy: Higher ROE with lower leverage suggests better gross margins
        if "returnOnEquity" in fundamentals.columns and "debtToEquity" in fundamentals.columns:
            roe = fundamentals["returnOnEquity"]
            de = fundamentals["debtToEquity"].fillna(0).clip(lower=0, upper=10)
            # Higher ROE with lower debt = better quality proxy
            gpa_proxy = roe / (1 + de * 0.5)
            gpa_proxy = gpa_proxy.replace([np.inf, -np.inf], np.nan)
            gpa_proxy = self.winsorize(gpa_proxy, 0.01, 0.99)
            scores["gross_profit_assets"] = self.percentile_rank(gpa_proxy, ascending=True)
        else:
            scores["gross_profit_assets"] = 0.5
        
        # 5. Accruals - Lower is better (better earnings quality)
        # Proxy: Stocks with high earnings growth but low price appreciation have high accruals
        if "earningsGrowth" in fundamentals.columns and not prices.empty:
            eg = fundamentals["earningsGrowth"].fillna(0)
            # Get price returns for tickers we have
            if len(prices) > 252:
                price_ret = (prices.iloc[-1] / prices.iloc[-252] - 1)
            else:
                price_ret = (prices.iloc[-1] / prices.iloc[0] - 1)
            
            # Accruals proxy: earnings growth not backed by price appreciation
            accruals = pd.Series(index=tickers, dtype=float)
            for t in tickers:
                if t in price_ret.index and t in eg.index:
                    accruals[t] = max(0, eg[t] - price_ret.get(t, 0))
                else:
                    accruals[t] = np.nan
            
            accruals = self.winsorize(accruals, 0.01, 0.99)
            scores["accruals"] = self.percentile_rank(accruals, ascending=False)
        else:
            scores["accruals"] = 0.5
        
        # 6. Debt/Equity (lower is better)
        if "debtToEquity" in fundamentals.columns:
            de = fundamentals["debtToEquity"].replace([np.inf, -np.inf], np.nan)
            de = de.clip(lower=0)  # Negative D/E doesn't make sense
            de = self.winsorize(de, 0.01, 0.99)
            scores["debt_equity"] = self.percentile_rank(de, ascending=False)
        else:
            scores["debt_equity"] = 0.5
        
        # 7. Interest Coverage (higher is better)
        # Proxy: Low debt + high profitability = good coverage
        if "debtToEquity" in fundamentals.columns and "returnOnEquity" in fundamentals.columns:
            de = fundamentals["debtToEquity"].fillna(0).clip(lower=0.01)
            roe = fundamentals["returnOnEquity"].fillna(0)
            # Coverage proxy: ROE / D/E (higher is better)
            coverage = roe / de
            coverage = coverage.replace([np.inf, -np.inf], np.nan)
            coverage = self.winsorize(coverage, 0.01, 0.99)
            scores["interest_coverage"] = self.percentile_rank(coverage, ascending=True)
        else:
            scores["interest_coverage"] = 0.5
        
        return scores
    
    def get_composite_score(self, scores: pd.DataFrame) -> pd.Series:
        """Compute weighted composite quality score."""
        weights = {f.name: f.weight for f in self.category.factors}
        return self.combine_subfactors(scores, weights)
