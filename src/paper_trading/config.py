"""Paper Trading Configuration.

Session, data feed, strategy, and performance tracking settings.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class SessionStatus(str, Enum):
    """Paper trading session lifecycle states."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DataFeedType(str, Enum):
    """Market data feed sources."""
    SIMULATED = "simulated"
    HISTORICAL_REPLAY = "historical_replay"
    RANDOM_WALK = "random_walk"


class RebalanceSchedule(str, Enum):
    """Rebalance frequency for automated strategies."""
    MANUAL = "manual"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class StrategyType(str, Enum):
    """Built-in strategy types."""
    MANUAL = "manual"
    EQUAL_WEIGHT = "equal_weight"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    FACTOR_BASED = "factor_based"
    CUSTOM = "custom"


class PerformancePeriod(str, Enum):
    """Performance reporting periods."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    TOTAL = "total"


@dataclass
class DataFeedConfig:
    """Data feed configuration."""
    feed_type: DataFeedType = DataFeedType.SIMULATED
    update_interval_seconds: float = 1.0
    volatility: float = 0.015  # Daily volatility for simulated feeds
    drift: float = 0.0004  # Daily drift for simulated feeds
    replay_speed: float = 1.0  # Multiplier for historical replay
    replay_start_date: date = field(default_factory=lambda: date(2024, 1, 1))
    replay_end_date: date = field(default_factory=lambda: date(2024, 12, 31))
    seed: int = 42


@dataclass
class StrategyConfig:
    """Strategy configuration."""
    strategy_type: StrategyType = StrategyType.MANUAL
    rebalance_schedule: RebalanceSchedule = RebalanceSchedule.MONTHLY
    max_positions: int = 20
    target_position_pct: float = 0.05  # 5% per position
    rebalance_threshold: float = 0.03  # 3% drift triggers rebalance
    stop_loss_pct: float = -0.15
    take_profit_pct: float = 0.30
    params: dict = field(default_factory=dict)


@dataclass
class SessionConfig:
    """Paper trading session configuration."""
    initial_capital: float = 100_000.0
    symbols: list[str] = field(default_factory=lambda: [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META",
    ])
    benchmark: str = "SPY"
    commission_per_share: float = 0.0
    slippage_bps: float = 2.0
    snapshot_interval_bars: int = 1  # Snapshot every N bars
    max_position_pct: float = 0.15
    max_sector_pct: float = 0.35
    data_feed: DataFeedConfig = field(default_factory=DataFeedConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)


DEFAULT_SESSION_CONFIG = SessionConfig()
DEFAULT_DATA_FEED_CONFIG = DataFeedConfig()
DEFAULT_STRATEGY_CONFIG = StrategyConfig()
