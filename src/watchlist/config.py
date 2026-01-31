"""Watchlist Management Configuration.

Enums, constants, and configuration for watchlist tracking.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class AlertType(str, Enum):
    """Watchlist alert types."""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PCT_CHANGE_UP = "pct_change_up"
    PCT_CHANGE_DOWN = "pct_change_down"
    VOLUME_SPIKE = "volume_spike"
    RSI_OVERSOLD = "rsi_oversold"
    RSI_OVERBOUGHT = "rsi_overbought"
    MA_CROSS_UP = "ma_cross_up"
    MA_CROSS_DOWN = "ma_cross_down"
    TARGET_HIT = "target_hit"
    STOP_HIT = "stop_hit"
    EARNINGS_SOON = "earnings_soon"


class NoteType(str, Enum):
    """Types of watchlist notes."""
    RESEARCH = "research"
    THESIS = "thesis"
    EARNINGS = "earnings"
    NEWS = "news"
    TECHNICAL = "technical"
    GENERAL = "general"


class Permission(str, Enum):
    """Sharing permissions."""
    VIEW = "view"
    EDIT = "edit"
    ADMIN = "admin"


class SortDirection(str, Enum):
    """Sort direction."""
    ASC = "asc"
    DESC = "desc"


class ColumnCategory(str, Enum):
    """Column categories."""
    PRICE = "price"
    VOLUME = "volume"
    VALUATION = "valuation"
    FUNDAMENTALS = "fundamentals"
    TECHNICAL = "technical"
    PERFORMANCE = "performance"
    CUSTOM = "custom"


class DataType(str, Enum):
    """Column data types."""
    NUMBER = "number"
    PERCENT = "percent"
    CURRENCY = "currency"
    TEXT = "text"
    DATE = "date"
    RATING = "rating"


class ConvictionLevel(int, Enum):
    """Conviction levels (1-5)."""
    VERY_LOW = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    VERY_HIGH = 5


# =============================================================================
# Constants
# =============================================================================

# Default watchlist colors
WATCHLIST_COLORS = [
    "#3498db",  # Blue
    "#2ecc71",  # Green
    "#e74c3c",  # Red
    "#9b59b6",  # Purple
    "#f39c12",  # Orange
    "#1abc9c",  # Teal
    "#34495e",  # Dark Gray
    "#e91e63",  # Pink
]

# Default watchlist icons
WATCHLIST_ICONS = [
    "📈", "📊", "💰", "🎯", "⭐", "🔥", "💎", "🚀",
    "📉", "🏆", "💡", "🔔", "📌", "🎪", "🌟", "⚡",
]

# Alert thresholds
DEFAULT_PCT_CHANGE_THRESHOLD = 5.0  # 5%
DEFAULT_VOLUME_SPIKE_RATIO = 2.0  # 2x average
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# Maximum items
MAX_WATCHLISTS = 50
MAX_ITEMS_PER_WATCHLIST = 100
MAX_NOTES_PER_ITEM = 20


# =============================================================================
# Default Columns
# =============================================================================

DEFAULT_COLUMNS = [
    "symbol", "last_price", "change", "change_pct",
    "volume", "market_cap", "pe_ratio", "target_pct",
]

ALL_COLUMNS = {
    # Price
    "symbol": ("Symbol", ColumnCategory.PRICE, DataType.TEXT),
    "last_price": ("Last", ColumnCategory.PRICE, DataType.CURRENCY),
    "change": ("Change", ColumnCategory.PRICE, DataType.CURRENCY),
    "change_pct": ("Change %", ColumnCategory.PRICE, DataType.PERCENT),
    "open": ("Open", ColumnCategory.PRICE, DataType.CURRENCY),
    "high": ("High", ColumnCategory.PRICE, DataType.CURRENCY),
    "low": ("Low", ColumnCategory.PRICE, DataType.CURRENCY),
    "high_52w": ("52W High", ColumnCategory.PRICE, DataType.CURRENCY),
    "low_52w": ("52W Low", ColumnCategory.PRICE, DataType.CURRENCY),
    
    # Volume
    "volume": ("Volume", ColumnCategory.VOLUME, DataType.NUMBER),
    "avg_volume": ("Avg Volume", ColumnCategory.VOLUME, DataType.NUMBER),
    "volume_ratio": ("Vol Ratio", ColumnCategory.VOLUME, DataType.NUMBER),
    
    # Valuation
    "market_cap": ("Market Cap", ColumnCategory.VALUATION, DataType.CURRENCY),
    "pe_ratio": ("P/E", ColumnCategory.VALUATION, DataType.NUMBER),
    "forward_pe": ("Fwd P/E", ColumnCategory.VALUATION, DataType.NUMBER),
    "ps_ratio": ("P/S", ColumnCategory.VALUATION, DataType.NUMBER),
    "pb_ratio": ("P/B", ColumnCategory.VALUATION, DataType.NUMBER),
    "ev_ebitda": ("EV/EBITDA", ColumnCategory.VALUATION, DataType.NUMBER),
    
    # Fundamentals
    "revenue": ("Revenue", ColumnCategory.FUNDAMENTALS, DataType.CURRENCY),
    "eps": ("EPS", ColumnCategory.FUNDAMENTALS, DataType.CURRENCY),
    "dividend_yield": ("Div Yield", ColumnCategory.FUNDAMENTALS, DataType.PERCENT),
    
    # Technical
    "rsi": ("RSI", ColumnCategory.TECHNICAL, DataType.NUMBER),
    "sma_50": ("SMA 50", ColumnCategory.TECHNICAL, DataType.CURRENCY),
    "sma_200": ("SMA 200", ColumnCategory.TECHNICAL, DataType.CURRENCY),
    "dist_sma_50": ("% from SMA50", ColumnCategory.TECHNICAL, DataType.PERCENT),
    
    # Performance
    "return_1d": ("1D", ColumnCategory.PERFORMANCE, DataType.PERCENT),
    "return_1w": ("1W", ColumnCategory.PERFORMANCE, DataType.PERCENT),
    "return_1m": ("1M", ColumnCategory.PERFORMANCE, DataType.PERCENT),
    "return_3m": ("3M", ColumnCategory.PERFORMANCE, DataType.PERCENT),
    "return_ytd": ("YTD", ColumnCategory.PERFORMANCE, DataType.PERCENT),
    "return_1y": ("1Y", ColumnCategory.PERFORMANCE, DataType.PERCENT),
    
    # Custom
    "buy_target": ("Buy Target", ColumnCategory.CUSTOM, DataType.CURRENCY),
    "sell_target": ("Sell Target", ColumnCategory.CUSTOM, DataType.CURRENCY),
    "target_pct": ("To Target", ColumnCategory.CUSTOM, DataType.PERCENT),
    "conviction": ("Conviction", ColumnCategory.CUSTOM, DataType.RATING),
    "notes": ("Notes", ColumnCategory.CUSTOM, DataType.TEXT),
    "tags": ("Tags", ColumnCategory.CUSTOM, DataType.TEXT),
    "added_date": ("Added", ColumnCategory.CUSTOM, DataType.DATE),
    "added_price": ("Add Price", ColumnCategory.CUSTOM, DataType.CURRENCY),
    "since_added": ("Since Added", ColumnCategory.CUSTOM, DataType.PERCENT),
}


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class WatchlistConfig:
    """Configuration for watchlist management."""
    max_watchlists: int = MAX_WATCHLISTS
    max_items_per_watchlist: int = MAX_ITEMS_PER_WATCHLIST
    max_notes_per_item: int = MAX_NOTES_PER_ITEM
    default_columns: list[str] = field(default_factory=lambda: DEFAULT_COLUMNS.copy())
    enable_sharing: bool = True
    enable_alerts: bool = True


DEFAULT_WATCHLIST_CONFIG = WatchlistConfig()
