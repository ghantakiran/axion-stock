"""Market regime detection for adaptive factor weighting."""

import logging
from datetime import date, timedelta
from enum import Enum
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classifications."""

    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    CRISIS = "crisis"


# Regime characteristics for documentation
REGIME_CHARACTERISTICS = {
    MarketRegime.BULL: {
        "description": "Rising prices, low VIX, positive breadth",
        "factor_emphasis": ["momentum", "growth"],
    },
    MarketRegime.BEAR: {
        "description": "Falling prices, high VIX, negative breadth",
        "factor_emphasis": ["quality", "volatility", "value"],
    },
    MarketRegime.SIDEWAYS: {
        "description": "Range-bound, moderate VIX",
        "factor_emphasis": ["value", "quality"],
    },
    MarketRegime.CRISIS: {
        "description": "VIX >35, correlation spike, rapid decline",
        "factor_emphasis": ["volatility", "quality"],
    },
}


class RegimeDetector:
    """Detect current market regime using rule-based classification.

    Uses multiple signals:
    - VIX level and 20-day change
    - S&P 500 200-day trend direction
    - Yield curve slope (10Y - 2Y)
    - Market breadth (% above 200 SMA)

    Future enhancement: Replace rule-based with Hidden Markov Model (HMM).
    """

    # Thresholds for regime classification
    VIX_CRISIS_THRESHOLD = 35.0
    VIX_HIGH_THRESHOLD = 25.0
    VIX_LOW_THRESHOLD = 15.0

    def __init__(self):
        self._data_service = None
        self._cache = {}
        self._cache_date = None

    @property
    def data_service(self):
        """Lazy load data service to avoid circular imports."""
        if self._data_service is None:
            try:
                from src.services.sync_adapter import sync_data_service

                self._data_service = sync_data_service
            except ImportError:
                logger.warning("DataService not available for regime detection")
        return self._data_service

    def classify(
        self,
        as_of_date: Optional[date] = None,
        sp500_prices: Optional[pd.Series] = None,
        vix_level: Optional[float] = None,
        yield_spread: Optional[float] = None,
    ) -> MarketRegime:
        """Classify current market regime.

        Args:
            as_of_date: Date for regime classification (default: today)
            sp500_prices: Optional S&P 500 price series (for trend calculation)
            vix_level: Optional VIX level (fetched from FRED if not provided)
            yield_spread: Optional 10Y-2Y spread (fetched from FRED if not provided)

        Returns:
            MarketRegime enum value
        """
        if as_of_date is None:
            as_of_date = date.today()

        # Check cache
        if self._cache_date == as_of_date and "regime" in self._cache:
            return self._cache["regime"]

        # Gather features
        features = self._gather_features(
            as_of_date, sp500_prices, vix_level, yield_spread
        )

        # Rule-based classification
        regime = self._classify_from_features(features)

        # Cache result
        self._cache_date = as_of_date
        self._cache["regime"] = regime
        self._cache["features"] = features

        logger.info(
            "Regime classification: %s (VIX=%.1f, trend=%s, spread=%.2f)",
            regime.value,
            features.get("vix_level", 0),
            "up" if features.get("sp500_trend_up", False) else "down",
            features.get("yield_spread", 0),
        )

        return regime

    def _gather_features(
        self,
        as_of_date: date,
        sp500_prices: Optional[pd.Series],
        vix_level: Optional[float],
        yield_spread: Optional[float],
    ) -> dict:
        """Gather all features needed for regime classification."""
        features = {
            "vix_level": vix_level,
            "vix_change_20d": None,
            "sp500_trend_up": None,
            "yield_spread": yield_spread,
            "breadth": None,
        }

        # Fetch VIX if not provided
        if vix_level is None and self.data_service:
            try:
                vix_series = self.data_service.get_economic_indicator(
                    "VIXCLS",
                    start=(as_of_date - timedelta(days=60)).isoformat(),
                )
                if not vix_series.empty:
                    features["vix_level"] = vix_series.iloc[-1]
                    if len(vix_series) >= 20:
                        features["vix_change_20d"] = (
                            vix_series.iloc[-1] - vix_series.iloc[-20]
                        )
            except Exception as e:
                logger.debug("Failed to fetch VIX: %s", e)

        # Fetch yield spread if not provided
        if yield_spread is None and self.data_service:
            try:
                spread_series = self.data_service.get_economic_indicator(
                    "T10Y2Y",
                    start=(as_of_date - timedelta(days=30)).isoformat(),
                )
                if not spread_series.empty:
                    features["yield_spread"] = spread_series.iloc[-1]
            except Exception as e:
                logger.debug("Failed to fetch yield spread: %s", e)

        # Calculate S&P 500 trend
        if sp500_prices is not None and len(sp500_prices) >= 200:
            sma_200 = sp500_prices.iloc[-200:].mean()
            current = sp500_prices.iloc[-1]
            features["sp500_trend_up"] = current > sma_200

        # Default values for missing features
        if features["vix_level"] is None:
            features["vix_level"] = 20.0  # Neutral default

        if features["yield_spread"] is None:
            features["yield_spread"] = 0.5  # Slightly positive default

        if features["sp500_trend_up"] is None:
            features["sp500_trend_up"] = True  # Default bullish

        return features

    def _classify_from_features(self, features: dict) -> MarketRegime:
        """Apply rule-based classification logic."""
        vix = features.get("vix_level", 20.0)
        trend_up = features.get("sp500_trend_up", True)
        yield_spread = features.get("yield_spread", 0.5)
        vix_change = features.get("vix_change_20d", 0)

        # Crisis: VIX above crisis threshold
        if vix >= self.VIX_CRISIS_THRESHOLD:
            return MarketRegime.CRISIS

        # Crisis: VIX spiking rapidly (>50% increase in 20 days)
        if vix_change is not None and vix_change > vix * 0.5:
            return MarketRegime.CRISIS

        # Bear: High VIX + downtrend
        if vix >= self.VIX_HIGH_THRESHOLD and not trend_up:
            return MarketRegime.BEAR

        # Bear: Inverted yield curve + downtrend
        if yield_spread < -0.2 and not trend_up:
            return MarketRegime.BEAR

        # Bull: Low VIX + uptrend
        if vix <= self.VIX_LOW_THRESHOLD and trend_up:
            return MarketRegime.BULL

        # Bull: Uptrend + positive yield curve
        if trend_up and yield_spread > 0.5:
            return MarketRegime.BULL

        # Sideways: Everything else
        return MarketRegime.SIDEWAYS

    def get_regime_info(self, regime: MarketRegime) -> dict:
        """Get characteristics and factor emphasis for a regime."""
        return REGIME_CHARACTERISTICS.get(regime, {})

    def get_last_features(self) -> dict:
        """Get the features from the last classification."""
        return self._cache.get("features", {})
