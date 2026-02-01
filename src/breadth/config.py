"""Market Breadth Configuration.

Enums and configuration dataclasses for breadth indicators,
market health scoring, and sector breadth analysis.
"""

from dataclasses import dataclass, field
from enum import Enum


class BreadthIndicator(str, Enum):
    """Breadth indicator types."""
    ADVANCE_DECLINE = "advance_decline"
    NEW_HIGHS_LOWS = "new_highs_lows"
    MCCLELLAN_OSCILLATOR = "mcclellan_oscillator"
    MCCLELLAN_SUMMATION = "mcclellan_summation"
    BREADTH_THRUST = "breadth_thrust"
    UP_DOWN_VOLUME = "up_down_volume"
    PERCENT_ABOVE_MA = "percent_above_ma"


class MarketHealthLevel(str, Enum):
    """Market health classification."""
    VERY_BEARISH = "very_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    VERY_BULLISH = "very_bullish"


class BreadthSignal(str, Enum):
    """Breadth signal types."""
    BULLISH_DIVERGENCE = "bullish_divergence"
    BEARISH_DIVERGENCE = "bearish_divergence"
    BREADTH_THRUST = "breadth_thrust"
    OVERBOUGHT = "overbought"
    OVERSOLD = "oversold"
    ZERO_CROSS_UP = "zero_cross_up"
    ZERO_CROSS_DOWN = "zero_cross_down"
    NEW_HIGH_POLE = "new_high_pole"
    NEW_LOW_POLE = "new_low_pole"


class BreadthTimeframe(str, Enum):
    """Timeframe for breadth analysis."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# GICS sectors for sector breadth
GICS_SECTORS = [
    "Technology",
    "Healthcare",
    "Financials",
    "Consumer Discretionary",
    "Communication Services",
    "Industrials",
    "Consumer Staples",
    "Energy",
    "Utilities",
    "Real Estate",
    "Materials",
]


@dataclass
class McClellanConfig:
    """McClellan Oscillator configuration."""
    fast_period: int = 19
    slow_period: int = 39
    overbought: float = 100.0
    oversold: float = -100.0


@dataclass
class ThrustConfig:
    """Breadth thrust detection configuration."""
    ema_period: int = 10
    low_threshold: float = 0.40
    high_threshold: float = 0.615
    lookback_days: int = 10


@dataclass
class HealthConfig:
    """Market health scoring configuration."""
    ad_weight: float = 0.25
    nhnl_weight: float = 0.20
    mcclellan_weight: float = 0.25
    thrust_weight: float = 0.15
    volume_weight: float = 0.15
    very_bullish_threshold: float = 80.0
    bullish_threshold: float = 60.0
    neutral_threshold: float = 40.0
    bearish_threshold: float = 20.0


@dataclass
class NewHighsLowsConfig:
    """New highs/lows configuration."""
    lookback_period: int = 252  # 52 weeks
    ma_period: int = 10
    high_pole_threshold: int = 100
    low_pole_threshold: int = 100


@dataclass
class BreadthConfig:
    """Top-level breadth configuration."""
    mcclellan: McClellanConfig = field(default_factory=McClellanConfig)
    thrust: ThrustConfig = field(default_factory=ThrustConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    new_highs_lows: NewHighsLowsConfig = field(default_factory=NewHighsLowsConfig)
    timeframe: BreadthTimeframe = BreadthTimeframe.DAILY


DEFAULT_MCCLELLAN_CONFIG = McClellanConfig()
DEFAULT_THRUST_CONFIG = ThrustConfig()
DEFAULT_HEALTH_CONFIG = HealthConfig()
DEFAULT_NHNL_CONFIG = NewHighsLowsConfig()
DEFAULT_BREADTH_CONFIG = BreadthConfig()
