"""Regime Detection Module.

Market regime classification using rule-based detection, Hidden Markov Models,
and clustering. Includes regime transition analysis and regime-aware allocation.

Example:
    from src.regime import GaussianHMM, ClusterRegimeClassifier, RegimeAllocator

    hmm = GaussianHMM()
    state = hmm.detect(returns, volatilities)
    print(f"Regime: {state.regime} ({state.confidence:.0%})")

    allocator = RegimeAllocator()
    alloc = allocator.allocate(state.regime, state.confidence, state.probabilities)
"""

from src.regime.detector import RegimeDetector, MarketRegime
from src.regime.weights import AdaptiveWeights, REGIME_WEIGHTS

from src.regime.config import (
    RegimeType,
    DetectionMethod,
    ClusterMethod,
    FeatureSet,
    HMMConfig,
    ClusterConfig,
    TransitionConfig,
    AllocationConfig,
)

from src.regime.models import (
    RegimeState,
    RegimeSegment,
    RegimeHistory,
    TransitionMatrix,
    RegimeStats,
    RegimeAllocation,
)

from src.regime.hmm import GaussianHMM
from src.regime.clustering import ClusterRegimeClassifier
from src.regime.transitions import RegimeTransitionAnalyzer
from src.regime.allocation import RegimeAllocator

__all__ = [
    # Existing (PRD-02)
    "RegimeDetector",
    "MarketRegime",
    "AdaptiveWeights",
    "REGIME_WEIGHTS",
    # Config (PRD-55)
    "RegimeType",
    "DetectionMethod",
    "ClusterMethod",
    "FeatureSet",
    "HMMConfig",
    "ClusterConfig",
    "TransitionConfig",
    "AllocationConfig",
    # Models (PRD-55)
    "RegimeState",
    "RegimeSegment",
    "RegimeHistory",
    "TransitionMatrix",
    "RegimeStats",
    "RegimeAllocation",
    # Components (PRD-55)
    "GaussianHMM",
    "ClusterRegimeClassifier",
    "RegimeTransitionAnalyzer",
    "RegimeAllocator",
]
