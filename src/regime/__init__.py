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
from src.regime.signal_adapter import (
    RawSignal,
    AdaptedSignal,
    AdaptedSignalSet,
    RegimeSignalAdapter,
)
from src.regime.threshold_manager import (
    ThresholdSet,
    ThresholdComparison,
    SignalDecision,
    DynamicThresholdManager,
)
from src.regime.ensemble import (
    MethodResult,
    EnsembleResult,
    EnsembleComparison,
    RegimeEnsemble,
)
from src.regime.regime_signals import (
    TransitionSignal,
    PersistenceSignal,
    AlignmentSignal,
    DivergenceSignal,
    RegimeSignalSummary,
    RegimeSignalGenerator,
)

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
    # Signal Adapter (PRD-61)
    "RawSignal",
    "AdaptedSignal",
    "AdaptedSignalSet",
    "RegimeSignalAdapter",
    # Threshold Manager (PRD-61)
    "ThresholdSet",
    "ThresholdComparison",
    "SignalDecision",
    "DynamicThresholdManager",
    # Ensemble (PRD-61)
    "MethodResult",
    "EnsembleResult",
    "EnsembleComparison",
    "RegimeEnsemble",
    # Regime Signals (PRD-61)
    "TransitionSignal",
    "PersistenceSignal",
    "AlignmentSignal",
    "DivergenceSignal",
    "RegimeSignalSummary",
    "RegimeSignalGenerator",
]
