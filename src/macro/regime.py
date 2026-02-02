"""Macro Regime Detection.

Classifies economic regimes using indicator consensus
and transition probability estimation.
"""

import logging
from typing import Optional

import numpy as np

from src.macro.config import RegimeConfig, RegimeType, DEFAULT_REGIME_CONFIG
from src.macro.models import EconomicIndicator, IndicatorSummary, RegimeState

logger = logging.getLogger(__name__)


class RegimeDetector:
    """Detects macro economic regimes."""

    def __init__(self, config: Optional[RegimeConfig] = None) -> None:
        self.config = config or DEFAULT_REGIME_CONFIG
        self._history: list[RegimeState] = []

    def detect(
        self,
        indicator_summary: IndicatorSummary,
        growth_score: float = 0.0,
        inflation_score: float = 0.0,
    ) -> RegimeState:
        """Detect current macro regime.

        Args:
            indicator_summary: Aggregated indicator summary.
            growth_score: Growth factor score (-1 to 1).
            inflation_score: Inflation factor score (-1 to 1).

        Returns:
            RegimeState with regime and confidence.
        """
        # Classify regime from growth/inflation quadrant
        regime = self._classify_regime(growth_score, inflation_score)

        # Compute probability from indicator breadth and scores
        probability = self._compute_probability(
            indicator_summary, growth_score, inflation_score, regime
        )

        # Consensus: how many indicators agree
        consensus = indicator_summary.breadth if regime in (
            RegimeType.EXPANSION, RegimeType.RECOVERY
        ) else 1.0 - indicator_summary.breadth

        # Duration
        duration = self._compute_duration(regime)

        # Transition probabilities
        transition_probs = self._estimate_transitions(regime)

        state = RegimeState(
            regime=regime,
            probability=round(probability, 4),
            duration=duration,
            transition_probs=transition_probs,
            indicator_consensus=round(consensus, 4),
        )

        self._history.append(state)
        return state

    def _classify_regime(
        self, growth: float, inflation: float
    ) -> RegimeType:
        """Classify regime from growth-inflation quadrant.

        High growth + Low inflation  -> Expansion (Goldilocks)
        High growth + High inflation -> Slowdown (Overheating)
        Low growth  + High inflation -> Contraction (Stagflation)
        Low growth  + Low inflation  -> Recovery (Reflation)
        """
        if growth >= 0 and inflation < 0:
            return RegimeType.EXPANSION
        elif growth >= 0 and inflation >= 0:
            return RegimeType.SLOWDOWN
        elif growth < 0 and inflation >= 0:
            return RegimeType.CONTRACTION
        else:
            return RegimeType.RECOVERY

    def _compute_probability(
        self,
        summary: IndicatorSummary,
        growth: float,
        inflation: float,
        regime: RegimeType,
    ) -> float:
        """Compute confidence probability for detected regime.

        Uses strength of growth/inflation signals and indicator breadth.
        """
        # Signal strength: how far from zero the scores are
        signal_strength = (abs(growth) + abs(inflation)) / 2

        # Indicator support
        if regime in (RegimeType.EXPANSION, RegimeType.RECOVERY):
            indicator_support = summary.breadth
        else:
            indicator_support = 1.0 - summary.breadth

        # Composite probability
        prob = 0.5 * signal_strength + 0.3 * indicator_support + 0.2 * abs(summary.composite_index)
        return float(np.clip(prob, 0.0, 1.0))

    def _compute_duration(self, regime: RegimeType) -> int:
        """Compute how many consecutive months in the same regime."""
        if not self._history:
            return 1

        duration = 1
        for state in reversed(self._history):
            if state.regime == regime:
                duration += 1
            else:
                break

        return duration

    def _estimate_transitions(
        self, current: RegimeType
    ) -> dict[RegimeType, float]:
        """Estimate transition probabilities from historical patterns.

        Uses empirical frequencies with smoothing.
        """
        n_regimes = len(RegimeType)
        smooth = self.config.transition_smoothing

        if len(self._history) < 2:
            # Uniform prior
            base = 1.0 / n_regimes
            return {r: round(base, 4) for r in RegimeType}

        # Count transitions from current regime
        counts = {r: smooth for r in RegimeType}
        for i in range(1, len(self._history)):
            if self._history[i - 1].regime == current:
                counts[self._history[i].regime] += 1

        total = sum(counts.values())
        if total == 0:
            base = 1.0 / n_regimes
            return {r: round(base, 4) for r in RegimeType}

        return {r: round(c / total, 4) for r, c in counts.items()}

    def get_history(self) -> list[RegimeState]:
        return self._history

    def reset(self) -> None:
        self._history.clear()
