"""PRD-176: Weight Store — persists weight adjustment history for audit trail.

Stores weight snapshots with timestamps for tracking how fusion
weights evolve over time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class WeightSnapshot:
    """A point-in-time record of fusion weights.

    Attributes:
        weights: Source → weight mapping.
        trigger: What caused this update ('manual', 'auto', 'initial').
        trade_count: Total trades at time of update.
        timestamp: When the snapshot was recorded.
    """

    weights: dict[str, float] = field(default_factory=dict)
    trigger: str = "initial"
    trade_count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "trigger": self.trigger,
            "trade_count": self.trade_count,
            "timestamp": self.timestamp.isoformat(),
        }


class WeightStore:
    """Persistent store for signal fusion weight history.

    Maintains an in-memory timeline of weight snapshots
    for audit and analysis purposes.

    Args:
        max_history: Maximum snapshots to retain.
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._history: list[WeightSnapshot] = []
        self._max_history = max_history

    def record(
        self,
        weights: dict[str, float],
        trigger: str = "auto",
        trade_count: int = 0,
    ) -> WeightSnapshot:
        """Record a weight snapshot.

        Args:
            weights: Current source weights.
            trigger: What triggered this update.
            trade_count: Total trades at this point.

        Returns:
            The created WeightSnapshot.
        """
        snapshot = WeightSnapshot(
            weights=dict(weights),
            trigger=trigger,
            trade_count=trade_count,
        )
        self._history.append(snapshot)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        return snapshot

    def get_latest(self) -> WeightSnapshot | None:
        """Get the most recent weight snapshot."""
        return self._history[-1] if self._history else None

    def get_history(self, limit: int = 50) -> list[dict]:
        """Get recent weight history as dicts."""
        return [s.to_dict() for s in self._history[-limit:]]

    def get_weight_evolution(self, source: str) -> list[tuple[str, float]]:
        """Get weight evolution for a specific source.

        Returns:
            List of (timestamp_iso, weight) tuples.
        """
        evolution = []
        for snap in self._history:
            if source in snap.weights:
                evolution.append((snap.timestamp.isoformat(), snap.weights[source]))
        return evolution

    def get_total_updates(self) -> int:
        """Get total number of recorded weight updates."""
        return len(self._history)
