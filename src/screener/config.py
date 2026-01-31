"""Advanced Stock Screener Configuration.

Enums, constants, and configuration for the screener.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class FilterCategory(str, Enum):
    """Filter category."""
    # Fundamentals
    VALUATION = "valuation"
    GROWTH = "growth"
    PROFITABILITY = "profitability"
    FINANCIAL_HEALTH = "financial_health"
    SIZE = "size"
    DIVIDENDS = "dividends"
    
    # Technicals
    PRICE = "price"
    MOVING_AVERAGE = "moving_average"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    PATTERNS = "patterns"
    
    # Alternative
    ANALYST = "analyst"
    INSTITUTIONAL = "institutional"
    INSIDER = "insider"
    SHORT_INTEREST = "short_interest"
    SENTIMENT = "sentiment"


class DataType(str, Enum):
    """Filter data type."""
    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    DATE = "date"
    STRING = "string"
    PERCENT = "percent"
    CURRENCY = "currency"


class Operator(str, Enum):
    """Comparison operator."""
    EQ = "eq"           # Equal
    NE = "ne"           # Not equal
    GT = "gt"           # Greater than
    GTE = "gte"         # Greater than or equal
    LT = "lt"           # Less than
    LTE = "lte"         # Less than or equal
    BETWEEN = "between" # Between two values
    IN = "in"           # In list
    NOT_IN = "not_in"   # Not in list
    ABOVE = "above"     # Above (for MA comparisons)
    BELOW = "below"     # Below
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"


class Universe(str, Enum):
    """Stock universe."""
    ALL = "all"
    SP500 = "sp500"
    SP400 = "sp400"
    SP600 = "sp600"
    NASDAQ100 = "nasdaq100"
    DOW30 = "dow30"
    RUSSELL1000 = "russell1000"
    RUSSELL2000 = "russell2000"
    SECTOR = "sector"
    INDUSTRY = "industry"
    CUSTOM = "custom"


class SortOrder(str, Enum):
    """Sort order."""
    ASC = "asc"
    DESC = "desc"


class AlertType(str, Enum):
    """Screen alert type."""
    ENTRY = "entry"       # Stock enters screen
    EXIT = "exit"         # Stock exits screen
    COUNT = "count"       # Match count threshold
    SCHEDULED = "scheduled"


class RebalanceFrequency(str, Enum):
    """Backtest rebalance frequency."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


# =============================================================================
# Constants
# =============================================================================

# Sectors
SECTORS = [
    "Technology",
    "Healthcare",
    "Financial",
    "Consumer Cyclical",
    "Consumer Defensive",
    "Industrial",
    "Energy",
    "Utilities",
    "Real Estate",
    "Basic Materials",
    "Communication Services",
]

# Default display columns
DEFAULT_COLUMNS = [
    "symbol",
    "name",
    "sector",
    "price",
    "market_cap",
    "pe_ratio",
    "revenue_growth",
    "gross_margin",
]


# =============================================================================
# Configuration Dataclasses
# =============================================================================

@dataclass
class ScreenerConfig:
    """Screener configuration."""
    max_results: int = 500
    default_universe: Universe = Universe.ALL
    cache_ttl_seconds: int = 300
    enable_alerts: bool = True
    enable_backtest: bool = True


@dataclass
class BacktestConfig:
    """Backtest configuration."""
    default_start_lookback_years: int = 5
    min_positions: int = 5
    max_positions: int = 50
    transaction_cost_bps: int = 10
    benchmark: str = "SPY"


DEFAULT_SCREENER_CONFIG = ScreenerConfig()
DEFAULT_BACKTEST_CONFIG = BacktestConfig()
