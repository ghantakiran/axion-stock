"""Value Factors - Identify undervalued stocks relative to fundamentals.

Factors:
1. Earnings Yield (EBIT/EV) - Better than P/E for capital structure differences
2. Free Cash Flow Yield (FCF/Market Cap) - Cash-based valuation
3. Book-to-Market (Book Value/Market Cap) - Classic Fama-French HML
4. EV/EBITDA - Debt-inclusive valuation
5. Dividend Yield - Income component
6. Forward P/E - Forward-looking value (approximated from trailing if not available)
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


class ValueFactors(FactorCalculator):
    """Calculator for value factors."""
    
    def __init__(self):
        super().__init__()
        self.category = FactorCategory(
            name="value",
            description="Identify undervalued stocks relative to fundamentals",
            default_weight=0.20,  # Base weight, adjusted by regime
        )
        self._register_factors()
    
    def _register_factors(self) -> None:
        """Register all value factors."""
        self.category.factors = [
            Factor(
                name="earnings_yield",
                description="EBIT / Enterprise Value",
                direction=FactorDirection.POSITIVE,
                weight=0.20,
            ),
            Factor(
                name="fcf_yield",
                description="Free Cash Flow / Market Cap",
                direction=FactorDirection.POSITIVE,
                weight=0.20,
            ),
            Factor(
                name="book_to_market",
                description="Book Value / Market Cap",
                direction=FactorDirection.POSITIVE,
                weight=0.15,
            ),
            Factor(
                name="ev_ebitda",
                description="Enterprise Value / EBITDA (inverted)",
                direction=FactorDirection.NEGATIVE,
                weight=0.20,
            ),
            Factor(
                name="dividend_yield",
                description="Annual Dividend / Price",
                direction=FactorDirection.POSITIVE,
                weight=0.10,
            ),
            Factor(
                name="earnings_pe",
                description="Trailing P/E (inverted)",
                direction=FactorDirection.NEGATIVE,
                weight=0.15,
            ),
        ]
    
    def compute(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        market_data: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Compute all value factors.
        
        Args:
            prices: Price DataFrame (dates x tickers)
            fundamentals: Fundamentals DataFrame with columns:
                - trailingPE, priceToBook, dividendYield, enterpriseToEbitda
                - marketCap, currentPrice
            market_data: Not used for value factors
            
        Returns:
            DataFrame with tickers as index, value factor scores as columns
        """
        tickers = fundamentals.index.tolist()
        scores = pd.DataFrame(index=tickers)
        
        # 1. Earnings Yield (inverse of P/E, but using earnings/price)
        if "trailingPE" in fundamentals.columns:
            pe = fundamentals["trailingPE"].replace([0, np.inf, -np.inf], np.nan)
            # Earnings yield = 1 / PE
            earnings_yield = 1.0 / pe
            earnings_yield = self.winsorize(earnings_yield, 0.01, 0.99)
            scores["earnings_yield"] = self.percentile_rank(earnings_yield, ascending=True)
        else:
            scores["earnings_yield"] = 0.5
        
        # 2. FCF Yield - Approximate from fundamentals if available
        # YFinance doesn't always have FCF directly, so we use earnings as proxy
        if "trailingPE" in fundamentals.columns and "marketCap" in fundamentals.columns:
            pe = fundamentals["trailingPE"].replace([0, np.inf, -np.inf], np.nan)
            market_cap = fundamentals["marketCap"]
            # Rough FCF yield proxy: earnings / market_cap = 1/PE
            fcf_yield = 1.0 / pe
            fcf_yield = self.winsorize(fcf_yield, 0.01, 0.99)
            scores["fcf_yield"] = self.percentile_rank(fcf_yield, ascending=True)
        else:
            scores["fcf_yield"] = 0.5
        
        # 3. Book-to-Market (inverse of Price-to-Book)
        if "priceToBook" in fundamentals.columns:
            pb = fundamentals["priceToBook"].replace([0, np.inf, -np.inf], np.nan)
            book_to_market = 1.0 / pb
            book_to_market = self.winsorize(book_to_market, 0.01, 0.99)
            scores["book_to_market"] = self.percentile_rank(book_to_market, ascending=True)
        else:
            scores["book_to_market"] = 0.5
        
        # 4. EV/EBITDA (lower is better, so ascending=False)
        if "enterpriseToEbitda" in fundamentals.columns:
            ev_ebitda = fundamentals["enterpriseToEbitda"].replace([np.inf, -np.inf], np.nan)
            ev_ebitda = self.winsorize(ev_ebitda, 0.01, 0.99)
            scores["ev_ebitda"] = self.percentile_rank(ev_ebitda, ascending=False)
        else:
            scores["ev_ebitda"] = 0.5
        
        # 5. Dividend Yield
        if "dividendYield" in fundamentals.columns:
            div_yield = fundamentals["dividendYield"].fillna(0)
            div_yield = self.winsorize(div_yield, 0.0, 0.99)
            scores["dividend_yield"] = self.percentile_rank(div_yield, ascending=True)
        else:
            scores["dividend_yield"] = 0.5
        
        # 6. P/E (lower is better for value)
        if "trailingPE" in fundamentals.columns:
            pe = fundamentals["trailingPE"].replace([np.inf, -np.inf], np.nan)
            # Filter out negative P/E (losses)
            pe = pe.where(pe > 0, np.nan)
            pe = self.winsorize(pe, 0.01, 0.99)
            scores["earnings_pe"] = self.percentile_rank(pe, ascending=False)
        else:
            scores["earnings_pe"] = 0.5
        
        return scores
    
    def get_composite_score(self, scores: pd.DataFrame) -> pd.Series:
        """Compute weighted composite value score.
        
        Args:
            scores: DataFrame from compute()
            
        Returns:
            Series with tickers as index, composite value score as values
        """
        weights = {f.name: f.weight for f in self.category.factors}
        return self.combine_subfactors(scores, weights)
