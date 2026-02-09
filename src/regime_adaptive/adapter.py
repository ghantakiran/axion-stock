"""Regime-to-config adapter.

Applies a regime-derived StrategyProfile to an ExecutorConfig (represented
as a plain dict) so the autonomous trading bot can shift parameters in
real time without a restart.  Supports smooth transitions, user-override
preservation, and signal filtering.
"""

from __future__ import annotations

import copy
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.regime_adaptive.profiles import ProfileRegistry, StrategyProfile

logger = logging.getLogger(__name__)


# ======================================================================
# Configuration & Result Models
# ======================================================================


@dataclass
class AdapterConfig:
    """Knobs for the regime adapter."""

    smooth_transitions: bool = True
    transition_speed: float = 0.5  # 0 = instant, 1 = very slow
    respect_user_overrides: bool = True
    min_confidence_to_adapt: float = 0.5
    log_adaptations: bool = True


@dataclass
class ConfigAdaptation:
    """Describes a single adaptation applied to the executor config."""

    original_config: dict = field(default_factory=dict)
    adapted_config: dict = field(default_factory=dict)
    changes: list[dict] = field(default_factory=list)
    regime: str = ""
    confidence: float = 0.0
    profile_used: str = ""
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    adaptation_id: str = field(
        default_factory=lambda: str(uuid.uuid4())[:8]
    )

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary."""
        return {
            "adaptation_id": self.adaptation_id,
            "original_config": self.original_config,
            "adapted_config": self.adapted_config,
            "changes": list(self.changes),
            "regime": self.regime,
            "confidence": self.confidence,
            "profile_used": self.profile_used,
            "timestamp": self.timestamp.isoformat(),
        }


# ======================================================================
# Fields that may be adapted
# ======================================================================

_ADAPTABLE_NUMERIC: list[str] = [
    "max_risk_per_trade",
    "max_concurrent_positions",
    "daily_loss_limit",
    "max_single_stock_exposure",
    "max_sector_exposure",
    "reward_to_risk_target",
    "time_stop_minutes",
    "consecutive_loss_threshold",
]

_ADAPTABLE_BOOL: list[str] = [
    "scale_in_enabled",
]

_ADAPTABLE_STR: list[str] = [
    "trailing_stop_cloud",
]


# ======================================================================
# RegimeAdapter
# ======================================================================


class RegimeAdapter:
    """Translates regime detections into executor-config mutations.

    Maintains internal state so that consecutive regime changes can be
    smoothly interpolated rather than causing abrupt parameter jumps.
    """

    def __init__(
        self,
        config: Optional[AdapterConfig] = None,
        registry: Optional[ProfileRegistry] = None,
    ) -> None:
        self._config = config or AdapterConfig()
        self._registry = registry or ProfileRegistry()
        self._previous_regime: Optional[str] = None
        self._previous_profile: Optional[StrategyProfile] = None
        self._transition_progress: float = 1.0  # 1.0 = fully transitioned
        self._adaptation_history: list[dict] = []

    # ------------------------------------------------------------------
    # Core adaptation
    # ------------------------------------------------------------------

    def adapt(
        self,
        executor_config: dict,
        regime: str,
        confidence: float,
    ) -> ConfigAdaptation:
        """Apply the regime profile to *executor_config* (dict of fields).

        Parameters
        ----------
        executor_config:
            Dict representation of ExecutorConfig fields.
        regime:
            Detected regime string (bull / bear / sideways / crisis).
        confidence:
            Detection confidence in [0, 1].

        Returns
        -------
        ConfigAdaptation with original, adapted configs and change list.
        """
        original = copy.deepcopy(executor_config)
        regime_lower = regime.lower()

        # Below confidence threshold: return unchanged
        if confidence < self._config.min_confidence_to_adapt:
            adaptation = ConfigAdaptation(
                original_config=original,
                adapted_config=copy.deepcopy(original),
                changes=[],
                regime=regime_lower,
                confidence=confidence,
                profile_used="none (below confidence threshold)",
            )
            self._record(adaptation)
            return adaptation

        # Get profile (blended when confidence < 0.7)
        profile = self._registry.get_blended_profile(regime_lower, confidence)

        # Handle smooth transitions
        if (
            self._config.smooth_transitions
            and self._previous_regime is not None
            and regime_lower != self._previous_regime
        ):
            # Regime changed: start a new transition from 0
            self._transition_progress = 0.0
        elif (
            self._config.smooth_transitions
            and self._previous_regime is not None
            and regime_lower == self._previous_regime
        ):
            # Same regime: advance transition progress
            step = max(0.1, 1.0 - self._config.transition_speed)
            self._transition_progress = min(
                1.0, self._transition_progress + step
            )
        else:
            # First call or no smoothing
            self._transition_progress = 1.0

        adapted = copy.deepcopy(executor_config)
        changes: list[dict] = []

        # --- Numeric fields ---
        for fld in _ADAPTABLE_NUMERIC:
            if fld not in executor_config:
                continue
            old_val = executor_config[fld]
            target_val = getattr(profile, fld)

            if (
                self._config.smooth_transitions
                and self._transition_progress < 1.0
                and self._previous_profile is not None
            ):
                # Interpolate between previous profile value and new target
                prev_val = getattr(self._previous_profile, fld)
                new_val = (
                    prev_val
                    + (target_val - prev_val) * self._transition_progress
                )
            else:
                new_val = target_val

            # Preserve int types
            if isinstance(old_val, int):
                new_val = int(round(new_val))
            else:
                new_val = round(new_val, 6)

            if new_val != old_val:
                adapted[fld] = new_val
                changes.append(
                    {
                        "field": fld,
                        "old_value": old_val,
                        "new_value": new_val,
                        "reason": f"Regime '{regime_lower}' profile ({profile.name})",
                    }
                )

        # --- Boolean fields ---
        for fld in _ADAPTABLE_BOOL:
            if fld not in executor_config:
                continue
            old_val = executor_config[fld]
            target_val = getattr(profile, fld)

            if (
                self._config.smooth_transitions
                and self._transition_progress < 1.0
            ):
                # Snap booleans at 50% progress
                new_val = target_val if self._transition_progress >= 0.5 else old_val
            else:
                new_val = target_val

            if new_val != old_val:
                adapted[fld] = new_val
                changes.append(
                    {
                        "field": fld,
                        "old_value": old_val,
                        "new_value": new_val,
                        "reason": f"Regime '{regime_lower}' profile ({profile.name})",
                    }
                )

        # --- String fields ---
        for fld in _ADAPTABLE_STR:
            if fld not in executor_config:
                continue
            old_val = executor_config[fld]
            target_val = getattr(profile, fld)

            if target_val != old_val:
                adapted[fld] = target_val
                changes.append(
                    {
                        "field": fld,
                        "old_value": old_val,
                        "new_value": target_val,
                        "reason": f"Regime '{regime_lower}' profile ({profile.name})",
                    }
                )

        # Update internal state
        self._previous_regime = regime_lower
        self._previous_profile = profile

        adaptation = ConfigAdaptation(
            original_config=original,
            adapted_config=adapted,
            changes=changes,
            regime=regime_lower,
            confidence=confidence,
            profile_used=profile.name,
        )

        self._record(adaptation)

        if self._config.log_adaptations and changes:
            logger.info(
                "Regime adaptation [%s]: %d parameter(s) changed for '%s' "
                "(confidence=%.2f, profile=%s)",
                adaptation.adaptation_id,
                len(changes),
                regime_lower,
                confidence,
                profile.name,
            )

        return adaptation

    # ------------------------------------------------------------------
    # Signal filtering
    # ------------------------------------------------------------------

    def filter_signals(
        self,
        signals: list[dict],
        regime: str,
        confidence: float,
    ) -> list[dict]:
        """Filter and annotate signals based on regime profile.

        Signals whose ``signal_type`` is in the profile's *avoid* list are
        removed.  Remaining signals get a ``regime_boost`` key:

        * ``1.0`` -- preferred signal type in this regime
        * ``0.0`` -- neutral (neither preferred nor avoided)
        * ``-1.0`` -- would have been avoided (kept only when confidence is
          very low, but this branch currently filters them out)

        Parameters
        ----------
        signals:
            List of signal dicts, each with at least a ``"signal_type"`` key.
        regime:
            Detected regime string.
        confidence:
            Detection confidence in [0, 1].

        Returns
        -------
        Filtered list of signal dicts with the ``regime_boost`` key added.
        """
        profile = self._registry.get_blended_profile(regime.lower(), confidence)
        preferred = set(profile.preferred_signal_types)
        avoided = set(profile.avoid_signal_types)

        filtered: list[dict] = []
        for sig in signals:
            sig_type = sig.get("signal_type", "")
            if sig_type in avoided:
                # Suppressed
                continue
            enriched = copy.deepcopy(sig)
            if sig_type in preferred:
                enriched["regime_boost"] = 1.0
            else:
                enriched["regime_boost"] = 0.0
            filtered.append(enriched)

        logger.debug(
            "Signal filter: %d input -> %d output (%s regime, %.2f conf)",
            len(signals),
            len(filtered),
            regime,
            confidence,
        )
        return filtered

    # ------------------------------------------------------------------
    # History & state
    # ------------------------------------------------------------------

    def get_adaptation_history(self) -> list[dict]:
        """Return the list of recent adaptations (oldest first)."""
        return list(self._adaptation_history)

    def reset(self) -> None:
        """Clear all internal state."""
        self._previous_regime = None
        self._previous_profile = None
        self._transition_progress = 1.0
        self._adaptation_history.clear()
        logger.debug("RegimeAdapter state reset")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record(self, adaptation: ConfigAdaptation) -> None:
        """Append an adaptation record to history (capped at 200)."""
        self._adaptation_history.append(adaptation.to_dict())
        if len(self._adaptation_history) > 200:
            self._adaptation_history = self._adaptation_history[-200:]
