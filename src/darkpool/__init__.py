"""Dark Pool Analytics Module.

Dark pool volume tracking, print analysis, block trade
detection, and hidden liquidity estimation.

Example:
    from src.darkpool import VolumeTracker, BlockDetector

    tracker = VolumeTracker()
    tracker.add_records(records)
    summary = tracker.summarize("AAPL")
    print(f"Dark share: {summary.avg_dark_share:.1%}")

    detector = BlockDetector()
    blocks = detector.detect(prints, adv=1_000_000, symbol="AAPL")
    print(f"Found {len(blocks)} blocks")
"""

from src.darkpool.config import (
    PrintType,
    BlockDirection,
    LiquidityLevel,
    VenueTier,
    VolumeConfig,
    PrintConfig,
    BlockConfig,
    LiquidityConfig,
    DarkPoolConfig,
    DEFAULT_VOLUME_CONFIG,
    DEFAULT_PRINT_CONFIG,
    DEFAULT_BLOCK_CONFIG,
    DEFAULT_LIQUIDITY_CONFIG,
    DEFAULT_CONFIG,
)

from src.darkpool.models import (
    DarkPoolVolume,
    VolumeSummary,
    DarkPrint,
    PrintSummary,
    DarkBlock,
    DarkLiquidity,
)

from src.darkpool.volume import VolumeTracker
from src.darkpool.prints import PrintAnalyzer
from src.darkpool.blocks import BlockDetector
from src.darkpool.liquidity import LiquidityEstimator

__all__ = [
    # Config
    "PrintType",
    "BlockDirection",
    "LiquidityLevel",
    "VenueTier",
    "VolumeConfig",
    "PrintConfig",
    "BlockConfig",
    "LiquidityConfig",
    "DarkPoolConfig",
    "DEFAULT_VOLUME_CONFIG",
    "DEFAULT_PRINT_CONFIG",
    "DEFAULT_BLOCK_CONFIG",
    "DEFAULT_LIQUIDITY_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "DarkPoolVolume",
    "VolumeSummary",
    "DarkPrint",
    "PrintSummary",
    "DarkBlock",
    "DarkLiquidity",
    # Components
    "VolumeTracker",
    "PrintAnalyzer",
    "BlockDetector",
    "LiquidityEstimator",
]
