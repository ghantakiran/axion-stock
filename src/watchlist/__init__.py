"""Watchlist Management.

Create and manage watchlists with price targets, notes, alerts, and sharing.

Example:
    from src.watchlist import (
        WatchlistManager, AlertManager, NotesManager, SharingManager,
        Watchlist, WatchlistItem, AlertType, NoteType, Permission,
    )
    
    # Create watchlist manager
    manager = WatchlistManager()
    
    # Create a watchlist
    watchlist = manager.create_watchlist("Tech Stocks", "My favorite tech companies")
    
    # Add items with targets
    manager.add_item(
        watchlist.watchlist_id,
        symbol="AAPL",
        company_name="Apple Inc.",
        current_price=185.0,
        buy_target=170.0,
        sell_target=200.0,
        conviction=4,
    )
    
    # Set up alerts
    alert_manager = AlertManager()
    alert_manager.create_alert(
        watchlist.watchlist_id,
        symbol="AAPL",
        alert_type=AlertType.PRICE_BELOW,
        threshold=170.0,
    )
"""

from src.watchlist.config import (
    AlertType,
    NoteType,
    Permission,
    SortDirection,
    ColumnCategory,
    DataType,
    ConvictionLevel,
    WATCHLIST_COLORS,
    WATCHLIST_ICONS,
    ALL_COLUMNS,
    DEFAULT_COLUMNS,
    WatchlistConfig,
    DEFAULT_WATCHLIST_CONFIG,
)

from src.watchlist.models import (
    WatchlistItem,
    Watchlist,
    ColumnConfig,
    WatchlistView,
    WatchlistAlert,
    AlertNotification,
    WatchlistNote,
    Tag,
    WatchlistShare,
    WatchlistPerformance,
)

from src.watchlist.manager import WatchlistManager
from src.watchlist.alerts import AlertManager
from src.watchlist.notes import NotesManager
from src.watchlist.sharing import SharingManager


__all__ = [
    # Config
    "AlertType",
    "NoteType",
    "Permission",
    "SortDirection",
    "ColumnCategory",
    "DataType",
    "ConvictionLevel",
    "WATCHLIST_COLORS",
    "WATCHLIST_ICONS",
    "ALL_COLUMNS",
    "DEFAULT_COLUMNS",
    "WatchlistConfig",
    "DEFAULT_WATCHLIST_CONFIG",
    # Models
    "WatchlistItem",
    "Watchlist",
    "ColumnConfig",
    "WatchlistView",
    "WatchlistAlert",
    "AlertNotification",
    "WatchlistNote",
    "Tag",
    "WatchlistShare",
    "WatchlistPerformance",
    # Managers
    "WatchlistManager",
    "AlertManager",
    "NotesManager",
    "SharingManager",
]
