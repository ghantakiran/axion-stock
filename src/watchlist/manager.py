"""Watchlist Manager.

Core CRUD operations for watchlists and items.
"""

from datetime import datetime, timezone
from typing import Optional
import logging

from src.watchlist.config import (
    WatchlistConfig,
    DEFAULT_WATCHLIST_CONFIG,
    WATCHLIST_COLORS,
    WATCHLIST_ICONS,
)
from src.watchlist.models import (
    Watchlist,
    WatchlistItem,
    WatchlistView,
    WatchlistPerformance,
)

logger = logging.getLogger(__name__)


class WatchlistManager:
    """Manages watchlists and their items.
    
    Provides CRUD operations for watchlists, items, and views.
    
    Example:
        manager = WatchlistManager()
        
        # Create a watchlist
        watchlist = manager.create_watchlist("Tech Stocks", "My favorite tech companies")
        
        # Add items
        manager.add_item(watchlist.watchlist_id, "AAPL", current_price=185.0)
        manager.add_item(watchlist.watchlist_id, "MSFT", current_price=378.0)
        
        # Set targets
        manager.set_targets(watchlist.watchlist_id, "AAPL", buy_target=170.0, sell_target=200.0)
    """
    
    def __init__(self, config: Optional[WatchlistConfig] = None):
        self.config = config or DEFAULT_WATCHLIST_CONFIG
        self._watchlists: dict[str, Watchlist] = {}
        self._views: dict[str, WatchlistView] = {}
        self._color_index = 0
        self._icon_index = 0
    
    # =========================================================================
    # Watchlist CRUD
    # =========================================================================
    
    def create_watchlist(
        self,
        name: str,
        description: str = "",
        color: Optional[str] = None,
        icon: Optional[str] = None,
        is_default: bool = False,
        created_by: str = "user",
    ) -> Watchlist:
        """Create a new watchlist.
        
        Args:
            name: Watchlist name.
            description: Optional description.
            color: Display color (auto-assigned if not provided).
            icon: Display icon (auto-assigned if not provided).
            is_default: Whether this is the default watchlist.
            created_by: User who created it.
            
        Returns:
            Created Watchlist.
        """
        # Check limit
        if len(self._watchlists) >= self.config.max_watchlists:
            raise ValueError(f"Maximum {self.config.max_watchlists} watchlists allowed")
        
        # Auto-assign color and icon
        if not color:
            color = WATCHLIST_COLORS[self._color_index % len(WATCHLIST_COLORS)]
            self._color_index += 1
        
        if not icon:
            icon = WATCHLIST_ICONS[self._icon_index % len(WATCHLIST_ICONS)]
            self._icon_index += 1
        
        # If setting as default, unset others
        if is_default:
            for wl in self._watchlists.values():
                wl.is_default = False
        
        watchlist = Watchlist(
            name=name,
            description=description,
            color=color,
            icon=icon,
            is_default=is_default,
            created_by=created_by,
            sort_order=len(self._watchlists),
        )
        
        self._watchlists[watchlist.watchlist_id] = watchlist
        return watchlist
    
    def get_watchlist(self, watchlist_id: str) -> Optional[Watchlist]:
        """Get watchlist by ID."""
        return self._watchlists.get(watchlist_id)
    
    def get_watchlist_by_name(self, name: str) -> Optional[Watchlist]:
        """Get watchlist by name."""
        for wl in self._watchlists.values():
            if wl.name.lower() == name.lower():
                return wl
        return None
    
    def get_all_watchlists(self) -> list[Watchlist]:
        """Get all watchlists sorted by sort_order."""
        return sorted(self._watchlists.values(), key=lambda w: w.sort_order)
    
    def get_default_watchlist(self) -> Optional[Watchlist]:
        """Get the default watchlist."""
        for wl in self._watchlists.values():
            if wl.is_default:
                return wl
        return None
    
    def update_watchlist(
        self,
        watchlist_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        icon: Optional[str] = None,
    ) -> Optional[Watchlist]:
        """Update watchlist properties."""
        watchlist = self._watchlists.get(watchlist_id)
        if not watchlist:
            return None
        
        if name is not None:
            watchlist.name = name
        if description is not None:
            watchlist.description = description
        if color is not None:
            watchlist.color = color
        if icon is not None:
            watchlist.icon = icon
        
        watchlist.updated_at = datetime.now(timezone.utc)
        return watchlist
    
    def delete_watchlist(self, watchlist_id: str) -> bool:
        """Delete a watchlist."""
        if watchlist_id in self._watchlists:
            del self._watchlists[watchlist_id]
            return True
        return False
    
    def reorder_watchlists(self, watchlist_ids: list[str]) -> None:
        """Reorder watchlists."""
        for i, wl_id in enumerate(watchlist_ids):
            if wl_id in self._watchlists:
                self._watchlists[wl_id].sort_order = i
    
    # =========================================================================
    # Item CRUD
    # =========================================================================
    
    def add_item(
        self,
        watchlist_id: str,
        symbol: str,
        company_name: str = "",
        current_price: float = 0.0,
        buy_target: Optional[float] = None,
        sell_target: Optional[float] = None,
        notes: str = "",
        tags: Optional[list[str]] = None,
        conviction: Optional[int] = None,
    ) -> Optional[WatchlistItem]:
        """Add an item to a watchlist.
        
        Args:
            watchlist_id: Target watchlist ID.
            symbol: Stock symbol.
            company_name: Company name.
            current_price: Current price (also used as added_price).
            buy_target: Optional buy target price.
            sell_target: Optional sell target price.
            notes: Optional notes.
            tags: Optional tags.
            conviction: Optional conviction level (1-5).
            
        Returns:
            Created WatchlistItem.
        """
        watchlist = self._watchlists.get(watchlist_id)
        if not watchlist:
            return None
        
        # Check limit
        if len(watchlist.items) >= self.config.max_items_per_watchlist:
            raise ValueError(f"Maximum {self.config.max_items_per_watchlist} items allowed")
        
        # Check if already exists
        if watchlist.has_symbol(symbol):
            return watchlist.get_item(symbol)
        
        item = WatchlistItem(
            symbol=symbol.upper(),
            company_name=company_name,
            current_price=current_price,
            added_price=current_price,
            buy_target=buy_target,
            sell_target=sell_target,
            notes=notes,
            tags=tags or [],
            conviction=conviction,
        )
        
        watchlist.items.append(item)
        watchlist.updated_at = datetime.now(timezone.utc)
        return item
    
    def get_item(self, watchlist_id: str, symbol: str) -> Optional[WatchlistItem]:
        """Get an item from a watchlist."""
        watchlist = self._watchlists.get(watchlist_id)
        if watchlist:
            return watchlist.get_item(symbol)
        return None
    
    def update_item(
        self,
        watchlist_id: str,
        symbol: str,
        current_price: Optional[float] = None,
        buy_target: Optional[float] = None,
        sell_target: Optional[float] = None,
        stop_loss: Optional[float] = None,
        notes: Optional[str] = None,
        tags: Optional[list[str]] = None,
        conviction: Optional[int] = None,
    ) -> Optional[WatchlistItem]:
        """Update an item's properties."""
        item = self.get_item(watchlist_id, symbol)
        if not item:
            return None
        
        if current_price is not None:
            item.current_price = current_price
        if buy_target is not None:
            item.buy_target = buy_target
        if sell_target is not None:
            item.sell_target = sell_target
        if stop_loss is not None:
            item.stop_loss = stop_loss
        if notes is not None:
            item.notes = notes
        if tags is not None:
            item.tags = tags
        if conviction is not None:
            item.conviction = conviction
        
        watchlist = self._watchlists.get(watchlist_id)
        if watchlist:
            watchlist.updated_at = datetime.now(timezone.utc)
        
        return item
    
    def remove_item(self, watchlist_id: str, symbol: str) -> bool:
        """Remove an item from a watchlist."""
        watchlist = self._watchlists.get(watchlist_id)
        if not watchlist:
            return False
        
        item = watchlist.get_item(symbol)
        if item:
            watchlist.items.remove(item)
            watchlist.updated_at = datetime.now(timezone.utc)
            return True
        return False
    
    def set_targets(
        self,
        watchlist_id: str,
        symbol: str,
        buy_target: Optional[float] = None,
        sell_target: Optional[float] = None,
        stop_loss: Optional[float] = None,
    ) -> Optional[WatchlistItem]:
        """Set price targets for an item."""
        return self.update_item(
            watchlist_id, symbol,
            buy_target=buy_target,
            sell_target=sell_target,
            stop_loss=stop_loss,
        )
    
    def update_prices(
        self,
        watchlist_id: str,
        prices: dict[str, tuple[float, float, float]],  # symbol -> (price, change, change_pct)
    ) -> int:
        """Bulk update prices for watchlist items.
        
        Args:
            watchlist_id: Watchlist ID.
            prices: Dict of symbol -> (price, change, change_pct).
            
        Returns:
            Number of items updated.
        """
        watchlist = self._watchlists.get(watchlist_id)
        if not watchlist:
            return 0
        
        updated = 0
        for item in watchlist.items:
            if item.symbol in prices:
                price, change, change_pct = prices[item.symbol]
                item.current_price = price
                item.change = change
                item.change_pct = change_pct
                updated += 1
        
        return updated
    
    # =========================================================================
    # Search and Filter
    # =========================================================================
    
    def find_symbol_in_watchlists(self, symbol: str) -> list[Watchlist]:
        """Find all watchlists containing a symbol."""
        return [wl for wl in self._watchlists.values() if wl.has_symbol(symbol)]
    
    def search_items(
        self,
        query: str,
        watchlist_id: Optional[str] = None,
    ) -> list[tuple[str, WatchlistItem]]:
        """Search items across watchlists.
        
        Args:
            query: Search query (matches symbol, name, notes).
            watchlist_id: Optional filter to specific watchlist.
            
        Returns:
            List of (watchlist_id, item) tuples.
        """
        results = []
        query = query.lower()
        
        watchlists = [self._watchlists[watchlist_id]] if watchlist_id else self._watchlists.values()
        
        for wl in watchlists:
            for item in wl.items:
                if (query in item.symbol.lower() or
                    query in item.company_name.lower() or
                    query in item.notes.lower() or
                    any(query in tag.lower() for tag in item.tags)):
                    results.append((wl.watchlist_id, item))
        
        return results
    
    def filter_by_tags(
        self,
        watchlist_id: str,
        tags: list[str],
    ) -> list[WatchlistItem]:
        """Filter items by tags."""
        watchlist = self._watchlists.get(watchlist_id)
        if not watchlist:
            return []
        
        tags_lower = [t.lower() for t in tags]
        return [
            item for item in watchlist.items
            if any(t.lower() in tags_lower for t in item.tags)
        ]
    
    def filter_by_conviction(
        self,
        watchlist_id: str,
        min_conviction: int,
    ) -> list[WatchlistItem]:
        """Filter items by minimum conviction level."""
        watchlist = self._watchlists.get(watchlist_id)
        if not watchlist:
            return []
        
        return [
            item for item in watchlist.items
            if item.conviction and item.conviction >= min_conviction
        ]
    
    # =========================================================================
    # Performance
    # =========================================================================
    
    def calculate_performance(self, watchlist_id: str) -> Optional[WatchlistPerformance]:
        """Calculate performance metrics for a watchlist."""
        watchlist = self._watchlists.get(watchlist_id)
        if not watchlist or not watchlist.items:
            return None
        
        perf = WatchlistPerformance(watchlist_id=watchlist_id)
        perf.total_items = len(watchlist.items)
        
        returns = []
        for item in watchlist.items:
            if item.added_price > 0:
                perf.hypothetical_investment += item.added_price
                perf.hypothetical_value += item.current_price
                
                ret = item.gain_since_added
                returns.append((item.symbol, ret))
                
                if ret > 0:
                    perf.winners += 1
                else:
                    perf.losers += 1
                
                # Check targets
                if item.buy_target and item.current_price <= item.buy_target:
                    perf.buy_targets_hit += 1
                if item.sell_target and item.current_price >= item.sell_target:
                    perf.sell_targets_hit += 1
                if item.stop_loss and item.current_price <= item.stop_loss:
                    perf.stops_hit += 1
        
        if perf.hypothetical_investment > 0:
            perf.hypothetical_return = perf.hypothetical_value - perf.hypothetical_investment
            perf.hypothetical_return_pct = perf.hypothetical_return / perf.hypothetical_investment
        
        if perf.total_items > 0:
            perf.win_rate = perf.winners / perf.total_items
        
        # Sort for top/worst
        returns.sort(key=lambda x: x[1], reverse=True)
        perf.top_performers = returns[:5]
        perf.worst_performers = returns[-5:][::-1]
        
        return perf
