"""Adaptive Factor Weights - Regime-based weight allocation.

Different market regimes favor different factors:
- Bull: Momentum and growth work well in uptrends
- Bear: Quality and low-volatility provide downside protection
- Sideways: Value and dividend yield outperform
- Crisis: Minimize exposure, favor lowest volatility

Also implements factor momentum overlay for dynamic tilting.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.regime.detector import MarketRegime


# Regime-specific factor weights (must sum to 1.0 for each regime)
REGIME_WEIGHTS: dict[str, dict[str, float]] = {
    "bull": {
        "value": 0.10,
        "momentum": 0.35,
        "quality": 0.15,
        "growth": 0.25,
        "volatility": 0.05,
        "technical": 0.10,
    },
    "bear": {
        "value": 0.25,
        "momentum": 0.05,
        "quality": 0.35,
        "growth": 0.05,
        "volatility": 0.25,
        "technical": 0.05,
    },
    "sideways": {
        "value": 0.25,
        "momentum": 0.15,
        "quality": 0.25,
        "growth": 0.10,
        "volatility": 0.15,
        "technical": 0.10,
    },
    "crisis": {
        "value": 0.05,
        "momentum": 0.00,
        "quality": 0.40,
        "growth": 0.00,
        "volatility": 0.50,
        "technical": 0.05,
    },
}

# Static weights for backward compatibility (v1 style)
STATIC_WEIGHTS: dict[str, float] = {
    "value": 0.20,
    "momentum": 0.25,
    "quality": 0.25,
    "growth": 0.15,
    "volatility": 0.10,
    "technical": 0.05,
}


@dataclass
class FactorMomentum:
    """Track factor performance for momentum overlay."""
    factor_returns: dict[str, pd.Series] = field(default_factory=dict)
    lookback_days: int = 63  # ~3 months
    half_life: int = 20  # Exponential decay half-life
    
    def update(self, factor_name: str, returns: pd.Series) -> None:
        """Update factor return history."""
        self.factor_returns[factor_name] = returns
    
    def get_momentum_score(self, factor_name: str) -> float:
        """Get momentum score for a factor (0-1 scale)."""
        if factor_name not in self.factor_returns:
            return 0.5
        
        returns = self.factor_returns[factor_name]
        if len(returns) < 20:
            return 0.5
        
        # Use lookback period
        recent = returns.iloc[-self.lookback_days:]
        
        # Exponentially weighted cumulative return
        weights = np.exp(-np.arange(len(recent))[::-1] / self.half_life)
        weights /= weights.sum()
        
        weighted_return = (recent * weights).sum()
        
        # Convert to 0-1 score (assuming -20% to +20% range)
        score = (weighted_return + 0.20) / 0.40
        return np.clip(score, 0.0, 1.0)


class AdaptiveWeights:
    """Compute adaptive factor weights based on regime and factor momentum.
    
    Weight calculation:
    1. Start with regime-based weights
    2. Apply factor momentum overlay (tilt toward recent performers)
    3. Ensure constraints (no factor > 50% or < 0%)
    """
    
    MIN_WEIGHT = 0.00
    MAX_WEIGHT = 0.50
    MOMENTUM_TILT = 0.15  # Max tilt from momentum overlay
    
    def __init__(
        self,
        use_momentum_overlay: bool = True,
        smoothing_factor: float = 0.3,
    ):
        """Initialize adaptive weights.
        
        Args:
            use_momentum_overlay: Whether to apply factor momentum tilts
            smoothing_factor: How much to smooth weight transitions (0-1)
        """
        self.use_momentum_overlay = use_momentum_overlay
        self.smoothing_factor = smoothing_factor
        self.factor_momentum = FactorMomentum()
        self._previous_weights: Optional[dict[str, float]] = None
    
    def get_weights(
        self,
        regime: MarketRegime,
        factor_returns: Optional[dict[str, pd.Series]] = None,
    ) -> dict[str, float]:
        """Get adaptive factor weights for the current regime.
        
        Args:
            regime: Current market regime
            factor_returns: Optional dict of factor return series for momentum
            
        Returns:
            Dict mapping factor names to weights (sum to 1.0)
        """
        # Get base regime weights
        base_weights = REGIME_WEIGHTS.get(regime.value, STATIC_WEIGHTS).copy()
        
        # Apply factor momentum overlay
        if self.use_momentum_overlay and factor_returns:
            base_weights = self._apply_momentum_overlay(base_weights, factor_returns)
        
        # Smooth transition from previous weights
        if self._previous_weights is not None:
            base_weights = self._smooth_weights(base_weights)
        
        # Enforce constraints and normalize
        base_weights = self._enforce_constraints(base_weights)
        
        # Store for next smoothing
        self._previous_weights = base_weights.copy()
        
        return base_weights
    
    def _apply_momentum_overlay(
        self,
        weights: dict[str, float],
        factor_returns: dict[str, pd.Series],
    ) -> dict[str, float]:
        """Apply factor momentum overlay to base weights.
        
        Factors with recent positive performance get tilted up,
        factors with negative performance get tilted down.
        """
        # Update factor momentum tracker
        for factor_name, returns in factor_returns.items():
            self.factor_momentum.update(factor_name, returns)
        
        # Calculate momentum scores
        momentum_scores = {}
        for factor_name in weights:
            momentum_scores[factor_name] = self.factor_momentum.get_momentum_score(factor_name)
        
        # Calculate tilts (relative to 0.5 neutral)
        tilts = {
            name: (score - 0.5) * self.MOMENTUM_TILT * 2
            for name, score in momentum_scores.items()
        }
        
        # Apply tilts
        adjusted = {}
        for name, weight in weights.items():
            tilt = tilts.get(name, 0.0)
            adjusted[name] = weight + tilt
        
        return adjusted
    
    def _smooth_weights(self, weights: dict[str, float]) -> dict[str, float]:
        """Smooth weight transitions to avoid sudden shifts."""
        smoothed = {}
        for name, weight in weights.items():
            prev = self._previous_weights.get(name, weight)
            smoothed[name] = (
                self.smoothing_factor * weight +
                (1 - self.smoothing_factor) * prev
            )
        return smoothed
    
    def _enforce_constraints(self, weights: dict[str, float]) -> dict[str, float]:
        """Enforce min/max constraints and normalize to sum to 1.0."""
        # Clip to constraints
        constrained = {
            name: np.clip(weight, self.MIN_WEIGHT, self.MAX_WEIGHT)
            for name, weight in weights.items()
        }
        
        # Normalize to sum to 1.0
        total = sum(constrained.values())
        if total > 0:
            normalized = {name: w / total for name, w in constrained.items()}
        else:
            # Fallback to equal weights
            n = len(constrained)
            normalized = {name: 1.0 / n for name in constrained}
        
        return normalized
    
    def get_static_weights(self) -> dict[str, float]:
        """Get static (non-adaptive) weights for backward compatibility."""
        return STATIC_WEIGHTS.copy()
    
    def explain_weights(
        self,
        regime: MarketRegime,
        weights: dict[str, float],
    ) -> str:
        """Generate explanation of current weight allocation."""
        base = REGIME_WEIGHTS.get(regime.value, STATIC_WEIGHTS)
        
        explanation = f"""
Factor Weights for {regime.value.upper()} Regime
{'=' * 45}

"""
        for factor in sorted(weights.keys()):
            w = weights[factor]
            base_w = base.get(factor, 0)
            diff = w - base_w
            
            bar = '█' * int(w * 20) + '░' * (20 - int(w * 20))
            diff_str = f"({diff:+.0%})" if abs(diff) > 0.01 else ""
            
            explanation += f"{factor:12s} {bar} {w:.0%} {diff_str}\n"
        
        explanation += f"\nTotal: {sum(weights.values()):.0%}"
        
        return explanation
