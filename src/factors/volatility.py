"""Volatility Factors - Measure risk characteristics and exploit low-vol anomaly.

Factors:
1. Realized Volatility (60d) - Standard deviation of daily returns
2. Idiosyncratic Volatility - Residual volatility after market exposure
3. Beta - Systematic market risk
4. Downside Beta - Beta using only negative market days
5. Max Drawdown (6m) - Peak-to-trough decline measure

Note: For the low-volatility anomaly, lower volatility stocks tend to outperform.
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


class VolatilityFactors(FactorCalculator):
    """Calculator for volatility factors."""
    
    DAYS_60 = 60
    DAYS_6M = 126
    DAYS_1Y = 252
    
    def __init__(self):
        super().__init__()
        self.category = FactorCategory(
            name="volatility",
            description="Measure risk characteristics and exploit low-vol anomaly",
            default_weight=0.10,  # Base weight, adjusted by regime
        )
        self._register_factors()
    
    def _register_factors(self) -> None:
        """Register all volatility factors."""
        self.category.factors = [
            Factor(
                name="realized_vol",
                description="60-day realized volatility (lower is better)",
                direction=FactorDirection.NEGATIVE,
                weight=0.25,
            ),
            Factor(
                name="idio_vol",
                description="Idiosyncratic volatility (lower is better)",
                direction=FactorDirection.NEGATIVE,
                weight=0.20,
            ),
            Factor(
                name="beta",
                description="Market beta (lower preferred for low-vol strategy)",
                direction=FactorDirection.NEGATIVE,
                weight=0.20,
            ),
            Factor(
                name="downside_beta",
                description="Downside beta (lower is better)",
                direction=FactorDirection.NEGATIVE,
                weight=0.20,
            ),
            Factor(
                name="max_drawdown",
                description="6-month max drawdown (less negative is better)",
                direction=FactorDirection.POSITIVE,  # Less negative = higher score
                weight=0.15,
            ),
        ]
    
    def compute(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        market_data: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Compute all volatility factors.
        
        Args:
            prices: Price DataFrame (dates x tickers)
            fundamentals: Fundamentals DataFrame (not heavily used)
            market_data: Market benchmark prices (e.g., SPY) for beta calculation
                        If None, will attempt to use SPY from prices or skip beta
            
        Returns:
            DataFrame with tickers as index, volatility factor scores as columns
        """
        tickers = list(prices.columns)
        scores = pd.DataFrame(index=tickers)
        
        # Compute daily returns
        returns = prices.pct_change().dropna(how='all')
        
        if returns.empty or len(returns) < 20:
            # Not enough data for volatility calculations
            for factor in self.category.factors:
                scores[factor.name] = 0.5
            return scores
        
        # Get market returns for beta calculations
        market_returns = self._get_market_returns(returns, market_data)
        
        # 1. Realized Volatility (60-day)
        if len(returns) >= self.DAYS_60:
            recent_returns = returns.iloc[-self.DAYS_60:]
            realized_vol = recent_returns.std() * np.sqrt(252)  # Annualized
            realized_vol = self.winsorize(realized_vol, 0.01, 0.99)
            # Lower volatility is better
            scores["realized_vol"] = self.percentile_rank(realized_vol, ascending=False)
        else:
            scores["realized_vol"] = 0.5
        
        # 2. Idiosyncratic Volatility
        if market_returns is not None and len(returns) >= self.DAYS_60:
            idio_vol = self._compute_idiosyncratic_vol(returns.iloc[-self.DAYS_60:], market_returns)
            idio_vol = self.winsorize(idio_vol, 0.01, 0.99)
            scores["idio_vol"] = self.percentile_rank(idio_vol, ascending=False)
        else:
            scores["idio_vol"] = 0.5
        
        # 3. Market Beta
        if market_returns is not None and len(returns) >= self.DAYS_1Y:
            beta = self._compute_beta(returns.iloc[-self.DAYS_1Y:], market_returns)
            beta = self.winsorize(beta, 0.01, 0.99)
            # Lower beta preferred for low-vol factor
            scores["beta"] = self.percentile_rank(beta, ascending=False)
        else:
            scores["beta"] = 0.5
        
        # 4. Downside Beta
        if market_returns is not None and len(returns) >= self.DAYS_1Y:
            downside_beta = self._compute_downside_beta(returns.iloc[-self.DAYS_1Y:], market_returns)
            downside_beta = self.winsorize(downside_beta, 0.01, 0.99)
            scores["downside_beta"] = self.percentile_rank(downside_beta, ascending=False)
        else:
            scores["downside_beta"] = 0.5
        
        # 5. Max Drawdown (6-month)
        if len(prices) >= self.DAYS_6M:
            max_dd = self._compute_max_drawdown(prices.iloc[-self.DAYS_6M:])
            max_dd = self.winsorize(max_dd, 0.01, 0.99)
            # Less negative (closer to 0) is better
            scores["max_drawdown"] = self.percentile_rank(max_dd, ascending=True)
        else:
            scores["max_drawdown"] = 0.5
        
        return scores
    
    def _get_market_returns(
        self,
        returns: pd.DataFrame,
        market_data: Optional[pd.DataFrame],
    ) -> Optional[pd.Series]:
        """Get market benchmark returns for beta calculation."""
        # Try to use provided market data
        if market_data is not None and not market_data.empty:
            if "SPY" in market_data.columns:
                return market_data["SPY"].pct_change().dropna()
            return market_data.iloc[:, 0].pct_change().dropna()
        
        # Try to find SPY in the price data
        if "SPY" in returns.columns:
            return returns["SPY"]
        
        # Use equal-weighted average of all stocks as market proxy
        return returns.mean(axis=1)
    
    def _compute_idiosyncratic_vol(
        self,
        returns: pd.DataFrame,
        market_returns: pd.Series,
    ) -> pd.Series:
        """Compute idiosyncratic (residual) volatility after removing market exposure."""
        idio_vol = pd.Series(index=returns.columns, dtype=float)
        
        # Align market returns with stock returns
        market_aligned = market_returns.reindex(returns.index).fillna(0)
        
        for ticker in returns.columns:
            stock_ret = returns[ticker].dropna()
            mkt_ret = market_aligned.loc[stock_ret.index]
            
            if len(stock_ret) < 20:
                idio_vol[ticker] = np.nan
                continue
            
            # Run regression: stock_ret = alpha + beta * market_ret + residual
            try:
                cov = np.cov(stock_ret, mkt_ret)
                if cov[1, 1] > 0:
                    beta = cov[0, 1] / cov[1, 1]
                    residuals = stock_ret - beta * mkt_ret
                    idio_vol[ticker] = residuals.std() * np.sqrt(252)
                else:
                    idio_vol[ticker] = stock_ret.std() * np.sqrt(252)
            except Exception:
                idio_vol[ticker] = np.nan
        
        return idio_vol
    
    def _compute_beta(
        self,
        returns: pd.DataFrame,
        market_returns: pd.Series,
    ) -> pd.Series:
        """Compute market beta for each stock."""
        beta = pd.Series(index=returns.columns, dtype=float)
        
        market_aligned = market_returns.reindex(returns.index).fillna(0)
        market_var = market_aligned.var()
        
        if market_var == 0:
            return pd.Series(1.0, index=returns.columns)
        
        for ticker in returns.columns:
            stock_ret = returns[ticker].dropna()
            mkt_ret = market_aligned.loc[stock_ret.index]
            
            if len(stock_ret) < 20:
                beta[ticker] = np.nan
                continue
            
            try:
                cov = np.cov(stock_ret, mkt_ret)[0, 1]
                var = mkt_ret.var()
                beta[ticker] = cov / var if var > 0 else 1.0
            except Exception:
                beta[ticker] = np.nan
        
        return beta
    
    def _compute_downside_beta(
        self,
        returns: pd.DataFrame,
        market_returns: pd.Series,
    ) -> pd.Series:
        """Compute downside beta using only negative market return days."""
        downside_beta = pd.Series(index=returns.columns, dtype=float)
        
        market_aligned = market_returns.reindex(returns.index).fillna(0)
        
        # Filter to only down market days
        down_days = market_aligned < 0
        
        if down_days.sum() < 20:
            return pd.Series(1.0, index=returns.columns)
        
        market_down = market_aligned[down_days]
        market_down_var = market_down.var()
        
        if market_down_var == 0:
            return pd.Series(1.0, index=returns.columns)
        
        for ticker in returns.columns:
            stock_ret = returns[ticker]
            stock_down = stock_ret.loc[down_days]
            
            valid = stock_down.notna() & market_down.notna()
            if valid.sum() < 10:
                downside_beta[ticker] = np.nan
                continue
            
            try:
                cov = np.cov(stock_down[valid], market_down[valid])[0, 1]
                downside_beta[ticker] = cov / market_down_var
            except Exception:
                downside_beta[ticker] = np.nan
        
        return downside_beta
    
    def _compute_max_drawdown(self, prices: pd.DataFrame) -> pd.Series:
        """Compute maximum drawdown for each stock over the period."""
        max_dd = pd.Series(index=prices.columns, dtype=float)
        
        for ticker in prices.columns:
            price_series = prices[ticker].dropna()
            if len(price_series) < 5:
                max_dd[ticker] = np.nan
                continue
            
            # Compute running maximum
            running_max = price_series.expanding().max()
            drawdown = (price_series / running_max) - 1
            max_dd[ticker] = drawdown.min()  # Most negative value
        
        return max_dd
    
    def get_composite_score(self, scores: pd.DataFrame) -> pd.Series:
        """Compute weighted composite volatility score."""
        weights = {f.name: f.weight for f in self.category.factors}
        return self.combine_subfactors(scores, weights)
