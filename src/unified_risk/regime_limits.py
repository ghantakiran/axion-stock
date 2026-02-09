"""Regime-Adaptive Risk Limits — dynamically adjusts limits by market regime.

Reads the current market regime and applies regime-specific multipliers
to risk limits. In bull markets, limits are relaxed; in crisis, they tighten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegimeLimits:
    """Risk limits for a specific market regime.

    Multipliers are applied to base limits (1.0 = no change).

    Attributes:
        regime: Market regime name.
        position_size_mult: Multiplier for position sizes.
        max_positions_mult: Multiplier for max concurrent positions.
        sector_concentration_mult: Multiplier for sector limits.
        correlation_threshold_mult: Multiplier for correlation threshold.
        stop_loss_mult: Multiplier for stop loss distance.
        description: Human-readable description.
    """

    regime: str = "sideways"
    position_size_mult: float = 1.0
    max_positions_mult: float = 1.0
    sector_concentration_mult: float = 1.0
    correlation_threshold_mult: float = 1.0
    stop_loss_mult: float = 1.0
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "position_size_mult": self.position_size_mult,
            "max_positions_mult": self.max_positions_mult,
            "sector_concentration_mult": self.sector_concentration_mult,
            "correlation_threshold_mult": self.correlation_threshold_mult,
            "stop_loss_mult": self.stop_loss_mult,
            "description": self.description,
        }


# Pre-defined regime profiles
REGIME_PROFILES: dict[str, RegimeLimits] = {
    "bull": RegimeLimits(
        regime="bull",
        position_size_mult=1.2,
        max_positions_mult=1.2,
        sector_concentration_mult=1.1,
        correlation_threshold_mult=1.0,
        stop_loss_mult=1.2,
        description="Trending bull: expanded sizing, wider stops",
    ),
    "bear": RegimeLimits(
        regime="bear",
        position_size_mult=0.5,
        max_positions_mult=0.6,
        sector_concentration_mult=0.8,
        correlation_threshold_mult=0.85,
        stop_loss_mult=0.8,
        description="Bear market: reduced sizing, tighter stops, stricter correlation",
    ),
    "sideways": RegimeLimits(
        regime="sideways",
        position_size_mult=0.8,
        max_positions_mult=0.9,
        sector_concentration_mult=1.0,
        correlation_threshold_mult=1.0,
        stop_loss_mult=0.9,
        description="Choppy/sideways: slightly reduced, favor mean reversion",
    ),
    "crisis": RegimeLimits(
        regime="crisis",
        position_size_mult=0.2,
        max_positions_mult=0.3,
        sector_concentration_mult=0.5,
        correlation_threshold_mult=0.7,
        stop_loss_mult=0.5,
        description="Crisis: minimal sizing, very tight limits, preserve capital",
    ),
}


class RegimeRiskAdapter:
    """Adapts risk limits based on the current market regime.

    Reads regime from platform's regime detection system and returns
    adjusted limits via multipliers.

    Args:
        profiles: Custom regime profiles (uses defaults if not provided).
        default_regime: Fallback regime when detection is unavailable.

    Example:
        adapter = RegimeRiskAdapter()
        limits = adapter.get_limits("bear")
        adjusted_size = base_size * limits.position_size_mult
    """

    def __init__(
        self,
        profiles: dict[str, RegimeLimits] | None = None,
        default_regime: str = "sideways",
    ) -> None:
        self._profiles = profiles or dict(REGIME_PROFILES)
        self._default_regime = default_regime
        self._current_regime: str = default_regime

    @property
    def current_regime(self) -> str:
        return self._current_regime

    def set_regime(self, regime: str) -> None:
        """Update the current market regime."""
        self._current_regime = regime

    def get_limits(self, regime: str | None = None) -> RegimeLimits:
        """Get risk limits for a specific regime.

        Args:
            regime: Regime name. Uses current_regime if None.

        Returns:
            RegimeLimits with multipliers for the regime.
        """
        regime = regime or self._current_regime
        return self._profiles.get(
            regime,
            self._profiles.get(self._default_regime, RegimeLimits()),
        )

    def adjust_position_size(self, base_size: float, regime: str | None = None) -> float:
        """Apply regime multiplier to a base position size."""
        limits = self.get_limits(regime)
        return base_size * limits.position_size_mult

    def adjust_max_positions(self, base_max: int, regime: str | None = None) -> int:
        """Apply regime multiplier to max concurrent positions."""
        limits = self.get_limits(regime)
        return max(1, int(base_max * limits.max_positions_mult))

    def adjust_stop_distance(self, base_stop: float, regime: str | None = None) -> float:
        """Apply regime multiplier to stop loss distance."""
        limits = self.get_limits(regime)
        return base_stop * limits.stop_loss_mult

    def get_all_profiles(self) -> dict[str, dict]:
        """Return all regime profiles as dicts."""
        return {name: limits.to_dict() for name, limits in self._profiles.items()}
