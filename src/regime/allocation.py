"""Regime-Aware Portfolio Allocator.

Provides per-regime target allocations and blended weights
using regime probabilities for smooth transitions.
"""

import logging
from typing import Optional

import numpy as np

from src.regime.config import AllocationConfig, RegimeType
from src.regime.models import RegimeAllocation

logger = logging.getLogger(__name__)

# Default regime-conditional target weights by asset class
DEFAULT_REGIME_TARGETS: dict[str, dict[str, float]] = {
    RegimeType.BULL.value: {
        "equity": 0.70,
        "bonds": 0.15,
        "commodities": 0.10,
        "cash": 0.05,
    },
    RegimeType.BEAR.value: {
        "equity": 0.30,
        "bonds": 0.40,
        "commodities": 0.10,
        "cash": 0.20,
    },
    RegimeType.SIDEWAYS.value: {
        "equity": 0.50,
        "bonds": 0.30,
        "commodities": 0.10,
        "cash": 0.10,
    },
    RegimeType.CRISIS.value: {
        "equity": 0.15,
        "bonds": 0.30,
        "commodities": 0.05,
        "cash": 0.50,
    },
}

# Historical regime return/risk estimates (annualized)
DEFAULT_REGIME_ESTIMATES: dict[str, dict[str, float]] = {
    RegimeType.BULL.value: {"return": 0.15, "risk": 0.12},
    RegimeType.BEAR.value: {"return": -0.10, "risk": 0.25},
    RegimeType.SIDEWAYS.value: {"return": 0.05, "risk": 0.15},
    RegimeType.CRISIS.value: {"return": -0.25, "risk": 0.40},
}


class RegimeAllocator:
    """Computes regime-aware portfolio allocations."""

    def __init__(
        self,
        config: Optional[AllocationConfig] = None,
        regime_targets: Optional[dict[str, dict[str, float]]] = None,
        regime_estimates: Optional[dict[str, dict[str, float]]] = None,
    ) -> None:
        self.config = config or AllocationConfig()
        self.targets = regime_targets or DEFAULT_REGIME_TARGETS
        self.estimates = regime_estimates or DEFAULT_REGIME_ESTIMATES
        self._previous_weights: Optional[dict[str, float]] = None

    def allocate(
        self,
        regime: str,
        confidence: float = 1.0,
        regime_probabilities: Optional[dict[str, float]] = None,
    ) -> RegimeAllocation:
        """Compute allocation for given regime.

        If blend_with_probabilities is True and probabilities are provided,
        blends target weights across all regimes weighted by their probability.

        Args:
            regime: Current regime label.
            confidence: Confidence in regime classification.
            regime_probabilities: Dict of {regime: probability}.

        Returns:
            RegimeAllocation.
        """
        # Direct target weights for the detected regime
        target = self.targets.get(regime, self.targets.get(RegimeType.SIDEWAYS.value, {}))
        weights = target.copy()

        # Blended weights using probabilities
        blended = weights.copy()
        if self.config.blend_with_probabilities and regime_probabilities:
            blended = self._blend_weights(regime_probabilities)

        # Apply smoothing if we have previous weights
        if self._previous_weights is not None:
            blended = self._smooth(blended)

        # Enforce constraints
        blended = self._constrain(blended)

        self._previous_weights = blended.copy()

        # Expected return/risk for current regime
        est = self.estimates.get(regime, {"return": 0.0, "risk": 0.2})

        return RegimeAllocation(
            regime=regime,
            confidence=round(confidence, 4),
            weights=weights,
            blended_weights=blended,
            expected_return=est["return"],
            expected_risk=est["risk"],
        )

    def recommend_shift(
        self,
        current_weights: dict[str, float],
        new_regime: str,
        regime_probabilities: Optional[dict[str, float]] = None,
    ) -> dict[str, float]:
        """Recommend allocation shifts for a regime change.

        Returns:
            Dict of {asset: weight_change} (positive = buy, negative = sell).
        """
        alloc = self.allocate(new_regime, regime_probabilities=regime_probabilities)
        target = alloc.blended_weights

        shifts = {}
        all_assets = set(list(current_weights.keys()) + list(target.keys()))
        for asset in all_assets:
            curr = current_weights.get(asset, 0.0)
            tgt = target.get(asset, 0.0)
            diff = tgt - curr
            if abs(diff) > 0.005:
                shifts[asset] = round(diff, 4)

        return shifts

    def regime_signal(
        self,
        regime: str,
        previous_regime: Optional[str] = None,
    ) -> dict[str, str]:
        """Generate buy/sell/hold signals based on regime.

        Returns:
            Dict of {asset_class: signal}.
        """
        target = self.targets.get(regime, {})
        prev_target = self.targets.get(previous_regime, {}) if previous_regime else {}

        signals = {}
        for asset in target:
            curr_w = target.get(asset, 0.0)
            prev_w = prev_target.get(asset, curr_w)
            diff = curr_w - prev_w
            if diff > 0.05:
                signals[asset] = "buy"
            elif diff < -0.05:
                signals[asset] = "sell"
            else:
                signals[asset] = "hold"

        return signals

    def _blend_weights(self, regime_probs: dict[str, float]) -> dict[str, float]:
        """Blend target weights across regimes using probabilities."""
        all_assets: set[str] = set()
        for regime_targets in self.targets.values():
            all_assets.update(regime_targets.keys())

        blended: dict[str, float] = {asset: 0.0 for asset in all_assets}

        for regime, prob in regime_probs.items():
            target = self.targets.get(regime, {})
            for asset in all_assets:
                blended[asset] += prob * target.get(asset, 0.0)

        return blended

    def _smooth(self, weights: dict[str, float]) -> dict[str, float]:
        """Smooth weight transition."""
        s = self.config.transition_smoothing
        smoothed = {}
        for asset, w in weights.items():
            prev = self._previous_weights.get(asset, w) if self._previous_weights else w
            smoothed[asset] = s * w + (1 - s) * prev
        return smoothed

    def _constrain(self, weights: dict[str, float]) -> dict[str, float]:
        """Enforce min/max constraints and normalize."""
        constrained = {
            asset: max(self.config.min_single_asset_weight,
                       min(self.config.max_single_asset_weight, w))
            for asset, w in weights.items()
        }
        total = sum(constrained.values())
        if total > 0:
            return {a: round(w / total, 4) for a, w in constrained.items()}
        n = len(constrained)
        return {a: round(1.0 / n, 4) for a in constrained} if n > 0 else constrained
