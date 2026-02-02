"""Crowding Analysis Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class CrowdingLevel(Enum):
    """Position crowding risk level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class SqueezeRisk(Enum):
    """Short squeeze risk level."""
    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"


class ConsensusRating(Enum):
    """Analyst consensus rating."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class OverlapMethod(Enum):
    """Fund overlap computation method."""
    JACCARD = "jaccard"
    COSINE = "cosine"


@dataclass
class DetectorConfig:
    """Crowding detection configuration."""
    high_threshold: float = 0.70  # crowding score for "high"
    extreme_threshold: float = 0.85  # crowding score for "extreme"
    medium_threshold: float = 0.50
    momentum_window: int = 4  # quarters
    min_holders: int = 5


@dataclass
class OverlapConfig:
    """Overlap analysis configuration."""
    method: OverlapMethod = OverlapMethod.JACCARD
    min_overlap_pct: float = 0.10  # 10% minimum to flag
    top_crowded_count: int = 20
    min_fund_size: float = 1e8  # $100M minimum AUM


@dataclass
class ShortInterestConfig:
    """Short interest configuration."""
    high_si_threshold: float = 0.20  # 20% of float
    squeeze_dtc_threshold: float = 5.0  # days-to-cover
    squeeze_si_threshold: float = 0.25  # 25% of float
    momentum_window: int = 10  # days
    ctb_elevated_threshold: float = 0.10  # 10% annualized


@dataclass
class ConsensusConfig:
    """Consensus analysis configuration."""
    divergence_threshold: float = 1.5  # std devs
    revision_window: int = 30  # days
    contrarian_threshold: float = 0.80  # 80%+ agreement = potential contrarian
    min_analysts: int = 5


@dataclass
class CrowdingConfig:
    """Top-level crowding configuration."""
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    overlap: OverlapConfig = field(default_factory=OverlapConfig)
    short_interest: ShortInterestConfig = field(default_factory=ShortInterestConfig)
    consensus: ConsensusConfig = field(default_factory=ConsensusConfig)


DEFAULT_DETECTOR_CONFIG = DetectorConfig()
DEFAULT_OVERLAP_CONFIG = OverlapConfig()
DEFAULT_SHORT_INTEREST_CONFIG = ShortInterestConfig()
DEFAULT_CONSENSUS_CONFIG = ConsensusConfig()
DEFAULT_CONFIG = CrowdingConfig()
