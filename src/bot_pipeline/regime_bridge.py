"""PRD-173: Regime Bridge — connects regime detection to the bot pipeline.

Queries the current market regime and maps it to a StrategyProfile
from the ProfileRegistry, then adapts ExecutorConfig parameters
to match the regime-appropriate risk posture.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.regime_adaptive.profiles import ProfileRegistry, StrategyProfile
from src.trade_executor.executor import ExecutorConfig

logger = logging.getLogger(__name__)


@dataclass
class RegimeState:
    """Current regime detection state."""

    regime: str = "sideways"
    confidence: float = 0.5
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "confidence": round(self.confidence, 3),
            "detected_at": self.detected_at.isoformat(),
        }


class RegimeBridge:
    """Bridge between regime detection and the bot pipeline.

    Translates market regime into concrete ExecutorConfig adjustments
    using the ProfileRegistry's blended profiles.

    Args:
        registry: ProfileRegistry with regime profiles (created if None).
        default_regime: Fallback regime when detection is unavailable.
    """

    def __init__(
        self,
        registry: ProfileRegistry | None = None,
        default_regime: str = "sideways",
    ) -> None:
        self._registry = registry or ProfileRegistry()
        self._default_regime = default_regime
        self._current_state = RegimeState(regime=default_regime)
        self._history: list[RegimeState] = []

    def get_current_regime(self) -> str:
        """Return the current market regime string."""
        return self._current_state.regime

    def get_current_state(self) -> RegimeState:
        """Return the full current regime state."""
        return self._current_state

    def update_regime(self, regime: str, confidence: float = 0.5) -> None:
        """Update the current regime detection.

        Args:
            regime: Detected regime ('bull', 'bear', 'sideways', 'crisis').
            confidence: Detection confidence 0.0-1.0.
        """
        self._current_state = RegimeState(
            regime=regime,
            confidence=max(0.0, min(1.0, confidence)),
        )
        self._history.append(self._current_state)
        # Keep history bounded
        if len(self._history) > 500:
            self._history = self._history[-500:]
        logger.info("Regime updated: %s (confidence=%.2f)", regime, confidence)

    def get_strategy_profile(self, regime: str | None = None) -> StrategyProfile:
        """Get the strategy profile for a regime.

        Args:
            regime: Regime string (uses current if None).

        Returns:
            StrategyProfile with regime-appropriate parameters.
        """
        regime = regime or self._current_state.regime
        confidence = self._current_state.confidence
        return self._registry.get_blended_profile(regime, confidence)

    def adapt_config(
        self,
        executor_config: ExecutorConfig,
        profile: StrategyProfile | None = None,
    ) -> ExecutorConfig:
        """Adapt an ExecutorConfig to match the regime profile.

        Maps StrategyProfile risk parameters onto ExecutorConfig fields.

        Args:
            executor_config: Base config to adapt.
            profile: Profile to use (fetches current regime if None).

        Returns:
            New ExecutorConfig with adapted parameters.
        """
        if profile is None:
            profile = self.get_strategy_profile()

        # Map profile params to ExecutorConfig
        adapted = ExecutorConfig(
            max_risk_per_trade=profile.max_risk_per_trade,
            max_concurrent_positions=profile.max_concurrent_positions,
            daily_loss_limit=profile.daily_loss_limit,
            reward_to_risk_target=profile.reward_to_risk_target,
            time_stop_minutes=profile.time_stop_minutes,
            consecutive_loss_threshold=profile.consecutive_loss_threshold,
            # Preserve original config fields not in profile
            primary_broker=executor_config.primary_broker,
            default_time_in_force=executor_config.default_time_in_force,
            consecutive_loss_pct=executor_config.consecutive_loss_pct,
        )
        return adapted

    def get_regime_history(self, limit: int = 50) -> list[dict]:
        """Get recent regime detection history."""
        return [s.to_dict() for s in self._history[-limit:]]
