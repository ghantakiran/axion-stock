"""Correlation Analysis Configuration.

Enums and configuration dataclasses for correlation computation,
regime detection, and diversification analysis.
"""

from dataclasses import dataclass, field
from enum import Enum


class CorrelationMethod(str, Enum):
    """Correlation computation method."""
    PEARSON = "pearson"
    SPEARMAN = "spearman"
    KENDALL = "kendall"


class RegimeType(str, Enum):
    """Correlation regime classification."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRISIS = "crisis"


class DiversificationLevel(str, Enum):
    """Portfolio diversification quality."""
    POOR = "poor"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"


class WindowType(str, Enum):
    """Rolling window type."""
    FIXED = "fixed"
    EXPANDING = "expanding"
    EXPONENTIAL = "exponential"


# Standard window sizes
STANDARD_WINDOWS = {
    "1M": 21,
    "3M": 63,
    "6M": 126,
    "1Y": 252,
}


@dataclass
class CorrelationConfig:
    """Configuration for correlation computation."""
    method: CorrelationMethod = CorrelationMethod.PEARSON
    min_periods: int = 20
    handle_missing: str = "pairwise"  # pairwise or dropna


@dataclass
class RollingConfig:
    """Configuration for rolling correlations."""
    window: int = 63  # 3 months
    window_type: WindowType = WindowType.FIXED
    half_life: int = 30  # For exponential weighting
    min_periods: int = 20


@dataclass
class RegimeConfig:
    """Configuration for correlation regime detection."""
    lookback: int = 252
    low_threshold: float = 0.25
    normal_threshold: float = 0.45
    high_threshold: float = 0.65
    change_threshold: float = 0.15  # Significant correlation shift


@dataclass
class DiversificationConfig:
    """Configuration for diversification scoring."""
    excellent_threshold: float = 1.5  # Diversification ratio
    good_threshold: float = 1.3
    fair_threshold: float = 1.1
    max_pair_correlation: float = 0.70  # Flag pairs above this


@dataclass
class CorrelationAnalysisConfig:
    """Top-level configuration."""
    correlation: CorrelationConfig = field(default_factory=CorrelationConfig)
    rolling: RollingConfig = field(default_factory=RollingConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    diversification: DiversificationConfig = field(default_factory=DiversificationConfig)


DEFAULT_CORRELATION_CONFIG = CorrelationConfig()
DEFAULT_ROLLING_CONFIG = RollingConfig()
DEFAULT_REGIME_CONFIG = RegimeConfig()
DEFAULT_DIVERSIFICATION_CONFIG = DiversificationConfig()
DEFAULT_CONFIG = CorrelationAnalysisConfig()
