"""Dynamic Threshold Manager.

Adjusts entry/exit thresholds, stop-loss levels, and confidence
requirements based on the current market regime.  Crisis regimes
tighten stops and raise confidence bars; bull regimes widen stops
and lower entry thresholds.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.regime.config import RegimeType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class ThresholdSet:
    """Regime-specific threshold configuration."""
    regime: str = ""
    entry_threshold: float = 0.5  # Minimum signal score to enter
    exit_threshold: float = -0.2  # Signal score to trigger exit
    stop_loss_pct: float = 0.05  # Stop-loss percentage
    take_profit_pct: float = 0.10  # Take-profit percentage
    min_confidence: float = 0.6  # Minimum confidence to act
    position_size_scalar: float = 1.0  # Position size multiplier

    @property
    def risk_reward_ratio(self) -> float:
        if self.stop_loss_pct <= 0:
            return 0.0
        return self.take_profit_pct / self.stop_loss_pct

    @property
    def is_conservative(self) -> bool:
        return self.min_confidence >= 0.7 and self.stop_loss_pct <= 0.03


@dataclass
class ThresholdComparison:
    """Comparison of thresholds across regimes."""
    thresholds: dict[str, ThresholdSet] = field(default_factory=dict)
    current_regime: str = ""
    current_set: ThresholdSet = field(default_factory=ThresholdSet)

    @property
    def tightest_stop(self) -> str:
        if not self.thresholds:
            return ""
        return min(
            self.thresholds, key=lambda r: self.thresholds[r].stop_loss_pct
        )

    @property
    def widest_stop(self) -> str:
        if not self.thresholds:
            return ""
        return max(
            self.thresholds, key=lambda r: self.thresholds[r].stop_loss_pct
        )


@dataclass
class SignalDecision:
    """Decision output from threshold evaluation."""
    signal_name: str = ""
    signal_score: float = 0.0
    signal_confidence: float = 0.0
    regime: str = ""
    action: str = "hold"  # enter, exit, hold
    reason: str = ""
    position_size: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0

    @property
    def is_actionable(self) -> bool:
        return self.action in ("enter", "exit")


# ---------------------------------------------------------------------------
# Default regime thresholds
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLDS: dict[str, ThresholdSet] = {
    "bull": ThresholdSet(
        regime="bull",
        entry_threshold=0.3,
        exit_threshold=-0.3,
        stop_loss_pct=0.07,
        take_profit_pct=0.15,
        min_confidence=0.5,
        position_size_scalar=1.2,
    ),
    "bear": ThresholdSet(
        regime="bear",
        entry_threshold=0.6,
        exit_threshold=-0.1,
        stop_loss_pct=0.03,
        take_profit_pct=0.08,
        min_confidence=0.7,
        position_size_scalar=0.6,
    ),
    "sideways": ThresholdSet(
        regime="sideways",
        entry_threshold=0.5,
        exit_threshold=-0.2,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        min_confidence=0.6,
        position_size_scalar=0.8,
    ),
    "crisis": ThresholdSet(
        regime="crisis",
        entry_threshold=0.8,
        exit_threshold=-0.05,
        stop_loss_pct=0.02,
        take_profit_pct=0.05,
        min_confidence=0.85,
        position_size_scalar=0.3,
    ),
}


# ---------------------------------------------------------------------------
# Threshold Manager
# ---------------------------------------------------------------------------
class DynamicThresholdManager:
    """Manages trading thresholds that adapt to market regime."""

    def __init__(
        self,
        thresholds: Optional[dict[str, ThresholdSet]] = None,
        base_position_size: float = 1.0,
    ) -> None:
        self.thresholds = thresholds or {
            k: ThresholdSet(**{
                f.name: getattr(v, f.name) for f in v.__dataclass_fields__.values()
            })
            for k, v in DEFAULT_THRESHOLDS.items()
        }
        self.base_position_size = base_position_size

    def get_thresholds(self, regime: str) -> ThresholdSet:
        """Get threshold set for a regime.

        Args:
            regime: Market regime name.

        Returns:
            ThresholdSet for the regime.
        """
        regime_key = regime.lower()
        return self.thresholds.get(regime_key, DEFAULT_THRESHOLDS.get("sideways"))

    def evaluate_signal(
        self,
        signal_name: str,
        signal_score: float,
        signal_confidence: float,
        regime: str,
        current_position: bool = False,
    ) -> SignalDecision:
        """Evaluate a signal against regime-specific thresholds.

        Args:
            signal_name: Name of the signal.
            signal_score: Signal score (-1 to +1).
            signal_confidence: Signal confidence (0-1).
            regime: Current market regime.
            current_position: Whether we currently hold a position.

        Returns:
            SignalDecision with action recommendation.
        """
        ts = self.get_thresholds(regime)

        # Default: hold
        action = "hold"
        reason = "Signal within hold range"

        if current_position:
            # Check exit conditions
            if signal_score <= ts.exit_threshold:
                action = "exit"
                reason = (
                    f"Signal {signal_score:.2f} <= exit threshold "
                    f"{ts.exit_threshold:.2f}"
                )
        else:
            # Check entry conditions
            if (
                signal_score >= ts.entry_threshold
                and signal_confidence >= ts.min_confidence
            ):
                action = "enter"
                reason = (
                    f"Signal {signal_score:.2f} >= entry threshold "
                    f"{ts.entry_threshold:.2f} with confidence "
                    f"{signal_confidence:.0%} >= {ts.min_confidence:.0%}"
                )
            elif signal_score >= ts.entry_threshold:
                reason = (
                    f"Signal meets entry threshold but confidence "
                    f"{signal_confidence:.0%} < {ts.min_confidence:.0%}"
                )

        # Position sizing
        pos_size = 0.0
        if action == "enter":
            pos_size = round(
                self.base_position_size * ts.position_size_scalar, 4
            )

        return SignalDecision(
            signal_name=signal_name,
            signal_score=signal_score,
            signal_confidence=signal_confidence,
            regime=regime.lower(),
            action=action,
            reason=reason,
            position_size=pos_size,
            stop_loss=round(ts.stop_loss_pct, 4),
            take_profit=round(ts.take_profit_pct, 4),
        )

    def compare_thresholds(
        self,
        current_regime: str,
    ) -> ThresholdComparison:
        """Compare thresholds across all regimes.

        Args:
            current_regime: Current market regime.

        Returns:
            ThresholdComparison with all regime threshold sets.
        """
        current = self.get_thresholds(current_regime)
        return ThresholdComparison(
            thresholds=dict(self.thresholds),
            current_regime=current_regime.lower(),
            current_set=current,
        )

    def interpolate_thresholds(
        self,
        regime_probabilities: dict[str, float],
    ) -> ThresholdSet:
        """Interpolate thresholds based on regime probabilities.

        Instead of hard switching, blend thresholds proportionally
        to regime probabilities for smoother transitions.

        Args:
            regime_probabilities: Dict of regime -> probability.

        Returns:
            Blended ThresholdSet.
        """
        entry = 0.0
        exit_t = 0.0
        stop = 0.0
        tp = 0.0
        conf = 0.0
        pos_scalar = 0.0
        total_prob = 0.0

        for regime, prob in regime_probabilities.items():
            ts = self.get_thresholds(regime)
            if ts is None:
                continue
            entry += ts.entry_threshold * prob
            exit_t += ts.exit_threshold * prob
            stop += ts.stop_loss_pct * prob
            tp += ts.take_profit_pct * prob
            conf += ts.min_confidence * prob
            pos_scalar += ts.position_size_scalar * prob
            total_prob += prob

        if total_prob > 0:
            entry /= total_prob
            exit_t /= total_prob
            stop /= total_prob
            tp /= total_prob
            conf /= total_prob
            pos_scalar /= total_prob

        dominant = max(regime_probabilities, key=regime_probabilities.get)

        return ThresholdSet(
            regime=f"blended({dominant})",
            entry_threshold=round(entry, 4),
            exit_threshold=round(exit_t, 4),
            stop_loss_pct=round(stop, 4),
            take_profit_pct=round(tp, 4),
            min_confidence=round(conf, 4),
            position_size_scalar=round(pos_scalar, 4),
        )
