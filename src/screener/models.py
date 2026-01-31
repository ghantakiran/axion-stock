"""Advanced Stock Screener Data Models.

Dataclasses for filters, screens, results, and alerts.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Optional
import uuid

from src.screener.config import (
    FilterCategory,
    DataType,
    Operator,
    Universe,
    SortOrder,
    AlertType,
    RebalanceFrequency,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# =============================================================================
# Filter Models
# =============================================================================

@dataclass
class FilterDefinition:
    """Definition of a screening filter."""
    filter_id: str
    name: str
    category: FilterCategory
    data_type: DataType
    description: str = ""
    
    # For numeric filters
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    default_operator: Operator = Operator.GTE
    
    # Metadata
    unit: Optional[str] = None  # %, $, ratio, x
    update_frequency: str = "daily"
    
    # Expression mapping
    expression_name: str = ""  # Name used in custom formulas


@dataclass
class FilterCondition:
    """A filter condition for screening."""
    filter_id: str
    operator: Operator
    value: Any
    value2: Optional[Any] = None  # For 'between' operator
    
    def evaluate(self, actual_value: Any) -> bool:
        """Evaluate this condition against an actual value."""
        if actual_value is None:
            return False
        
        try:
            if self.operator == Operator.EQ:
                return actual_value == self.value
            elif self.operator == Operator.NE:
                return actual_value != self.value
            elif self.operator == Operator.GT:
                return actual_value > self.value
            elif self.operator == Operator.GTE:
                return actual_value >= self.value
            elif self.operator == Operator.LT:
                return actual_value < self.value
            elif self.operator == Operator.LTE:
                return actual_value <= self.value
            elif self.operator == Operator.BETWEEN:
                return self.value <= actual_value <= self.value2
            elif self.operator == Operator.IN:
                return actual_value in self.value
            elif self.operator == Operator.NOT_IN:
                return actual_value not in self.value
            elif self.operator in (Operator.ABOVE, Operator.CROSSES_ABOVE):
                return actual_value > self.value
            elif self.operator in (Operator.BELOW, Operator.CROSSES_BELOW):
                return actual_value < self.value
        except (TypeError, ValueError):
            return False
        
        return False


@dataclass
class CustomFormula:
    """User-defined custom formula."""
    formula_id: str = field(default_factory=_new_id)
    name: str = ""
    expression: str = ""
    description: Optional[str] = None
    created_by: str = ""
    created_at: datetime = field(default_factory=_utc_now)
    
    # Validation
    is_valid: bool = True
    validation_error: Optional[str] = None


# =============================================================================
# Screen Models
# =============================================================================

@dataclass
class Screen:
    """A stock screening configuration."""
    screen_id: str = field(default_factory=_new_id)
    name: str = ""
    description: Optional[str] = None
    
    # Filters
    filters: list[FilterCondition] = field(default_factory=list)
    custom_formulas: list[CustomFormula] = field(default_factory=list)
    
    # Universe constraints
    universe: Universe = Universe.ALL
    sectors: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    market_cap_min: Optional[float] = None
    market_cap_max: Optional[float] = None
    exclude_symbols: list[str] = field(default_factory=list)
    
    # Display settings
    sort_by: str = "market_cap"
    sort_order: SortOrder = SortOrder.DESC
    columns: list[str] = field(default_factory=list)
    max_results: int = 100
    
    # Metadata
    created_by: str = ""
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    is_public: bool = False
    tags: list[str] = field(default_factory=list)
    
    # Preset flag
    is_preset: bool = False


@dataclass
class ScreenMatch:
    """A stock matching screen criteria."""
    symbol: str
    name: str
    sector: str = ""
    industry: str = ""
    
    # Key data
    price: float = 0.0
    market_cap: float = 0.0
    
    # All metrics (filter values)
    metrics: dict[str, Any] = field(default_factory=dict)
    
    # Match info
    match_score: float = 1.0  # How well it matches (for ranking)
    matched_filters: list[str] = field(default_factory=list)


@dataclass
class ScreenResult:
    """Results from running a screen."""
    screen_id: str
    screen_name: str
    run_at: datetime = field(default_factory=_utc_now)
    
    # Results
    total_universe: int = 0
    matches: int = 0
    stocks: list[ScreenMatch] = field(default_factory=list)
    
    # Filters applied
    filters_applied: int = 0
    
    # Performance
    execution_time_ms: float = 0.0


# =============================================================================
# Alert Models
# =============================================================================

@dataclass
class ScreenAlert:
    """Alert configuration for a screen."""
    alert_id: str = field(default_factory=_new_id)
    screen_id: str = ""
    alert_type: AlertType = AlertType.ENTRY
    
    # Configuration
    enabled: bool = True
    notify_on_entry: bool = True
    notify_on_exit: bool = False
    
    # For count alerts
    count_threshold: Optional[int] = None
    count_direction: str = "above"  # above, below
    
    # Delivery
    channels: list[str] = field(default_factory=list)  # email, push, webhook
    
    # Schedule (for scheduled alerts)
    schedule_cron: Optional[str] = None  # e.g., "0 9 * * 1-5" for 9am weekdays
    
    # State
    last_run: Optional[datetime] = None
    last_matches: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class AlertNotification:
    """A triggered alert notification."""
    notification_id: str = field(default_factory=_new_id)
    alert_id: str = ""
    screen_id: str = ""
    screen_name: str = ""
    
    # Trigger info
    trigger_type: str = ""  # entry, exit, count
    triggered_at: datetime = field(default_factory=_utc_now)
    
    # Affected stocks
    entered_stocks: list[str] = field(default_factory=list)
    exited_stocks: list[str] = field(default_factory=list)
    current_count: int = 0
    
    # Delivery status
    delivered: bool = False
    delivered_at: Optional[datetime] = None


# =============================================================================
# Backtest Models
# =============================================================================

@dataclass
class ScreenBacktestConfig:
    """Configuration for backtesting a screen."""
    screen_id: str = ""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    
    # Portfolio settings
    rebalance_frequency: RebalanceFrequency = RebalanceFrequency.MONTHLY
    max_positions: int = 20
    equal_weight: bool = True
    
    # Costs
    transaction_cost_bps: int = 10
    
    # Benchmark
    benchmark: str = "SPY"


@dataclass
class ScreenBacktestResult:
    """Results from backtesting a screen."""
    screen_id: str = ""
    screen_name: str = ""
    config: Optional[ScreenBacktestConfig] = None
    run_at: datetime = field(default_factory=_utc_now)
    
    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    benchmark_return: float = 0.0
    alpha: float = 0.0
    
    # Risk metrics
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    
    # Other stats
    win_rate: float = 0.0
    avg_holding_period: float = 0.0
    turnover: float = 0.0
    
    # Time series
    equity_curve: list[float] = field(default_factory=list)
    benchmark_curve: list[float] = field(default_factory=list)
    dates: list[date] = field(default_factory=list)
    
    # Holdings over time
    holdings_history: list[dict] = field(default_factory=list)
