"""Order Flow Analysis Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class FlowSignal(str, Enum):
    """Order flow signal strength."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class ImbalanceType(str, Enum):
    """Order book imbalance classification."""
    BID_HEAVY = "bid_heavy"
    ASK_HEAVY = "ask_heavy"
    BALANCED = "balanced"


class BlockSize(str, Enum):
    """Block trade size classification."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    INSTITUTIONAL = "institutional"


class PressureDirection(str, Enum):
    """Buy/sell pressure direction."""
    BUYING = "buying"
    SELLING = "selling"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class ImbalanceConfig:
    """Order book imbalance configuration."""
    bid_heavy_threshold: float = 1.5
    ask_heavy_threshold: float = 0.67
    signal_threshold: float = 2.0
    strong_signal_threshold: float = 3.0
    smoothing_window: int = 5


@dataclass(frozen=True)
class BlockConfig:
    """Block trade detection configuration."""
    medium_threshold: int = 10_000
    large_threshold: int = 50_000
    institutional_threshold: int = 100_000
    institutional_dollar_threshold: float = 1_000_000.0


@dataclass(frozen=True)
class PressureConfig:
    """Buy/sell pressure configuration."""
    window: int = 20
    smoothing_window: int = 5
    strong_buying_threshold: float = 1.5
    strong_selling_threshold: float = 0.67
    neutral_band: float = 0.1


@dataclass(frozen=True)
class OrderFlowConfig:
    """Complete order flow configuration."""
    imbalance: ImbalanceConfig = field(default_factory=ImbalanceConfig)
    block: BlockConfig = field(default_factory=BlockConfig)
    pressure: PressureConfig = field(default_factory=PressureConfig)


DEFAULT_IMBALANCE_CONFIG = ImbalanceConfig()
DEFAULT_BLOCK_CONFIG = BlockConfig()
DEFAULT_PRESSURE_CONFIG = PressureConfig()
DEFAULT_CONFIG = OrderFlowConfig()
