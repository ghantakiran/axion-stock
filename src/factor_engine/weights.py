"""Adaptive weight management for factor scoring."""

import logging
from typing import Optional

import pandas as pd

from src.factor_engine.regime import MarketRegime, RegimeDetector

logger = logging.getLogger(__name__)


# Regime-specific factor weights (from PRD-02)
# All weights sum to 1.0 within each regime
REGIME_WEIGHTS = {
    MarketRegime.BULL: {
        "value": 0.10,
        "momentum": 0.35,
        "quality": 0.15,
        "growth": 0.25,
        "volatility": 0.05,
        "technical": 0.10,
    },
    MarketRegime.BEAR: {
        "value": 0.25,
        "momentum": 0.05,
        "quality": 0.35,
        "growth": 0.05,
        "volatility": 0.25,
        "technical": 0.05,
    },
    MarketRegime.SIDEWAYS: {
        "value": 0.25,
        "momentum": 0.15,
        "quality": 0.25,
        "growth": 0.10,
        "volatility": 0.15,
        "technical": 0.10,
    },
    MarketRegime.CRISIS: {
        "value": 0.05,
        "momentum": 0.00,
        "quality": 0.40,
        "growth": 0.00,
        "volatility": 0.50,
        "technical": 0.05,
    },
}

# Static v1 weights (for backward compatibility)
STATIC_WEIGHTS_V1 = {
    "value": 0.25,
    "momentum": 0.30,
    "quality": 0.25,
    "growth": 0.20,
}

# Static v2 weights (6 factors, no regime adjustment)
STATIC_WEIGHTS_V2 = {
    "value": 0.20,
    "momentum": 0.25,
    "quality": 0.20,
    "growth": 0.15,
    "volatility": 0.10,
    "technical": 0.10,
}

# Constraints for factor weights
MIN_WEIGHT = 0.0
MAX_WEIGHT = 0.50


class AdaptiveWeightManager:
    """Manages factor weights with regime adaptation and momentum overlay.

    Features:
    1. Regime-based weight selection from REGIME_WEIGHTS
    2. Factor momentum overlay (tilt toward recently-performing factors)
    3. Weight constraints (no factor > 50% or < 0%)
    4. Smooth weight transitions via exponential weighting
    """

    def __init__(
        self,
        regime_detector: Optional[RegimeDetector] = None,
        enable_momentum_overlay: bool = True,
        momentum_half_life: int = 20,
    ):
        """Initialize weight manager.

        Args:
            regime_detector: RegimeDetector instance (created if None)
            enable_momentum_overlay: Whether to tilt weights based on factor performance
            momentum_half_life: Half-life in days for momentum EMA
        """
        self.regime_detector = regime_detector or RegimeDetector()
        self.enable_momentum_overlay = enable_momentum_overlay
        self.momentum_half_life = momentum_half_life

        # Cache for factor returns (for momentum overlay)
        self._factor_returns_cache: Optional[pd.DataFrame] = None

    def get_weights(
        self,
        regime: Optional[MarketRegime] = None,
        factor_returns: Optional[pd.DataFrame] = None,
        use_adaptive: bool = True,
    ) -> dict[str, float]:
        """Get current factor weights.

        Args:
            regime: Market regime (detected if not provided)
            factor_returns: Historical factor category returns (for momentum overlay)
            use_adaptive: Whether to use regime-adaptive weights

        Returns:
            Dict mapping factor names to weights (sum to 1.0)
        """
        if not use_adaptive:
            return STATIC_WEIGHTS_V2.copy()

        # Get regime-based weights
        if regime is None:
            regime = self.regime_detector.classify()

        weights = REGIME_WEIGHTS.get(regime, STATIC_WEIGHTS_V2).copy()

        # Apply factor momentum overlay
        if self.enable_momentum_overlay and factor_returns is not None:
            weights = self._apply_momentum_overlay(weights, factor_returns)

        # Apply constraints
        weights = self._apply_constraints(weights)

        # Normalize to sum to 1.0
        weights = self._normalize(weights)

        return weights

    def get_static_weights_v1(self) -> dict[str, float]:
        """Get v1-compatible static weights (4 factors)."""
        return STATIC_WEIGHTS_V1.copy()

    def get_static_weights_v2(self) -> dict[str, float]:
        """Get v2 static weights (6 factors, no regime adjustment)."""
        return STATIC_WEIGHTS_V2.copy()

    def _apply_momentum_overlay(
        self,
        base_weights: dict[str, float],
        factor_returns: pd.DataFrame,
    ) -> dict[str, float]:
        """Tilt weights toward recently-performing factors.

        Uses exponentially-weighted trailing 3-month factor returns
        to adjust weights up/down by up to 20%.
        """
        if factor_returns.empty or len(factor_returns) < 21:
            return base_weights

        weights = base_weights.copy()

        # Calculate trailing 3-month returns with EMA weighting
        lookback = min(63, len(factor_returns))  # ~3 months
        recent_returns = factor_returns.iloc[-lookback:]

        # EMA weights (more recent = higher weight)
        alpha = 2 / (self.momentum_half_life + 1)
        ema_weights = pd.Series(
            [(1 - alpha) ** i for i in range(lookback - 1, -1, -1)]
        )
        ema_weights = ema_weights / ema_weights.sum()

        # Calculate weighted factor returns
        factor_momentum = {}
        for col in recent_returns.columns:
            if col in weights:
                returns = recent_returns[col].values
                weighted_return = (returns * ema_weights.values).sum()
                factor_momentum[col] = weighted_return

        if not factor_momentum:
            return weights

        # Rank factors by recent performance
        momentum_series = pd.Series(factor_momentum)
        momentum_rank = momentum_series.rank(pct=True)

        # Adjust weights: top performers get up to +20%, bottom get -20%
        max_adjustment = 0.20
        for factor in weights:
            if factor in momentum_rank:
                # Map rank (0-1) to adjustment (-0.2 to +0.2)
                rank = momentum_rank[factor]
                adjustment = (rank - 0.5) * 2 * max_adjustment
                weights[factor] = weights[factor] * (1 + adjustment)

        return weights

    def _apply_constraints(self, weights: dict[str, float]) -> dict[str, float]:
        """Apply min/max weight constraints."""
        constrained = {}
        for factor, weight in weights.items():
            constrained[factor] = max(MIN_WEIGHT, min(MAX_WEIGHT, weight))
        return constrained

    def _normalize(self, weights: dict[str, float]) -> dict[str, float]:
        """Normalize weights to sum to 1.0."""
        total = sum(weights.values())
        if total == 0:
            # Equal weight fallback
            n = len(weights)
            return {k: 1.0 / n for k in weights}
        return {k: v / total for k, v in weights.items()}

    def get_regime_weights_table(self) -> pd.DataFrame:
        """Get a table of all regime weights for display."""
        data = {}
        for regime in MarketRegime:
            weights = REGIME_WEIGHTS.get(regime, {})
            data[regime.value] = weights
        return pd.DataFrame(data)
