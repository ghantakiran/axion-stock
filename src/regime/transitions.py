"""Regime Transition Analyzer.

Computes empirical transition matrices, expected durations,
regime change detection, and conditional statistics.
"""

import logging
from typing import Optional

import numpy as np

from src.regime.config import TransitionConfig, RegimeType
from src.regime.models import TransitionMatrix, RegimeStats

logger = logging.getLogger(__name__)

DEFAULT_STATES = [
    RegimeType.BULL.value,
    RegimeType.BEAR.value,
    RegimeType.SIDEWAYS.value,
    RegimeType.CRISIS.value,
]


class RegimeTransitionAnalyzer:
    """Analyzes regime transitions and conditional statistics."""

    def __init__(self, config: Optional[TransitionConfig] = None) -> None:
        self.config = config or TransitionConfig()

    def compute_transition_matrix(
        self, regimes: list[str], states: Optional[list[str]] = None
    ) -> TransitionMatrix:
        """Compute empirical transition probability matrix.

        Args:
            regimes: Ordered list of regime labels.
            states: Optional list of state names (default: 4 canonical).

        Returns:
            TransitionMatrix.
        """
        if states is None:
            states = sorted(set(regimes)) if regimes else DEFAULT_STATES

        n = len(states)
        state_idx = {s: i for i, s in enumerate(states)}
        counts = [[0] * n for _ in range(n)]

        for t in range(len(regimes) - 1):
            from_s = regimes[t]
            to_s = regimes[t + 1]
            if from_s in state_idx and to_s in state_idx:
                counts[state_idx[from_s]][state_idx[to_s]] += 1

        # Add Laplace smoothing
        alpha = self.config.smoothing_alpha
        matrix = []
        for i in range(n):
            row_total = sum(counts[i]) + alpha * n
            if row_total > 0:
                row = [round((counts[i][j] + alpha) / row_total, 4) for j in range(n)]
            else:
                row = [round(1.0 / n, 4)] * n
            matrix.append(row)

        # Expected durations: 1 / (1 - P(stay))
        expected_durations = {}
        for i, state in enumerate(states):
            p_stay = matrix[i][i]
            expected_durations[state] = round(1.0 / (1.0 - p_stay), 1) if p_stay < 1.0 else 999.0

        return TransitionMatrix(
            states=states,
            matrix=matrix,
            counts=counts,
            expected_durations=expected_durations,
        )

    def regime_stats(
        self, regimes: list[str], returns: list[float]
    ) -> list[RegimeStats]:
        """Compute conditional statistics per regime.

        Args:
            regimes: Regime labels aligned with returns.
            returns: Return series.

        Returns:
            List of RegimeStats.
        """
        if len(regimes) != len(returns):
            min_len = min(len(regimes), len(returns))
            regimes = regimes[:min_len]
            returns = returns[:min_len]

        states = sorted(set(regimes))
        total = len(regimes)
        results = []

        for state in states:
            indices = [i for i, r in enumerate(regimes) if r == state]
            state_returns = [returns[i] for i in indices]
            count = len(indices)

            # Compute durations of contiguous segments
            durations = []
            run = 0
            for i in range(len(regimes)):
                if regimes[i] == state:
                    run += 1
                else:
                    if run > 0:
                        durations.append(run)
                    run = 0
            if run > 0:
                durations.append(run)

            results.append(RegimeStats(
                regime=state,
                count=count,
                avg_return=round(float(np.mean(state_returns)), 6) if state_returns else 0.0,
                volatility=round(float(np.std(state_returns, ddof=1)), 6) if len(state_returns) > 1 else 0.0,
                avg_duration=round(float(np.mean(durations)), 1) if durations else 0.0,
                max_duration=max(durations) if durations else 0,
                frequency=round(count / total, 4) if total > 0 else 0.0,
            ))

        return results

    def detect_changes(self, regimes: list[str]) -> list[int]:
        """Find indices where regime changes occur.

        Returns:
            List of indices where regime[i] != regime[i-1].
        """
        changes = []
        for i in range(1, len(regimes)):
            if regimes[i] != regimes[i - 1]:
                changes.append(i)
        return changes

    def forecast_regime(
        self,
        current_regime: str,
        transition_matrix: TransitionMatrix,
        horizon: int = 5,
    ) -> list[dict[str, float]]:
        """Forecast regime probabilities over a horizon.

        Uses matrix exponentiation: P(t+h) = P^h.

        Args:
            current_regime: Current regime label.
            transition_matrix: Fitted transition matrix.
            horizon: Number of steps to forecast.

        Returns:
            List of probability dicts, one per step.
        """
        states = transition_matrix.states
        if current_regime not in states:
            return [
                {s: round(1.0 / len(states), 4) for s in states}
                for _ in range(horizon)
            ]

        idx = states.index(current_regime)
        mat = np.array(transition_matrix.matrix)
        results = []

        # Start with 1-hot vector for current regime
        state_vec = np.zeros(len(states))
        state_vec[idx] = 1.0

        for _ in range(horizon):
            state_vec = state_vec @ mat
            probs = {
                states[k]: round(float(state_vec[k]), 4)
                for k in range(len(states))
            }
            results.append(probs)

        return results
