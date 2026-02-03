"""Regime Detection Configuration."""

from dataclasses import dataclass
from enum import Enum


class RegimeType(str, Enum):
    """Market regime classification."""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    CRISIS = "crisis"


class DetectionMethod(str, Enum):
    """Regime detection method."""
    RULE_BASED = "rule_based"
    HMM = "hmm"
    CLUSTERING = "clustering"


class ClusterMethod(str, Enum):
    """Clustering algorithm."""
    KMEANS = "kmeans"
    AGGLOMERATIVE = "agglomerative"


class FeatureSet(str, Enum):
    """Feature set for regime detection."""
    RETURNS_ONLY = "returns_only"
    RETURNS_VOL = "returns_vol"
    FULL = "full"


@dataclass(frozen=True)
class HMMConfig:
    """Hidden Markov Model configuration."""
    n_regimes: int = 4
    n_iterations: int = 100
    convergence_tol: float = 1e-4
    random_seed: int = 42
    min_observations: int = 60


@dataclass(frozen=True)
class ClusterConfig:
    """Clustering configuration."""
    method: ClusterMethod = ClusterMethod.KMEANS
    n_clusters: int = 4
    window_size: int = 21
    feature_set: FeatureSet = FeatureSet.RETURNS_VOL
    min_observations: int = 60


@dataclass(frozen=True)
class TransitionConfig:
    """Transition analysis configuration."""
    min_regime_length: int = 5
    smoothing_alpha: float = 0.01


@dataclass(frozen=True)
class AllocationConfig:
    """Regime-aware allocation configuration."""
    blend_with_probabilities: bool = True
    max_single_asset_weight: float = 0.40
    min_single_asset_weight: float = 0.0
    transition_smoothing: float = 0.3
