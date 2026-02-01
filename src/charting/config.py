"""Technical Charting Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class PatternType(str, Enum):
    """Chart pattern types."""
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    HEAD_AND_SHOULDERS = "head_and_shoulders"
    INVERSE_HEAD_AND_SHOULDERS = "inverse_head_and_shoulders"
    ASCENDING_TRIANGLE = "ascending_triangle"
    DESCENDING_TRIANGLE = "descending_triangle"
    FLAG = "flag"
    WEDGE = "wedge"


class TrendDirection(str, Enum):
    """Trend direction classification."""
    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"


class SRType(str, Enum):
    """Support/resistance level type."""
    SUPPORT = "support"
    RESISTANCE = "resistance"


class CrossoverType(str, Enum):
    """Moving average crossover type."""
    GOLDEN_CROSS = "golden_cross"
    DEATH_CROSS = "death_cross"


@dataclass(frozen=True)
class PatternConfig:
    """Pattern detection configuration."""
    min_pattern_bars: int = 10
    max_pattern_bars: int = 100
    price_tolerance: float = 0.02
    confirmation_bars: int = 2
    min_confidence: float = 0.5


@dataclass(frozen=True)
class TrendConfig:
    """Trend analysis configuration."""
    short_window: int = 20
    medium_window: int = 50
    long_window: int = 200
    min_r_squared: float = 0.3
    sideways_threshold: float = 0.001


@dataclass(frozen=True)
class SRConfig:
    """Support/resistance configuration."""
    lookback: int = 100
    pivot_window: int = 5
    zone_tolerance: float = 0.01
    min_touches: int = 2
    max_levels: int = 10


@dataclass(frozen=True)
class FibConfig:
    """Fibonacci configuration."""
    retracement_levels: tuple[float, ...] = (0.236, 0.382, 0.500, 0.618, 0.786)
    extension_levels: tuple[float, ...] = (1.000, 1.272, 1.618, 2.000, 2.618)
    swing_window: int = 10
    min_swing_pct: float = 0.05


@dataclass(frozen=True)
class ChartingConfig:
    """Complete charting configuration."""
    pattern: PatternConfig = field(default_factory=PatternConfig)
    trend: TrendConfig = field(default_factory=TrendConfig)
    sr: SRConfig = field(default_factory=SRConfig)
    fib: FibConfig = field(default_factory=FibConfig)


DEFAULT_PATTERN_CONFIG = PatternConfig()
DEFAULT_TREND_CONFIG = TrendConfig()
DEFAULT_SR_CONFIG = SRConfig()
DEFAULT_FIB_CONFIG = FibConfig()
DEFAULT_CONFIG = ChartingConfig()
