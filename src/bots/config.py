"""Trading Bots Configuration.

Enums, constants, and configuration for automated trading bots.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# =============================================================================
# Enums
# =============================================================================

class BotType(str, Enum):
    """Types of trading bots."""
    DCA = "dca"
    REBALANCE = "rebalance"
    SIGNAL = "signal"
    GRID = "grid"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"


class BotStatus(str, Enum):
    """Bot operational status."""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class ExecutionStatus(str, Enum):
    """Bot execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class ScheduleFrequency(str, Enum):
    """Schedule frequency options."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class ExecutionTime(str, Enum):
    """When to execute during the day."""
    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"
    MIDDAY = "midday"
    CUSTOM = "custom"


class OrderType(str, Enum):
    """Order types for bot execution."""
    MARKET = "market"
    LIMIT = "limit"
    LIMIT_IOC = "limit_ioc"  # Immediate or cancel


class SignalType(str, Enum):
    """Signal types for signal bots."""
    PRICE_CROSS_MA = "price_cross_ma"
    MA_CROSSOVER = "ma_crossover"
    RSI = "rsi"
    MACD = "macd"
    BOLLINGER = "bollinger"
    VOLUME_SPIKE = "volume_spike"
    FACTOR_SCORE = "factor_score"
    PRICE_LEVEL = "price_level"
    PERCENT_CHANGE = "percent_change"


class SignalCondition(str, Enum):
    """Signal condition types."""
    ABOVE = "above"
    BELOW = "below"
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"
    EQUALS = "equals"
    BETWEEN = "between"


class PositionSizeMethod(str, Enum):
    """Position sizing methods."""
    FIXED_AMOUNT = "fixed_amount"
    FIXED_SHARES = "fixed_shares"
    PERCENT_PORTFOLIO = "percent_portfolio"
    ATR_BASED = "atr_based"
    VOLATILITY_SCALED = "volatility_scaled"
    KELLY = "kelly"


class RebalanceMethod(str, Enum):
    """Rebalancing methods."""
    FULL = "full"  # Rebalance all positions
    THRESHOLD_ONLY = "threshold_only"  # Only positions exceeding drift
    CASH_FLOW = "cash_flow"  # Use cash to rebalance
    TAX_AWARE = "tax_aware"  # Consider tax implications


class GridType(str, Enum):
    """Grid bot types."""
    ARITHMETIC = "arithmetic"  # Equal price spacing
    GEOMETRIC = "geometric"  # Equal percentage spacing


class TradeSide(str, Enum):
    """Trade side."""
    BUY = "buy"
    SELL = "sell"


# =============================================================================
# Configuration Dataclasses
# =============================================================================

@dataclass
class ScheduleConfig:
    """Schedule configuration for bots."""
    frequency: ScheduleFrequency = ScheduleFrequency.DAILY
    execution_time: ExecutionTime = ExecutionTime.MARKET_OPEN
    custom_time: Optional[str] = None  # HH:MM format
    day_of_week: Optional[int] = None  # 0=Monday, for weekly
    day_of_month: Optional[int] = None  # 1-28 for monthly
    timezone: str = "America/New_York"
    skip_weekends: bool = True
    skip_holidays: bool = True


@dataclass
class RiskConfig:
    """Risk configuration for bots."""
    max_position_size: float = 10000.0  # Max $ per position
    max_portfolio_pct: float = 0.25  # Max 25% of portfolio
    max_daily_trades: int = 10
    max_daily_loss: float = 500.0
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    max_drawdown_pct: float = 0.10  # Halt at 10% drawdown


@dataclass
class ExecutionConfig:
    """Execution configuration for bots."""
    order_type: OrderType = OrderType.MARKET
    limit_offset_pct: float = 0.1  # 0.1% better than market for limits
    timeout_seconds: int = 60
    retry_count: int = 3
    retry_delay_seconds: int = 5
    require_confirmation: bool = False  # Manual approval


@dataclass
class DCAConfig:
    """DCA bot configuration."""
    amount_per_period: float = 100.0
    allocations: dict[str, float] = field(default_factory=lambda: {"SPY": 1.0})
    
    # Enhancement options
    increase_on_dip: bool = False
    dip_threshold_pct: float = 5.0  # What's considered a dip
    dip_increase_pct: float = 50.0  # Increase investment by 50% on dip
    skip_if_price_above: Optional[float] = None
    reinvest_dividends: bool = True


@dataclass
class RebalanceConfig:
    """Rebalance bot configuration."""
    target_allocations: dict[str, float] = field(default_factory=dict)
    drift_threshold_pct: float = 5.0  # Rebalance if drift > 5%
    rebalance_method: RebalanceMethod = RebalanceMethod.THRESHOLD_ONLY
    min_trade_size: float = 50.0
    
    # Tax optimization
    tax_aware: bool = False
    avoid_wash_sales: bool = True
    prefer_long_term_lots: bool = True


@dataclass
class SignalBotConfig:
    """Signal bot configuration."""
    signals: list[dict] = field(default_factory=list)  # List of signal configs
    require_all_signals: bool = False  # AND vs OR
    confirmation_periods: int = 1
    cooldown_periods: int = 5  # Min periods between trades
    
    # Position management
    position_size_method: PositionSizeMethod = PositionSizeMethod.FIXED_AMOUNT
    fixed_amount: float = 1000.0
    percent_portfolio: float = 0.05


@dataclass
class GridConfig:
    """Grid bot configuration."""
    symbol: str = ""
    grid_type: GridType = GridType.ARITHMETIC
    upper_price: float = 0.0
    lower_price: float = 0.0
    num_grids: int = 10
    total_investment: float = 10000.0
    
    # Options
    trailing_grid: bool = False
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None


@dataclass
class BotConfig:
    """Main bot configuration."""
    bot_id: str = ""
    user_id: str = ""
    name: str = ""
    description: str = ""
    bot_type: BotType = BotType.DCA
    account_id: str = ""
    enabled: bool = True
    
    # Symbols
    symbols: list[str] = field(default_factory=list)
    
    # Sub-configs
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    
    # Type-specific configs
    dca_config: Optional[DCAConfig] = None
    rebalance_config: Optional[RebalanceConfig] = None
    signal_config: Optional[SignalBotConfig] = None
    grid_config: Optional[GridConfig] = None


@dataclass
class GlobalBotSettings:
    """Global settings for all bots."""
    max_total_bot_allocation: float = 0.5  # Max 50% managed by bots
    max_concurrent_orders: int = 10
    require_approval_above: float = 5000.0
    emergency_stop_all: bool = False
    allowed_hours_start: str = "09:30"
    allowed_hours_end: str = "16:00"
    paper_mode: bool = True  # Default to paper trading


DEFAULT_GLOBAL_SETTINGS = GlobalBotSettings()
