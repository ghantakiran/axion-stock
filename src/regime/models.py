"""Regime Detection Data Models."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RegimeState:
    """Current regime identification."""
    regime: str = "sideways"
    confidence: float = 0.0
    probabilities: dict[str, float] = field(default_factory=dict)
    duration: int = 0
    method: str = "hmm"

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.7

    @property
    def is_crisis(self) -> bool:
        return self.regime == "crisis"


@dataclass
class RegimeSegment:
    """A contiguous period in a single regime."""
    regime: str
    start_idx: int
    end_idx: int
    length: int = 0
    avg_return: float = 0.0
    volatility: float = 0.0

    def __post_init__(self):
        if self.length == 0:
            self.length = self.end_idx - self.start_idx + 1


@dataclass
class RegimeHistory:
    """Time series of regime classifications."""
    regimes: list[str] = field(default_factory=list)
    probabilities: list[dict[str, float]] = field(default_factory=list)
    segments: list[RegimeSegment] = field(default_factory=list)
    method: str = "hmm"

    @property
    def n_observations(self) -> int:
        return len(self.regimes)

    @property
    def current_regime(self) -> str:
        return self.regimes[-1] if self.regimes else "sideways"

    @property
    def n_regime_changes(self) -> int:
        if len(self.regimes) < 2:
            return 0
        return sum(
            1 for i in range(1, len(self.regimes))
            if self.regimes[i] != self.regimes[i - 1]
        )


@dataclass
class TransitionMatrix:
    """Regime transition probability matrix."""
    states: list[str] = field(default_factory=list)
    matrix: list[list[float]] = field(default_factory=list)
    counts: list[list[int]] = field(default_factory=list)
    expected_durations: dict[str, float] = field(default_factory=dict)

    def get_probability(self, from_state: str, to_state: str) -> float:
        if from_state not in self.states or to_state not in self.states:
            return 0.0
        i = self.states.index(from_state)
        j = self.states.index(to_state)
        return self.matrix[i][j]

    def get_persistence(self, state: str) -> float:
        """Probability of staying in same state."""
        return self.get_probability(state, state)


@dataclass
class RegimeStats:
    """Conditional statistics for a regime."""
    regime: str
    count: int = 0
    avg_return: float = 0.0
    volatility: float = 0.0
    avg_duration: float = 0.0
    max_duration: int = 0
    frequency: float = 0.0


@dataclass
class RegimeAllocation:
    """Regime-conditional portfolio allocation."""
    regime: str
    confidence: float = 0.0
    weights: dict[str, float] = field(default_factory=dict)
    blended_weights: dict[str, float] = field(default_factory=dict)
    expected_return: float = 0.0
    expected_risk: float = 0.0

    @property
    def is_defensive(self) -> bool:
        return self.regime in ("bear", "crisis")
