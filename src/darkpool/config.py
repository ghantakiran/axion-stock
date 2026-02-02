"""Dark Pool Analytics Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class PrintType(Enum):
    """Dark print classification."""
    BLOCK = "block"
    MIDPOINT = "midpoint"
    RETAIL = "retail"
    INSTITUTIONAL = "institutional"
    UNKNOWN = "unknown"


class BlockDirection(Enum):
    """Inferred block trade direction."""
    BUY = "buy"
    SELL = "sell"
    UNKNOWN = "unknown"


class LiquidityLevel(Enum):
    """Dark pool liquidity level."""
    DEEP = "deep"
    MODERATE = "moderate"
    SHALLOW = "shallow"
    DRY = "dry"


class VenueTier(Enum):
    """Dark pool venue tier."""
    MAJOR = "major"
    MID = "mid"
    MINOR = "minor"


@dataclass
class VolumeConfig:
    """Volume tracking configuration."""
    lookback_days: int = 20
    dark_share_warning: float = 0.45  # warn if dark > 45%
    momentum_window: int = 5
    min_volume: int = 1000  # minimum shares to track
    short_volume_threshold: float = 0.50  # short > 50% is elevated


@dataclass
class PrintConfig:
    """Print analysis configuration."""
    block_threshold: int = 10000  # shares for block classification
    retail_max_size: int = 200  # max shares for retail print
    midpoint_tolerance: float = 0.001  # within 0.1% of midpoint
    min_prints: int = 10


@dataclass
class BlockConfig:
    """Block detection configuration."""
    min_block_size: int = 10000  # shares
    min_block_value: float = 200_000  # dollars
    adv_ratio_threshold: float = 0.01  # 1% of ADV
    cluster_window: int = 300  # seconds for clustering
    cluster_min_blocks: int = 3


@dataclass
class LiquidityConfig:
    """Liquidity estimation configuration."""
    depth_levels: list[int] = field(default_factory=lambda: [
        1000, 5000, 10000, 50000, 100000,
    ])
    fill_rate_window: int = 20  # days
    score_weights: dict = field(default_factory=lambda: {
        "volume_share": 0.3,
        "fill_rate": 0.3,
        "depth": 0.2,
        "consistency": 0.2,
    })
    deep_threshold: float = 0.7
    moderate_threshold: float = 0.4
    shallow_threshold: float = 0.2


@dataclass
class DarkPoolConfig:
    """Top-level dark pool configuration."""
    volume: VolumeConfig = field(default_factory=VolumeConfig)
    prints: PrintConfig = field(default_factory=PrintConfig)
    blocks: BlockConfig = field(default_factory=BlockConfig)
    liquidity: LiquidityConfig = field(default_factory=LiquidityConfig)


DEFAULT_VOLUME_CONFIG = VolumeConfig()
DEFAULT_PRINT_CONFIG = PrintConfig()
DEFAULT_BLOCK_CONFIG = BlockConfig()
DEFAULT_LIQUIDITY_CONFIG = LiquidityConfig()
DEFAULT_CONFIG = DarkPoolConfig()
