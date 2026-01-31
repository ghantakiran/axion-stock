"""Watchlist Data Models.

Dataclasses for watchlists, items, alerts, notes, and sharing.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Optional, Any
import uuid

from src.watchlist.config import (
    AlertType,
    NoteType,
    Permission,
    ConvictionLevel,
    ColumnCategory,
    DataType,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# =============================================================================
# Core Watchlist Models
# =============================================================================

@dataclass
class WatchlistItem:
    """An item in a watchlist."""
    item_id: str = field(default_factory=_new_id)
    symbol: str = ""
    company_name: str = ""
    
    # Current data
    current_price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    
    # Targets
    buy_target: Optional[float] = None
    sell_target: Optional[float] = None
    stop_loss: Optional[float] = None
    
    # Notes and classification
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    conviction: Optional[int] = None  # 1-5
    
    # Alerts
    alerts_enabled: bool = True
    
    # Tracking
    added_at: datetime = field(default_factory=_utc_now)
    added_price: float = 0.0
    
    @property
    def gain_since_added(self) -> float:
        """Calculate gain since added."""
        if self.added_price > 0:
            return (self.current_price - self.added_price) / self.added_price
        return 0.0
    
    @property
    def distance_to_buy_target(self) -> Optional[float]:
        """Calculate distance to buy target."""
        if self.buy_target and self.current_price > 0:
            return (self.buy_target - self.current_price) / self.current_price
        return None
    
    @property
    def distance_to_sell_target(self) -> Optional[float]:
        """Calculate distance to sell target."""
        if self.sell_target and self.current_price > 0:
            return (self.sell_target - self.current_price) / self.current_price
        return None


@dataclass
class Watchlist:
    """A watchlist containing multiple items."""
    watchlist_id: str = field(default_factory=_new_id)
    name: str = ""
    description: str = ""
    
    # Items
    items: list[WatchlistItem] = field(default_factory=list)
    
    # Organization
    is_default: bool = False
    color: str = "#3498db"
    icon: str = "📈"
    sort_order: int = 0
    
    # Sharing
    is_public: bool = False
    shared_with: list[str] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    created_by: str = ""
    
    @property
    def item_count(self) -> int:
        return len(self.items)
    
    def get_item(self, symbol: str) -> Optional[WatchlistItem]:
        """Get item by symbol."""
        for item in self.items:
            if item.symbol == symbol:
                return item
        return None
    
    def has_symbol(self, symbol: str) -> bool:
        """Check if symbol is in watchlist."""
        return any(item.symbol == symbol for item in self.items)


# =============================================================================
# Column Configuration
# =============================================================================

@dataclass
class ColumnConfig:
    """Configuration for a display column."""
    column_id: str = ""
    name: str = ""
    category: ColumnCategory = ColumnCategory.PRICE
    data_type: DataType = DataType.TEXT
    width: int = 100
    alignment: str = "right"
    format_str: Optional[str] = None
    is_visible: bool = True
    sort_order: int = 0


@dataclass
class WatchlistView:
    """View configuration for a watchlist."""
    view_id: str = field(default_factory=_new_id)
    watchlist_id: str = ""
    name: str = "Default"
    
    # Columns
    columns: list[str] = field(default_factory=list)
    column_configs: dict[str, ColumnConfig] = field(default_factory=dict)
    
    # Sorting
    sort_column: str = "symbol"
    sort_ascending: bool = True
    
    # Filtering
    filter_tags: list[str] = field(default_factory=list)
    filter_conviction: Optional[int] = None


# =============================================================================
# Alert Models
# =============================================================================

@dataclass
class WatchlistAlert:
    """An alert for a watchlist item."""
    alert_id: str = field(default_factory=_new_id)
    watchlist_id: str = ""
    item_id: str = ""
    symbol: str = ""
    
    # Condition
    alert_type: AlertType = AlertType.PRICE_ABOVE
    threshold: float = 0.0
    
    # Status
    is_active: bool = True
    triggered_at: Optional[datetime] = None
    trigger_count: int = 0
    
    # Notification preferences
    notify_email: bool = True
    notify_push: bool = True
    notify_sms: bool = False
    
    # Metadata
    created_at: datetime = field(default_factory=_utc_now)
    
    @property
    def is_triggered(self) -> bool:
        return self.triggered_at is not None


@dataclass
class AlertNotification:
    """Notification for a triggered alert."""
    notification_id: str = field(default_factory=_new_id)
    alert_id: str = ""
    symbol: str = ""
    
    # Content
    title: str = ""
    message: str = ""
    
    # Trigger data
    trigger_value: float = 0.0
    threshold: float = 0.0
    
    # Status
    is_read: bool = False
    created_at: datetime = field(default_factory=_utc_now)


# =============================================================================
# Notes Models
# =============================================================================

@dataclass
class WatchlistNote:
    """A note attached to a watchlist item."""
    note_id: str = field(default_factory=_new_id)
    watchlist_id: str = ""
    symbol: str = ""
    
    # Content
    title: str = ""
    content: str = ""
    
    # Classification
    note_type: NoteType = NoteType.GENERAL
    tags: list[str] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    created_by: str = ""


@dataclass
class Tag:
    """A user-defined tag."""
    tag_id: str = field(default_factory=_new_id)
    name: str = ""
    color: str = "#3498db"
    usage_count: int = 0
    created_at: datetime = field(default_factory=_utc_now)


# =============================================================================
# Sharing Models
# =============================================================================

@dataclass
class WatchlistShare:
    """Sharing configuration for a watchlist."""
    share_id: str = field(default_factory=_new_id)
    watchlist_id: str = ""
    
    # Access
    shared_with: str = ""  # user_id or "public"
    permission: Permission = Permission.VIEW
    
    # Tracking
    shared_at: datetime = field(default_factory=_utc_now)
    shared_by: str = ""
    
    # Link sharing
    share_link: Optional[str] = None
    link_expires: Optional[datetime] = None
    
    @property
    def is_link_valid(self) -> bool:
        if not self.share_link:
            return False
        if self.link_expires and datetime.now(timezone.utc) > self.link_expires:
            return False
        return True


# =============================================================================
# Performance Models
# =============================================================================

@dataclass
class WatchlistPerformance:
    """Performance tracking for a watchlist."""
    watchlist_id: str = ""
    calculated_at: datetime = field(default_factory=_utc_now)
    
    # Hypothetical returns (if bought at add price)
    total_items: int = 0
    hypothetical_investment: float = 0.0
    hypothetical_value: float = 0.0
    hypothetical_return: float = 0.0
    hypothetical_return_pct: float = 0.0
    
    # Winners/losers
    winners: int = 0
    losers: int = 0
    win_rate: float = 0.0
    
    # Best/worst
    top_performers: list[tuple[str, float]] = field(default_factory=list)
    worst_performers: list[tuple[str, float]] = field(default_factory=list)
    
    # Targets
    buy_targets_hit: int = 0
    sell_targets_hit: int = 0
    stops_hit: int = 0
