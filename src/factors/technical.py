"""Technical Factors - Price-based signals for timing and mean reversion.

Factors:
1. RSI (14-day) - Relative Strength Index for overbought/oversold
2. MACD Signal - Trend strength and direction
3. Volume Trend - Volume breakout indicator
4. Price vs 200 SMA - Long-term trend position
5. Price vs 50 SMA - Medium-term trend position
6. Bollinger Band %B - Mean reversion indicator
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


class TechnicalFactors(FactorCalculator):
    """Calculator for technical factors."""
    
    def __init__(self):
        super().__init__()
        self.category = FactorCategory(
            name="technical",
            description="Price-based signals for timing and mean reversion",
            default_weight=0.05,  # Base weight, adjusted by regime
        )
        self._register_factors()
    
    def _register_factors(self) -> None:
        """Register all technical factors."""
        self.category.factors = [
            Factor(
                name="rsi",
                description="14-day RSI (mid-range preferred)",
                direction=FactorDirection.POSITIVE,  # Handled specially
                weight=0.15,
            ),
            Factor(
                name="macd_signal",
                description="MACD signal line crossover",
                direction=FactorDirection.POSITIVE,
                weight=0.20,
            ),
            Factor(
                name="volume_trend",
                description="20d/60d volume ratio (breakout indicator)",
                direction=FactorDirection.POSITIVE,
                weight=0.15,
            ),
            Factor(
                name="price_vs_200sma",
                description="Price relative to 200-day SMA",
                direction=FactorDirection.POSITIVE,
                weight=0.20,
            ),
            Factor(
                name="price_vs_50sma",
                description="Price relative to 50-day SMA",
                direction=FactorDirection.POSITIVE,
                weight=0.15,
            ),
            Factor(
                name="bollinger_pct_b",
                description="Bollinger Band %B (mid-range preferred)",
                direction=FactorDirection.POSITIVE,  # Handled specially
                weight=0.15,
            ),
        ]
    
    def compute(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        market_data: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Compute all technical factors.
        
        Args:
            prices: Price DataFrame (dates x tickers)
            fundamentals: Not used for technical factors
            market_data: Not used for technical factors
            
        Returns:
            DataFrame with tickers as index, technical factor scores as columns
        """
        tickers = list(prices.columns)
        scores = pd.DataFrame(index=tickers)
        
        if prices.empty or len(prices) < 20:
            for factor in self.category.factors:
                scores[factor.name] = 0.5
            return scores
        
        # 1. RSI (14-day)
        rsi = self._compute_rsi(prices, period=14)
        # For RSI, mid-range (40-60) is neutral, we prefer stocks not oversold
        # Transform: higher RSI (up to 70) is better, but penalize extremes
        rsi_score = self._rsi_to_score(rsi)
        scores["rsi"] = self.percentile_rank(rsi_score, ascending=True)
        
        # 2. MACD Signal
        macd_signal = self._compute_macd_signal(prices)
        macd_signal = self.winsorize(macd_signal, 0.01, 0.99)
        scores["macd_signal"] = self.percentile_rank(macd_signal, ascending=True)
        
        # 3. Volume Trend (requires volume data, use price-based proxy)
        volume_trend = self._compute_volume_proxy(prices)
        volume_trend = self.winsorize(volume_trend, 0.01, 0.99)
        scores["volume_trend"] = self.percentile_rank(volume_trend, ascending=True)
        
        # 4. Price vs 200 SMA
        if len(prices) >= 200:
            sma_200 = prices.rolling(window=200).mean().iloc[-1]
            price_vs_200 = prices.iloc[-1] / sma_200
            price_vs_200 = price_vs_200.replace([np.inf, -np.inf], np.nan)
            price_vs_200 = self.winsorize(price_vs_200, 0.01, 0.99)
            scores["price_vs_200sma"] = self.percentile_rank(price_vs_200, ascending=True)
        else:
            scores["price_vs_200sma"] = 0.5
        
        # 5. Price vs 50 SMA
        if len(prices) >= 50:
            sma_50 = prices.rolling(window=50).mean().iloc[-1]
            price_vs_50 = prices.iloc[-1] / sma_50
            price_vs_50 = price_vs_50.replace([np.inf, -np.inf], np.nan)
            price_vs_50 = self.winsorize(price_vs_50, 0.01, 0.99)
            scores["price_vs_50sma"] = self.percentile_rank(price_vs_50, ascending=True)
        else:
            scores["price_vs_50sma"] = 0.5
        
        # 6. Bollinger Band %B
        boll_pct_b = self._compute_bollinger_pct_b(prices, period=20)
        # Mid-range (0.3-0.7) is neutral, prefer stocks near middle
        boll_score = self._bollinger_to_score(boll_pct_b)
        scores["bollinger_pct_b"] = self.percentile_rank(boll_score, ascending=True)
        
        return scores
    
    def _compute_rsi(self, prices: pd.DataFrame, period: int = 14) -> pd.Series:
        """Compute RSI for each stock."""
        rsi = pd.Series(index=prices.columns, dtype=float)
        
        for ticker in prices.columns:
            price_series = prices[ticker].dropna()
            if len(price_series) < period + 1:
                rsi[ticker] = 50.0
                continue
            
            # Calculate price changes
            delta = price_series.diff()
            
            # Separate gains and losses
            gains = delta.clip(lower=0)
            losses = (-delta).clip(lower=0)
            
            # Calculate average gains and losses
            avg_gain = gains.rolling(window=period).mean().iloc[-1]
            avg_loss = losses.rolling(window=period).mean().iloc[-1]
            
            if avg_loss == 0:
                rsi[ticker] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[ticker] = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _rsi_to_score(self, rsi: pd.Series) -> pd.Series:
        """Convert RSI to a score that prefers mid-range values.
        
        Scoring:
        - RSI 30-70: Good range, higher score
        - RSI < 30: Oversold, might bounce but risky
        - RSI > 70: Overbought, might pullback
        """
        score = pd.Series(index=rsi.index, dtype=float)
        
        for ticker in rsi.index:
            r = rsi[ticker]
            if pd.isna(r):
                score[ticker] = 0.5
            elif 40 <= r <= 60:
                # Neutral zone - moderate score
                score[ticker] = 0.5
            elif 30 <= r < 40:
                # Approaching oversold - potential bounce
                score[ticker] = 0.6
            elif 60 < r <= 70:
                # Strong momentum but not extreme
                score[ticker] = 0.7
            elif r < 30:
                # Oversold - might bounce or continue falling
                score[ticker] = 0.4
            else:  # r > 70
                # Overbought - momentum but risk of pullback
                score[ticker] = 0.6
        
        return score
    
    def _compute_macd_signal(self, prices: pd.DataFrame) -> pd.Series:
        """Compute MACD signal line crossover strength."""
        macd_signal = pd.Series(index=prices.columns, dtype=float)
        
        for ticker in prices.columns:
            price_series = prices[ticker].dropna()
            if len(price_series) < 35:
                macd_signal[ticker] = 0.0
                continue
            
            # MACD: 12-day EMA - 26-day EMA
            ema_12 = price_series.ewm(span=12, adjust=False).mean()
            ema_26 = price_series.ewm(span=26, adjust=False).mean()
            macd_line = ema_12 - ema_26
            
            # Signal line: 9-day EMA of MACD
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            
            # MACD histogram (positive = bullish)
            histogram = macd_line - signal_line
            
            # Normalize by price
            current_price = price_series.iloc[-1]
            if current_price > 0:
                macd_signal[ticker] = histogram.iloc[-1] / current_price * 100
            else:
                macd_signal[ticker] = 0.0
        
        return macd_signal
    
    def _compute_volume_proxy(self, prices: pd.DataFrame) -> pd.Series:
        """Compute volume trend proxy using price volatility changes.
        
        Since we don't always have volume data, we use price volatility
        as a proxy - higher recent volatility often correlates with volume.
        """
        volume_proxy = pd.Series(index=prices.columns, dtype=float)
        
        for ticker in prices.columns:
            price_series = prices[ticker].dropna()
            if len(price_series) < 60:
                volume_proxy[ticker] = 1.0
                continue
            
            returns = price_series.pct_change()
            
            # Recent (20d) vs longer-term (60d) volatility
            vol_20 = returns.iloc[-20:].std()
            vol_60 = returns.iloc[-60:].std()
            
            if vol_60 > 0:
                volume_proxy[ticker] = vol_20 / vol_60
            else:
                volume_proxy[ticker] = 1.0
        
        return volume_proxy
    
    def _compute_bollinger_pct_b(self, prices: pd.DataFrame, period: int = 20) -> pd.Series:
        """Compute Bollinger Band %B for each stock.
        
        %B = (Price - Lower Band) / (Upper Band - Lower Band)
        0 = at lower band, 1 = at upper band, 0.5 = at middle band
        """
        pct_b = pd.Series(index=prices.columns, dtype=float)
        
        for ticker in prices.columns:
            price_series = prices[ticker].dropna()
            if len(price_series) < period:
                pct_b[ticker] = 0.5
                continue
            
            # Middle band (SMA)
            middle = price_series.rolling(window=period).mean()
            
            # Standard deviation
            std = price_series.rolling(window=period).std()
            
            # Upper and lower bands (2 standard deviations)
            upper = middle + 2 * std
            lower = middle - 2 * std
            
            # Current values
            current_price = price_series.iloc[-1]
            current_upper = upper.iloc[-1]
            current_lower = lower.iloc[-1]
            
            # %B calculation
            band_width = current_upper - current_lower
            if band_width > 0:
                pct_b[ticker] = (current_price - current_lower) / band_width
            else:
                pct_b[ticker] = 0.5
        
        return pct_b
    
    def _bollinger_to_score(self, pct_b: pd.Series) -> pd.Series:
        """Convert Bollinger %B to a score.
        
        Scoring logic:
        - 0.3-0.7: Neutral zone, moderate score
        - < 0.2: Very oversold, potential bounce
        - > 0.8: Very overbought, potential pullback
        """
        score = pd.Series(index=pct_b.index, dtype=float)
        
        for ticker in pct_b.index:
            b = pct_b[ticker]
            if pd.isna(b):
                score[ticker] = 0.5
            elif 0.3 <= b <= 0.7:
                # Mid-range - stable, slightly bullish bias toward upper
                score[ticker] = 0.5 + (b - 0.5) * 0.2
            elif 0.2 <= b < 0.3:
                # Near lower band - potential bounce
                score[ticker] = 0.55
            elif 0.7 < b <= 0.8:
                # Near upper band - momentum
                score[ticker] = 0.6
            elif b < 0.2:
                # Very oversold
                score[ticker] = 0.4
            else:  # b > 0.8
                # Very overbought
                score[ticker] = 0.45
        
        return score
    
    def get_composite_score(self, scores: pd.DataFrame) -> pd.Series:
        """Compute weighted composite technical score."""
        weights = {f.name: f.weight for f in self.category.factors}
        return self.combine_subfactors(scores, weights)
