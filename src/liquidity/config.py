"""Liquidity Analysis Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class LiquidityLevel(str, Enum):
    """Liquidity quality classification."""
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class ImpactModel(str, Enum):
    """Market impact estimation model."""
    LINEAR = "linear"
    SQUARE_ROOT = "square_root"


class SpreadType(str, Enum):
    """Spread measurement type."""
    ABSOLUTE = "absolute"
    RELATIVE = "relative"
    EFFECTIVE = "effective"


class VolumeProfile(str, Enum):
    """Intraday volume profile shape."""
    U_SHAPE = "u_shape"
    J_SHAPE = "j_shape"
    FLAT = "flat"
    IRREGULAR = "irregular"


@dataclass(frozen=True)
class SpreadConfig:
    """Spread analysis configuration."""
    outlier_percentile: float = 99.0
    min_observations: int = 10
    effective_spread_window: int = 20


@dataclass(frozen=True)
class VolumeConfig:
    """Volume analysis configuration."""
    window: int = 21
    vwap_window: int = 1
    low_volume_threshold: float = 0.5
    high_volume_threshold: float = 2.0
    min_observations: int = 10


@dataclass(frozen=True)
class ImpactConfig:
    """Market impact estimation configuration."""
    model: ImpactModel = ImpactModel.SQUARE_ROOT
    impact_coefficient: float = 0.1
    max_participation_rate: float = 0.10
    default_volatility: float = 0.02
    spread_cost_multiplier: float = 0.5


@dataclass(frozen=True)
class ScoringConfig:
    """Liquidity scoring configuration."""
    spread_weight: float = 0.35
    volume_weight: float = 0.40
    impact_weight: float = 0.25
    very_high_threshold: float = 80.0
    high_threshold: float = 60.0
    medium_threshold: float = 40.0
    low_threshold: float = 20.0


@dataclass(frozen=True)
class LiquidityConfig:
    """Complete liquidity analysis configuration."""
    spread: SpreadConfig = field(default_factory=SpreadConfig)
    volume: VolumeConfig = field(default_factory=VolumeConfig)
    impact: ImpactConfig = field(default_factory=ImpactConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)


DEFAULT_SPREAD_CONFIG = SpreadConfig()
DEFAULT_VOLUME_CONFIG = VolumeConfig()
DEFAULT_IMPACT_CONFIG = ImpactConfig()
DEFAULT_SCORING_CONFIG = ScoringConfig()
DEFAULT_CONFIG = LiquidityConfig()
