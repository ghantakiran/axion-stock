"""Regime transition monitor.

Tracks regime changes over time, detects transitions, enforces a circuit
breaker when the regime signal is too noisy, and provides transition
frequency analytics.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ======================================================================
# Configuration
# ======================================================================


@dataclass
class MonitorConfig:
    """Knobs for the regime monitor."""

    check_interval_seconds: float = 60.0
    alert_on_transition: bool = True
    min_confidence_for_alert: float = 0.6
    max_transitions_per_hour: int = 5


# ======================================================================
# Data Models
# ======================================================================


@dataclass
class RegimeTransition:
    """Record of a single regime change."""

    from_regime: str = ""
    to_regime: str = ""
    confidence: float = 0.0
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    method: str = "ensemble"
    transition_id: str = field(
        default_factory=lambda: str(uuid.uuid4())[:8]
    )

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary."""
        return {
            "transition_id": self.transition_id,
            "from_regime": self.from_regime,
            "to_regime": self.to_regime,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "method": self.method,
        }


@dataclass
class MonitorState:
    """Snapshot of the monitor's current understanding of the regime."""

    current_regime: str = "sideways"
    current_confidence: float = 0.5
    regime_duration_seconds: float = 0.0
    transitions_last_hour: int = 0
    is_circuit_broken: bool = False
    last_check: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary."""
        return {
            "current_regime": self.current_regime,
            "current_confidence": self.current_confidence,
            "regime_duration_seconds": round(self.regime_duration_seconds, 2),
            "transitions_last_hour": self.transitions_last_hour,
            "is_circuit_broken": self.is_circuit_broken,
            "last_check": (
                self.last_check.isoformat() if self.last_check else None
            ),
        }


# ======================================================================
# RegimeMonitor
# ======================================================================


class RegimeMonitor:
    """Monitors regime detections, records transitions, and enforces
    a circuit breaker when transitions are excessively frequent.

    Usage::

        monitor = RegimeMonitor()
        transition = monitor.update("bull", 0.85, method="hmm")
        if transition:
            print(f"Regime changed to {transition.to_regime}")
    """

    def __init__(self, config: Optional[MonitorConfig] = None) -> None:
        self._config = config or MonitorConfig()
        self._transitions: list[RegimeTransition] = []
        self._state = MonitorState()
        self._regime_start: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Core update
    # ------------------------------------------------------------------

    def update(
        self,
        regime: str,
        confidence: float,
        method: str = "ensemble",
    ) -> Optional[RegimeTransition]:
        """Process a new regime observation.

        Parameters
        ----------
        regime:
            Detected regime string (bull / bear / sideways / crisis).
        confidence:
            Detection confidence in [0, 1].
        method:
            The detection method that produced this observation.

        Returns
        -------
        A ``RegimeTransition`` if a regime change was detected and the
        circuit breaker is not tripped, otherwise ``None``.
        """
        now = datetime.now(timezone.utc)
        regime_lower = regime.lower()
        self._state.last_check = now

        # Update transitions-last-hour count
        self._prune_old_transitions(now)
        self._state.transitions_last_hour = self._count_recent_transitions(now)

        # Same regime — just update duration and confidence
        if regime_lower == self._state.current_regime:
            self._state.current_confidence = confidence
            if self._regime_start is not None:
                delta = (now - self._regime_start).total_seconds()
                self._state.regime_duration_seconds = delta
            return None

        # Regime changed — check confidence threshold
        if confidence < self._config.min_confidence_for_alert:
            logger.debug(
                "Regime change to '%s' suppressed (confidence %.2f < %.2f)",
                regime_lower,
                confidence,
                self._config.min_confidence_for_alert,
            )
            return None

        # Check circuit breaker
        if (
            self._state.transitions_last_hour
            >= self._config.max_transitions_per_hour
        ):
            self._state.is_circuit_broken = True
            logger.warning(
                "Circuit breaker TRIPPED: %d transitions in last hour "
                "(max=%d). Ignoring regime change to '%s'.",
                self._state.transitions_last_hour,
                self._config.max_transitions_per_hour,
                regime_lower,
            )
            return None

        # Valid transition
        transition = RegimeTransition(
            from_regime=self._state.current_regime,
            to_regime=regime_lower,
            confidence=confidence,
            timestamp=now,
            method=method,
        )
        self._transitions.append(transition)

        # Update state
        self._state.current_regime = regime_lower
        self._state.current_confidence = confidence
        self._state.regime_duration_seconds = 0.0
        self._state.is_circuit_broken = False
        self._regime_start = now
        self._state.transitions_last_hour = self._count_recent_transitions(now)

        if self._config.alert_on_transition:
            logger.info(
                "Regime TRANSITION [%s]: %s -> %s (confidence=%.2f, "
                "method=%s, transitions_last_hour=%d)",
                transition.transition_id,
                transition.from_regime,
                transition.to_regime,
                confidence,
                method,
                self._state.transitions_last_hour,
            )

        return transition

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_state(self) -> MonitorState:
        """Return a copy of the current monitor state."""
        now = datetime.now(timezone.utc)
        # Refresh duration
        if self._regime_start is not None:
            self._state.regime_duration_seconds = (
                now - self._regime_start
            ).total_seconds()
        self._state.transitions_last_hour = self._count_recent_transitions(now)
        return MonitorState(
            current_regime=self._state.current_regime,
            current_confidence=self._state.current_confidence,
            regime_duration_seconds=self._state.regime_duration_seconds,
            transitions_last_hour=self._state.transitions_last_hour,
            is_circuit_broken=self._state.is_circuit_broken,
            last_check=self._state.last_check,
        )

    def get_transitions(self, limit: int = 20) -> list[RegimeTransition]:
        """Return the most recent transitions (newest first).

        Parameters
        ----------
        limit:
            Maximum number of transitions to return.
        """
        return list(reversed(self._transitions[-limit:]))

    def get_transition_frequency(self) -> dict:
        """Return a mapping of ``(from, to)`` pairs to occurrence counts.

        Example return value::

            {"bull->bear": 3, "sideways->bull": 5, ...}
        """
        freq: dict[str, int] = {}
        for t in self._transitions:
            key = f"{t.from_regime}->{t.to_regime}"
            freq[key] = freq.get(key, 0) + 1
        return freq

    def reset(self) -> None:
        """Clear all internal state."""
        self._transitions.clear()
        self._state = MonitorState()
        self._regime_start = None
        logger.debug("RegimeMonitor state reset")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _count_recent_transitions(self, now: datetime) -> int:
        """Count transitions that occurred in the last 60 minutes."""
        count = 0
        for t in reversed(self._transitions):
            delta = (now - t.timestamp).total_seconds()
            if delta <= 3600.0:
                count += 1
            else:
                break
        return count

    def _prune_old_transitions(self, now: datetime) -> None:
        """Remove transitions older than 24 hours to cap memory."""
        cutoff = 86400.0  # 24 hours in seconds
        self._transitions = [
            t
            for t in self._transitions
            if (now - t.timestamp).total_seconds() <= cutoff
        ]
