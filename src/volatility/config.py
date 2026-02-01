"""Volatility Analysis Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class VolMethod(str, Enum):
    """Volatility estimation method."""
    HISTORICAL = "historical"
    EWMA = "ewma"
    PARKINSON = "parkinson"
    GARMAN_KLASS = "garman_klass"


class VolRegime(str, Enum):
    """Volatility regime classification."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


class VolTimeframe(str, Enum):
    """Volatility measurement timeframe."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class SurfaceInterpolation(str, Enum):
    """Surface interpolation method."""
    LINEAR = "linear"
    CUBIC = "cubic"


# Standard windows in trading days
STANDARD_WINDOWS: dict[str, int] = {
    "1W": 5,
    "2W": 10,
    "1M": 21,
    "2M": 42,
    "3M": 63,
    "6M": 126,
    "1Y": 252,
}


@dataclass(frozen=True)
class VolConfig:
    """Core volatility computation configuration."""
    default_window: int = 21
    annualization_factor: float = 252.0
    ewma_lambda: float = 0.94
    min_periods: int = 10
    cone_percentiles: tuple[float, ...] = (5.0, 25.0, 50.0, 75.0, 95.0)
    cone_windows: tuple[int, ...] = (5, 10, 21, 42, 63, 126, 252)


@dataclass(frozen=True)
class TermStructureConfig:
    """Term structure analysis configuration."""
    tenor_days: tuple[int, ...] = (5, 10, 21, 42, 63, 126, 252)
    contango_threshold: float = 0.01
    backwardation_threshold: float = -0.01


@dataclass(frozen=True)
class SurfaceConfig:
    """Volatility surface configuration."""
    moneyness_range: tuple[float, float] = (0.80, 1.20)
    moneyness_step: float = 0.05
    interpolation: SurfaceInterpolation = SurfaceInterpolation.LINEAR
    skew_delta: float = 0.25


@dataclass(frozen=True)
class RegimeConfig:
    """Volatility regime detection configuration."""
    lookback_window: int = 252
    low_threshold: float = -1.0
    high_threshold: float = 1.0
    extreme_threshold: float = 2.0
    min_regime_days: int = 5


@dataclass(frozen=True)
class VolAnalysisConfig:
    """Complete volatility analysis configuration."""
    vol: VolConfig = field(default_factory=VolConfig)
    term_structure: TermStructureConfig = field(default_factory=TermStructureConfig)
    surface: SurfaceConfig = field(default_factory=SurfaceConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)


DEFAULT_VOL_CONFIG = VolConfig()
DEFAULT_TERM_STRUCTURE_CONFIG = TermStructureConfig()
DEFAULT_SURFACE_CONFIG = SurfaceConfig()
DEFAULT_REGIME_CONFIG = RegimeConfig()
DEFAULT_CONFIG = VolAnalysisConfig()
