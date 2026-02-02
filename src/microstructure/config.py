"""Market Microstructure Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class TradeClassification(Enum):
    """Trade classification method."""
    LEE_READY = "lee_ready"
    TICK_TEST = "tick_test"
    BULK_VOLUME = "bulk_volume"


class SpreadType(Enum):
    """Spread computation type."""
    QUOTED = "quoted"
    EFFECTIVE = "effective"
    REALIZED = "realized"


class ImpactModel(Enum):
    """Price impact model type."""
    LINEAR = "linear"
    SQUARE_ROOT = "square_root"
    ALMGREN_CHRISS = "almgren_chriss"


class BookSide(Enum):
    """Order book side."""
    BID = "bid"
    ASK = "ask"


@dataclass
class SpreadConfig:
    """Spread analysis configuration."""
    min_tick_size: float = 0.01
    realized_spread_delay: int = 5  # minutes
    ewma_halflife: int = 20  # periods for EWMA smoothing
    roll_window: int = 60  # periods for Roll estimator
    min_trades: int = 10


@dataclass
class OrderBookConfig:
    """Order book analysis configuration."""
    depth_levels: int = 10
    imbalance_levels: int = 5  # levels for imbalance calc
    resilience_window: int = 30  # seconds
    snapshot_interval: int = 60  # seconds
    min_depth: float = 100.0  # minimum shares at level


@dataclass
class TickConfig:
    """Tick analysis configuration."""
    classification_method: TradeClassification = TradeClassification.LEE_READY
    vwap_window: int = 390  # minutes (full trading day)
    min_ticks: int = 50
    size_buckets: list[int] = field(default_factory=lambda: [100, 500, 1000, 5000, 10000])
    tick_trade_window: int = 60  # seconds for tick-to-trade ratio


@dataclass
class ImpactConfig:
    """Price impact estimation configuration."""
    model: ImpactModel = ImpactModel.SQUARE_ROOT
    temporary_decay: float = 0.5  # decay rate for temporary impact
    volatility_window: int = 20  # periods for vol estimation
    adv_window: int = 20  # periods for ADV estimation
    participation_rate: float = 0.05  # default 5% of volume


@dataclass
class MicrostructureConfig:
    """Top-level microstructure configuration."""
    spread: SpreadConfig = field(default_factory=SpreadConfig)
    orderbook: OrderBookConfig = field(default_factory=OrderBookConfig)
    tick: TickConfig = field(default_factory=TickConfig)
    impact: ImpactConfig = field(default_factory=ImpactConfig)


DEFAULT_SPREAD_CONFIG = SpreadConfig()
DEFAULT_ORDERBOOK_CONFIG = OrderBookConfig()
DEFAULT_TICK_CONFIG = TickConfig()
DEFAULT_IMPACT_CONFIG = ImpactConfig()
DEFAULT_CONFIG = MicrostructureConfig()
