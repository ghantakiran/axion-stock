"""Multi-Method Regime Ensemble.

Combines regime classifications from HMM, clustering, and rule-based
detection into a consensus regime with higher confidence.  Supports
configurable method weights and tie-breaking rules.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.regime.config import RegimeType, HMMConfig, ClusterConfig
from src.regime.models import RegimeState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class MethodResult:
    """Result from a single detection method."""
    method: str = ""  # hmm, clustering, rule_based
    regime: str = ""
    confidence: float = 0.0
    probabilities: dict[str, float] = field(default_factory=dict)
    weight: float = 1.0

    @property
    def weighted_confidence(self) -> float:
        return self.confidence * self.weight


@dataclass
class EnsembleResult:
    """Consensus regime from ensemble of methods."""
    consensus_regime: str = ""
    consensus_confidence: float = 0.0
    consensus_probabilities: dict[str, float] = field(default_factory=dict)
    method_results: list[MethodResult] = field(default_factory=list)
    agreement_ratio: float = 0.0  # Fraction of methods agreeing
    n_methods: int = 0
    is_unanimous: bool = False

    @property
    def is_high_confidence(self) -> bool:
        return self.consensus_confidence >= 0.7

    @property
    def has_strong_agreement(self) -> bool:
        return self.agreement_ratio >= 0.67

    @property
    def dominant_method(self) -> str:
        if not self.method_results:
            return ""
        return max(
            self.method_results, key=lambda m: m.weighted_confidence
        ).method


@dataclass
class EnsembleComparison:
    """Comparison of individual methods vs ensemble."""
    ensemble: EnsembleResult = field(default_factory=EnsembleResult)
    method_agreement: dict[str, bool] = field(default_factory=dict)
    divergent_methods: list[str] = field(default_factory=list)
    confidence_spread: float = 0.0  # Max - min confidence

    @property
    def has_divergence(self) -> bool:
        return len(self.divergent_methods) > 0


# ---------------------------------------------------------------------------
# Ensemble Classifier
# ---------------------------------------------------------------------------
DEFAULT_METHOD_WEIGHTS = {
    "hmm": 0.40,
    "clustering": 0.30,
    "rule_based": 0.30,
}


class RegimeEnsemble:
    """Combines multiple regime detection methods into consensus."""

    def __init__(
        self,
        method_weights: Optional[dict[str, float]] = None,
        min_methods: int = 2,
    ) -> None:
        self.method_weights = method_weights or dict(DEFAULT_METHOD_WEIGHTS)
        self.min_methods = min_methods

    def combine(
        self,
        results: list[MethodResult],
    ) -> EnsembleResult:
        """Combine multiple method results into consensus.

        Uses weighted voting: each method votes for a regime weighted
        by its confidence and assigned method weight.

        Args:
            results: List of MethodResult from individual detectors.

        Returns:
            EnsembleResult with consensus regime.
        """
        if not results:
            return EnsembleResult()

        n = len(results)

        # Weight each method's probabilities
        all_regimes = set()
        for r in results:
            all_regimes.update(r.probabilities.keys())
            all_regimes.add(r.regime)

        if not all_regimes:
            all_regimes = {"bull", "bear", "sideways", "crisis"}

        # Aggregate weighted probabilities
        combined_probs: dict[str, float] = {r: 0.0 for r in all_regimes}
        total_weight = 0.0

        for r in results:
            w = r.weight
            if r.probabilities:
                for regime, prob in r.probabilities.items():
                    combined_probs[regime] = combined_probs.get(regime, 0.0) + prob * w
            else:
                # If no probabilities, use confidence for voted regime
                combined_probs[r.regime] = (
                    combined_probs.get(r.regime, 0.0) + r.confidence * w
                )
            total_weight += w

        # Normalize
        if total_weight > 0:
            for regime in combined_probs:
                combined_probs[regime] /= total_weight

        # Normalize to sum to 1
        prob_sum = sum(combined_probs.values())
        if prob_sum > 0:
            combined_probs = {
                r: round(p / prob_sum, 6) for r, p in combined_probs.items()
            }

        # Consensus regime = highest combined probability
        consensus = max(combined_probs, key=combined_probs.get)

        # Consensus confidence = combined probability of consensus regime
        consensus_conf = combined_probs.get(consensus, 0.0)

        # Agreement ratio
        agreeing = sum(1 for r in results if r.regime == consensus)
        agreement = agreeing / n if n > 0 else 0.0

        return EnsembleResult(
            consensus_regime=consensus,
            consensus_confidence=round(consensus_conf, 4),
            consensus_probabilities=combined_probs,
            method_results=results,
            agreement_ratio=round(agreement, 4),
            n_methods=n,
            is_unanimous=agreeing == n,
        )

    def combine_from_states(
        self,
        states: dict[str, RegimeState],
    ) -> EnsembleResult:
        """Combine RegimeState objects from different methods.

        Convenience wrapper that converts RegimeState dict to
        MethodResult list using configured method weights.

        Args:
            states: Dict of method_name -> RegimeState.

        Returns:
            EnsembleResult with consensus.
        """
        results = []
        for method, state in states.items():
            weight = self.method_weights.get(method, 0.33)
            results.append(MethodResult(
                method=method,
                regime=state.regime,
                confidence=state.confidence,
                probabilities=dict(state.probabilities),
                weight=weight,
            ))
        return self.combine(results)

    def compare_methods(
        self,
        results: list[MethodResult],
    ) -> EnsembleComparison:
        """Compare individual methods against ensemble consensus.

        Args:
            results: List of MethodResult.

        Returns:
            EnsembleComparison showing agreement/divergence.
        """
        ensemble = self.combine(results)

        agreement = {}
        divergent = []
        confidences = []

        for r in results:
            agrees = r.regime == ensemble.consensus_regime
            agreement[r.method] = agrees
            if not agrees:
                divergent.append(r.method)
            confidences.append(r.confidence)

        spread = (max(confidences) - min(confidences)) if confidences else 0.0

        return EnsembleComparison(
            ensemble=ensemble,
            method_agreement=agreement,
            divergent_methods=divergent,
            confidence_spread=round(spread, 4),
        )

    def weighted_regime_state(
        self,
        results: list[MethodResult],
    ) -> RegimeState:
        """Convert ensemble result to a RegimeState for downstream use.

        Args:
            results: List of MethodResult.

        Returns:
            RegimeState compatible with existing regime infrastructure.
        """
        ensemble = self.combine(results)
        return RegimeState(
            regime=ensemble.consensus_regime,
            confidence=ensemble.consensus_confidence,
            probabilities=ensemble.consensus_probabilities,
            duration=0,
            method="ensemble",
        )
