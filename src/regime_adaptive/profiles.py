"""Strategy profiles for each market regime.

Defines per-regime parameter presets that govern risk limits, position sizing,
signal filtering, and exit behaviour.  The ProfileRegistry holds 4 built-in
profiles (bull / bear / sideways / crisis) and supports custom overrides and
confidence-weighted blending.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ======================================================================
# Data Models
# ======================================================================


@dataclass
class StrategyProfile:
    """Trading parameter set tuned for a specific market regime."""

    # Identity
    name: str = ""
    regime: str = "sideways"  # RegimeType value
    description: str = ""

    # Risk limits
    max_risk_per_trade: float = 0.05
    max_concurrent_positions: int = 10
    daily_loss_limit: float = 0.10
    max_single_stock_exposure: float = 0.15
    max_sector_exposure: float = 0.30

    # Execution / exit
    reward_to_risk_target: float = 2.0
    time_stop_minutes: int = 120
    trailing_stop_cloud: str = "pullback"
    scale_in_enabled: bool = True
    consecutive_loss_threshold: int = 3

    # Signal filtering
    preferred_signal_types: list[str] = field(default_factory=list)
    avoid_signal_types: list[str] = field(default_factory=list)

    # Sizing
    position_size_multiplier: float = 1.0
    min_conviction: int = 50

    def to_dict(self) -> dict:
        """Serialise the profile to a plain dictionary."""
        return {
            "name": self.name,
            "regime": self.regime,
            "description": self.description,
            "max_risk_per_trade": self.max_risk_per_trade,
            "max_concurrent_positions": self.max_concurrent_positions,
            "daily_loss_limit": self.daily_loss_limit,
            "max_single_stock_exposure": self.max_single_stock_exposure,
            "max_sector_exposure": self.max_sector_exposure,
            "reward_to_risk_target": self.reward_to_risk_target,
            "time_stop_minutes": self.time_stop_minutes,
            "trailing_stop_cloud": self.trailing_stop_cloud,
            "scale_in_enabled": self.scale_in_enabled,
            "consecutive_loss_threshold": self.consecutive_loss_threshold,
            "preferred_signal_types": list(self.preferred_signal_types),
            "avoid_signal_types": list(self.avoid_signal_types),
            "position_size_multiplier": self.position_size_multiplier,
            "min_conviction": self.min_conviction,
        }


# ======================================================================
# Built-in Profile Definitions
# ======================================================================

_BULL_PROFILE = StrategyProfile(
    name="bull_aggressive",
    regime="bull",
    description="Aggressive posture for confirmed bull regimes",
    max_risk_per_trade=0.06,
    max_concurrent_positions=12,
    daily_loss_limit=0.12,
    max_single_stock_exposure=0.15,
    max_sector_exposure=0.30,
    reward_to_risk_target=1.8,
    time_stop_minutes=180,
    trailing_stop_cloud="pullback",
    scale_in_enabled=True,
    consecutive_loss_threshold=3,
    preferred_signal_types=[
        "CLOUD_CROSS_BULLISH",
        "TREND_ALIGNED_LONG",
        "CLOUD_BOUNCE_LONG",
    ],
    avoid_signal_types=[
        "CLOUD_CROSS_BEARISH",
        "CLOUD_BOUNCE_SHORT",
    ],
    position_size_multiplier=1.2,
    min_conviction=50,
)

_BEAR_PROFILE = StrategyProfile(
    name="bear_defensive",
    regime="bear",
    description="Defensive posture with tighter limits for bear regimes",
    max_risk_per_trade=0.03,
    max_concurrent_positions=5,
    daily_loss_limit=0.06,
    max_single_stock_exposure=0.15,
    max_sector_exposure=0.30,
    reward_to_risk_target=2.5,
    time_stop_minutes=90,
    trailing_stop_cloud="fast",
    scale_in_enabled=False,
    consecutive_loss_threshold=2,
    preferred_signal_types=[
        "CLOUD_CROSS_BEARISH",
        "TREND_ALIGNED_SHORT",
    ],
    avoid_signal_types=[
        "CLOUD_BOUNCE_LONG",
        "TREND_ALIGNED_LONG",
    ],
    position_size_multiplier=0.6,
    min_conviction=70,
)

_SIDEWAYS_PROFILE = StrategyProfile(
    name="sideways_neutral",
    regime="sideways",
    description="Neutral range-trading posture for sideways regimes",
    max_risk_per_trade=0.04,
    max_concurrent_positions=8,
    daily_loss_limit=0.08,
    max_single_stock_exposure=0.15,
    max_sector_exposure=0.30,
    reward_to_risk_target=2.0,
    time_stop_minutes=120,
    trailing_stop_cloud="pullback",
    scale_in_enabled=True,
    consecutive_loss_threshold=3,
    preferred_signal_types=[
        "CLOUD_BOUNCE_LONG",
        "CLOUD_BOUNCE_SHORT",
        "MOMENTUM_EXHAUSTION",
    ],
    avoid_signal_types=[
        "TREND_ALIGNED_LONG",
        "TREND_ALIGNED_SHORT",
    ],
    position_size_multiplier=0.8,
    min_conviction=60,
)

_CRISIS_PROFILE = StrategyProfile(
    name="crisis_protective",
    regime="crisis",
    description="Protective posture with minimal exposure during crisis",
    max_risk_per_trade=0.02,
    max_concurrent_positions=3,
    daily_loss_limit=0.04,
    max_single_stock_exposure=0.15,
    max_sector_exposure=0.30,
    reward_to_risk_target=3.0,
    time_stop_minutes=60,
    trailing_stop_cloud="fast",
    scale_in_enabled=False,
    consecutive_loss_threshold=1,
    preferred_signal_types=[
        "CLOUD_CROSS_BEARISH",
    ],
    avoid_signal_types=[
        "CLOUD_CROSS_BULLISH",
        "CLOUD_BOUNCE_LONG",
        "TREND_ALIGNED_LONG",
        "MTF_CONFLUENCE",
    ],
    position_size_multiplier=0.3,
    min_conviction=80,
)

_DEFAULT_PROFILES: dict[str, StrategyProfile] = {
    "bull": _BULL_PROFILE,
    "bear": _BEAR_PROFILE,
    "sideways": _SIDEWAYS_PROFILE,
    "crisis": _CRISIS_PROFILE,
}


# ======================================================================
# Numeric fields eligible for blending
# ======================================================================

_NUMERIC_FIELDS: list[str] = [
    "max_risk_per_trade",
    "max_concurrent_positions",
    "daily_loss_limit",
    "max_single_stock_exposure",
    "max_sector_exposure",
    "reward_to_risk_target",
    "time_stop_minutes",
    "position_size_multiplier",
    "min_conviction",
    "consecutive_loss_threshold",
]

_BOOL_FIELDS: list[str] = [
    "scale_in_enabled",
]


# ======================================================================
# ProfileRegistry
# ======================================================================


class ProfileRegistry:
    """Registry of per-regime strategy profiles.

    Holds the four built-in profiles and allows custom overrides.  Provides
    a blending helper that mixes the detected-regime profile toward the
    neutral *sideways* baseline when detection confidence is low.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, StrategyProfile] = {
            k: copy.deepcopy(v) for k, v in _DEFAULT_PROFILES.items()
        }

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_profile(self, regime: str) -> StrategyProfile:
        """Return the profile for *regime* (falls back to sideways)."""
        regime_lower = regime.lower()
        if regime_lower in self._profiles:
            return copy.deepcopy(self._profiles[regime_lower])
        logger.warning(
            "Unknown regime '%s', falling back to sideways profile", regime
        )
        return copy.deepcopy(self._profiles["sideways"])

    def get_all_profiles(self) -> dict[str, StrategyProfile]:
        """Return a copy of every registered profile."""
        return {k: copy.deepcopy(v) for k, v in self._profiles.items()}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register_custom(self, profile: StrategyProfile) -> None:
        """Register (or replace) a profile for the given regime."""
        regime_lower = profile.regime.lower()
        self._profiles[regime_lower] = copy.deepcopy(profile)
        logger.info(
            "Registered custom profile '%s' for regime '%s'",
            profile.name,
            regime_lower,
        )

    # ------------------------------------------------------------------
    # Blending
    # ------------------------------------------------------------------

    def get_blended_profile(
        self, regime: str, confidence: float
    ) -> StrategyProfile:
        """Return a confidence-weighted blend between *regime* and sideways.

        When confidence >= 0.7 the pure regime profile is returned.
        Below that threshold numeric parameters are linearly interpolated
        and boolean parameters use the more conservative value.

        The ``blend_factor`` is clamped so that ``max(0.5, confidence)``
        ensures the detected regime is never fully ignored.
        """
        target = self.get_profile(regime)

        if confidence >= 0.7:
            return target

        baseline = self.get_profile("sideways")
        blend_factor = max(0.5, confidence)

        blended = copy.deepcopy(target)
        blended.name = f"blended_{regime}_{confidence:.2f}"
        blended.description = (
            f"Blended profile ({blend_factor:.0%} {regime} / "
            f"{1 - blend_factor:.0%} sideways)"
        )

        # --- Numeric fields: weighted average ---
        for fld in _NUMERIC_FIELDS:
            target_val = getattr(target, fld)
            baseline_val = getattr(baseline, fld)
            blended_val = (
                blend_factor * target_val + (1 - blend_factor) * baseline_val
            )
            # Preserve int type for fields that expect it
            if isinstance(target_val, int):
                blended_val = int(round(blended_val))
            setattr(blended, fld, blended_val)

        # --- Boolean fields: use the more conservative value ---
        # "Conservative" = the value that reduces risk.
        # For scale_in_enabled, False is more conservative (less exposure).
        for fld in _BOOL_FIELDS:
            target_val = getattr(target, fld)
            baseline_val = getattr(baseline, fld)
            if fld == "scale_in_enabled":
                # More conservative = False when either is False
                setattr(blended, fld, target_val and baseline_val)
            else:
                setattr(blended, fld, target_val and baseline_val)

        # --- String field: trailing_stop_cloud ---
        # Use the faster (more conservative) stop when confidence is low
        if target.trailing_stop_cloud == "fast" or baseline.trailing_stop_cloud == "fast":
            blended.trailing_stop_cloud = "fast"
        else:
            blended.trailing_stop_cloud = target.trailing_stop_cloud

        # --- List fields: union minus shared avoids ---
        preferred_union = list(
            set(target.preferred_signal_types)
            | set(baseline.preferred_signal_types)
        )
        avoid_union = list(
            set(target.avoid_signal_types)
            | set(baseline.avoid_signal_types)
        )
        # Remove any signal type that appears in the avoid list
        blended.preferred_signal_types = [
            s for s in preferred_union if s not in avoid_union
        ]
        blended.avoid_signal_types = sorted(avoid_union)

        return blended
