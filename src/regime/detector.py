"""Market Regime Detector - Classify current market conditions.

Uses multiple inputs to determine the current market regime:
- S&P 500 trend (price vs 200-day SMA)
- VIX level and changes
- Market breadth (advance/decline, % above 200 SMA)
- Yield curve slope
- Credit spreads (if available)

Regimes:
- BULL: Strong uptrend, low volatility, positive breadth
- BEAR: Downtrend, elevated volatility, negative breadth
- SIDEWAYS: Range-bound, moderate conditions
- CRISIS: Extreme volatility, correlation breakdown
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd


class MarketRegime(Enum):
    """Market regime classification."""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    CRISIS = "crisis"


@dataclass
class RegimeFeatures:
    """Features used for regime classification."""
    sp500_above_200sma: bool
    sp500_trend_strength: float  # % above/below 200 SMA
    vix_level: float
    vix_20d_change: float
    breadth_ratio: float  # Advance/decline or % above 200 SMA
    yield_curve_slope: Optional[float] = None  # 10Y - 2Y
    credit_spread: Optional[float] = None  # HY - IG spread
    momentum_1m: float = 0.0  # 1-month market return
    correlation_spike: bool = False


@dataclass
class RegimeClassification:
    """Result of regime classification."""
    regime: MarketRegime
    confidence: float  # 0-1 confidence in classification
    features: RegimeFeatures
    timestamp: datetime
    
    def __str__(self) -> str:
        return f"{self.regime.value.upper()} (confidence: {self.confidence:.0%})"


class RegimeDetector:
    """Detector for market regime classification.
    
    Uses a rule-based approach with the following logic:
    1. Crisis: VIX > 35 or extreme drawdown
    2. Bull: Above 200 SMA + positive breadth + low VIX
    3. Bear: Below 200 SMA + negative breadth + elevated VIX
    4. Sideways: Everything else (range-bound)
    """
    
    # VIX thresholds
    VIX_CRISIS = 35.0
    VIX_ELEVATED = 25.0
    VIX_LOW = 15.0
    
    # Trend thresholds
    TREND_STRONG_UP = 0.05  # 5% above 200 SMA
    TREND_STRONG_DOWN = -0.05
    
    # Breadth thresholds
    BREADTH_POSITIVE = 0.55  # >55% of stocks above their 200 SMA
    BREADTH_NEGATIVE = 0.45
    
    def __init__(self):
        self._cache: dict[str, RegimeClassification] = {}
        self._cache_ttl = timedelta(hours=1)
    
    def classify(
        self,
        market_prices: pd.DataFrame,
        vix_data: Optional[pd.Series] = None,
        universe_prices: Optional[pd.DataFrame] = None,
        as_of_date: Optional[date] = None,
    ) -> RegimeClassification:
        """Classify the current market regime.
        
        Args:
            market_prices: DataFrame with market index prices (e.g., SPY)
                          Must have at least 200 days of data
            vix_data: Optional VIX price series
            universe_prices: Optional DataFrame of universe prices for breadth
            as_of_date: Date to classify (default: latest in data)
            
        Returns:
            RegimeClassification with regime, confidence, and features
        """
        # Handle empty or insufficient data
        if market_prices.empty or len(market_prices) < 5:
            return RegimeClassification(
                regime=MarketRegime.SIDEWAYS,
                confidence=0.0,
                features=RegimeFeatures(
                    sp500_above_200sma=True,
                    sp500_trend_strength=0.0,
                    vix_level=20.0,
                    vix_20d_change=0.0,
                    breadth_ratio=0.5,
                ),
                timestamp=datetime.now(),
            )
        
        if as_of_date is None:
            as_of_date = market_prices.index[-1]
            if hasattr(as_of_date, 'date'):
                as_of_date = as_of_date.date()
        
        # Check cache
        cache_key = str(as_of_date)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if datetime.now() - cached.timestamp < self._cache_ttl:
                return cached
        
        # Compute features
        features = self._compute_features(
            market_prices, vix_data, universe_prices, as_of_date
        )
        
        # Classify based on features
        regime, confidence = self._classify_from_features(features)
        
        result = RegimeClassification(
            regime=regime,
            confidence=confidence,
            features=features,
            timestamp=datetime.now(),
        )
        
        # Cache result
        self._cache[cache_key] = result
        
        return result
    
    def _compute_features(
        self,
        market_prices: pd.DataFrame,
        vix_data: Optional[pd.Series],
        universe_prices: Optional[pd.DataFrame],
        as_of_date: date,
    ) -> RegimeFeatures:
        """Compute all features for regime classification."""
        
        # Get market series (assume SPY or first column)
        if "SPY" in market_prices.columns:
            market = market_prices["SPY"]
        else:
            market = market_prices.iloc[:, 0]
        
        # Filter to as_of_date
        market = market[market.index <= pd.Timestamp(as_of_date)]
        
        # S&P 500 trend features
        sp500_above_200sma = False
        sp500_trend_strength = 0.0
        
        if len(market) >= 200:
            sma_200 = market.rolling(window=200).mean().iloc[-1]
            current_price = market.iloc[-1]
            sp500_above_200sma = current_price > sma_200
            sp500_trend_strength = (current_price / sma_200 - 1) if sma_200 > 0 else 0.0
        
        # 1-month momentum
        momentum_1m = 0.0
        if len(market) >= 21:
            momentum_1m = (market.iloc[-1] / market.iloc[-21] - 1)
        
        # VIX features
        vix_level = 20.0  # Default neutral
        vix_20d_change = 0.0
        
        if vix_data is not None and len(vix_data) > 0:
            vix_filtered = vix_data[vix_data.index <= pd.Timestamp(as_of_date)]
            if len(vix_filtered) > 0:
                vix_level = vix_filtered.iloc[-1]
                if len(vix_filtered) >= 20:
                    vix_20d_change = vix_filtered.iloc[-1] - vix_filtered.iloc[-20]
        
        # Breadth features
        breadth_ratio = 0.5  # Default neutral
        
        if universe_prices is not None and len(universe_prices) >= 200:
            # Calculate % of stocks above their 200 SMA
            sma_200_all = universe_prices.rolling(window=200).mean().iloc[-1]
            current_all = universe_prices.iloc[-1]
            above_sma = (current_all > sma_200_all).sum()
            total = (~current_all.isna()).sum()
            if total > 0:
                breadth_ratio = above_sma / total
        
        # Correlation spike detection
        correlation_spike = False
        if universe_prices is not None and len(universe_prices) >= 60:
            returns = universe_prices.pct_change().iloc[-60:]
            if not returns.empty:
                corr_matrix = returns.corr()
                # Average pairwise correlation
                mask = np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
                avg_corr = corr_matrix.where(mask).stack().mean()
                # Correlation spike if avg > 0.6 (typically around 0.3-0.4)
                correlation_spike = avg_corr > 0.6
        
        return RegimeFeatures(
            sp500_above_200sma=sp500_above_200sma,
            sp500_trend_strength=sp500_trend_strength,
            vix_level=vix_level,
            vix_20d_change=vix_20d_change,
            breadth_ratio=breadth_ratio,
            momentum_1m=momentum_1m,
            correlation_spike=correlation_spike,
        )
    
    def _classify_from_features(
        self,
        features: RegimeFeatures,
    ) -> tuple[MarketRegime, float]:
        """Classify regime from computed features.
        
        Returns:
            Tuple of (MarketRegime, confidence)
        """
        # Crisis check (highest priority)
        if features.vix_level > self.VIX_CRISIS:
            confidence = min(1.0, (features.vix_level - self.VIX_CRISIS) / 15 + 0.7)
            return MarketRegime.CRISIS, confidence
        
        if features.correlation_spike and features.momentum_1m < -0.10:
            return MarketRegime.CRISIS, 0.75
        
        # Bull market check
        bull_signals = 0
        bull_confidence = 0.0
        
        if features.sp500_above_200sma:
            bull_signals += 1
            bull_confidence += 0.25
        
        if features.sp500_trend_strength > self.TREND_STRONG_UP:
            bull_signals += 1
            bull_confidence += 0.20
        
        if features.vix_level < self.VIX_LOW:
            bull_signals += 1
            bull_confidence += 0.15
        
        if features.breadth_ratio > self.BREADTH_POSITIVE:
            bull_signals += 1
            bull_confidence += 0.20
        
        if features.momentum_1m > 0.02:
            bull_signals += 1
            bull_confidence += 0.10
        
        # Bear market check
        bear_signals = 0
        bear_confidence = 0.0
        
        if not features.sp500_above_200sma:
            bear_signals += 1
            bear_confidence += 0.25
        
        if features.sp500_trend_strength < self.TREND_STRONG_DOWN:
            bear_signals += 1
            bear_confidence += 0.20
        
        if features.vix_level > self.VIX_ELEVATED:
            bear_signals += 1
            bear_confidence += 0.20
        
        if features.breadth_ratio < self.BREADTH_NEGATIVE:
            bear_signals += 1
            bear_confidence += 0.20
        
        if features.momentum_1m < -0.02:
            bear_signals += 1
            bear_confidence += 0.10
        
        # Classify based on signals
        if bull_signals >= 3 and bull_confidence > bear_confidence:
            return MarketRegime.BULL, min(0.95, bull_confidence)
        
        if bear_signals >= 3 and bear_confidence > bull_confidence:
            return MarketRegime.BEAR, min(0.95, bear_confidence)
        
        # Sideways (default)
        sideways_confidence = 1.0 - max(bull_confidence, bear_confidence)
        return MarketRegime.SIDEWAYS, max(0.5, sideways_confidence)
    
    def get_regime_summary(self, classification: RegimeClassification) -> str:
        """Generate a human-readable summary of the regime classification."""
        f = classification.features
        
        trend = "above" if f.sp500_above_200sma else "below"
        trend_pct = f.sp500_trend_strength * 100
        
        summary = f"""
Market Regime: {classification.regime.value.upper()}
Confidence: {classification.confidence:.0%}

Key Indicators:
- S&P 500 Trend: {trend} 200 SMA ({trend_pct:+.1f}%)
- VIX Level: {f.vix_level:.1f} (20d change: {f.vix_20d_change:+.1f})
- Market Breadth: {f.breadth_ratio:.0%} above 200 SMA
- 1-Month Return: {f.momentum_1m:.1%}
- Correlation Spike: {'Yes' if f.correlation_spike else 'No'}
"""
        return summary.strip()
