"""Tests for Watchlist Management."""

import pytest
from datetime import date, timedelta

from src.watchlist import (
    # Config
    AlertType, NoteType, Permission, ConvictionLevel,
    # Models
    Watchlist, WatchlistItem, WatchlistNote, WatchlistShare,
    # Managers
    WatchlistManager, AlertManager, NotesManager, SharingManager,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def watchlist_manager():
    """Create a watchlist manager."""
    return WatchlistManager()


@pytest.fixture
def sample_watchlist(watchlist_manager):
    """Create a sample watchlist with items."""
    wl = watchlist_manager.create_watchlist("Tech Stocks", "My tech picks")
    
    watchlist_manager.add_item(
        wl.watchlist_id, "AAPL", "Apple Inc.",
        current_price=185.0, buy_target=170.0, sell_target=200.0,
        conviction=4, tags=["mega-cap", "growth"]
    )
    watchlist_manager.add_item(
        wl.watchlist_id, "MSFT", "Microsoft Corp.",
        current_price=378.0, buy_target=350.0, sell_target=420.0,
        conviction=5, tags=["mega-cap", "cloud"]
    )
    watchlist_manager.add_item(
        wl.watchlist_id, "GOOGL", "Alphabet Inc.",
        current_price=141.0, buy_target=130.0, sell_target=160.0,
        conviction=3, tags=["mega-cap", "ai"]
    )
    
    return wl


# =============================================================================
# Test Watchlist Item
# =============================================================================

class TestWatchlistItem:
    """Tests for WatchlistItem model."""
    
    def test_gain_since_added(self):
        """Test gain calculation."""
        item = WatchlistItem(
            symbol="AAPL",
            added_price=150.0,
            current_price=185.0,
        )
        # (185 - 150) / 150 = 23.33%
        assert item.gain_since_added == pytest.approx(0.2333, rel=0.01)
    
    def test_distance_to_targets(self):
        """Test target distance calculations."""
        item = WatchlistItem(
            symbol="AAPL",
            current_price=185.0,
            buy_target=170.0,
            sell_target=200.0,
        )
        
        # To buy: (170 - 185) / 185 = -8.1%
        assert item.distance_to_buy_target == pytest.approx(-0.081, rel=0.01)
        
        # To sell: (200 - 185) / 185 = 8.1%
        assert item.distance_to_sell_target == pytest.approx(0.081, rel=0.01)


# =============================================================================
# Test Watchlist Manager
# =============================================================================

class TestWatchlistManager:
    """Tests for WatchlistManager."""
    
    def test_create_watchlist(self, watchlist_manager):
        """Test creating a watchlist."""
        wl = watchlist_manager.create_watchlist("Test List", "Description")
        
        assert wl.name == "Test List"
        assert wl.description == "Description"
        assert wl.watchlist_id is not None
    
    def test_add_item(self, watchlist_manager):
        """Test adding items to watchlist."""
        wl = watchlist_manager.create_watchlist("Test")
        
        item = watchlist_manager.add_item(
            wl.watchlist_id, "AAPL",
            current_price=185.0,
        )
        
        assert item is not None
        assert item.symbol == "AAPL"
        assert wl.item_count == 1
    
    def test_prevent_duplicate_items(self, watchlist_manager):
        """Test that duplicate symbols return existing item."""
        wl = watchlist_manager.create_watchlist("Test")
        
        item1 = watchlist_manager.add_item(wl.watchlist_id, "AAPL")
        item2 = watchlist_manager.add_item(wl.watchlist_id, "AAPL")
        
        assert item1.item_id == item2.item_id
        assert wl.item_count == 1
    
    def test_set_targets(self, watchlist_manager, sample_watchlist):
        """Test setting price targets."""
        watchlist_manager.set_targets(
            sample_watchlist.watchlist_id, "AAPL",
            buy_target=165.0, stop_loss=150.0,
        )
        
        item = watchlist_manager.get_item(sample_watchlist.watchlist_id, "AAPL")
        assert item.buy_target == 165.0
        assert item.stop_loss == 150.0
    
    def test_remove_item(self, watchlist_manager, sample_watchlist):
        """Test removing items."""
        initial_count = sample_watchlist.item_count
        
        result = watchlist_manager.remove_item(sample_watchlist.watchlist_id, "AAPL")
        
        assert result is True
        assert sample_watchlist.item_count == initial_count - 1
    
    def test_find_symbol_in_watchlists(self, watchlist_manager, sample_watchlist):
        """Test finding symbol across watchlists."""
        # Create another watchlist with AAPL
        wl2 = watchlist_manager.create_watchlist("Another List")
        watchlist_manager.add_item(wl2.watchlist_id, "AAPL")
        
        watchlists = watchlist_manager.find_symbol_in_watchlists("AAPL")
        
        assert len(watchlists) == 2
    
    def test_filter_by_tags(self, watchlist_manager, sample_watchlist):
        """Test filtering by tags."""
        items = watchlist_manager.filter_by_tags(
            sample_watchlist.watchlist_id, ["cloud"]
        )
        
        assert len(items) == 1
        assert items[0].symbol == "MSFT"
    
    def test_filter_by_conviction(self, watchlist_manager, sample_watchlist):
        """Test filtering by conviction level."""
        items = watchlist_manager.filter_by_conviction(
            sample_watchlist.watchlist_id, min_conviction=4
        )
        
        assert len(items) == 2
        assert all(item.conviction >= 4 for item in items)
    
    def test_calculate_performance(self, watchlist_manager, sample_watchlist):
        """Test performance calculation."""
        perf = watchlist_manager.calculate_performance(sample_watchlist.watchlist_id)
        
        assert perf is not None
        assert perf.total_items == 3


# =============================================================================
# Test Alert Manager
# =============================================================================

class TestAlertManager:
    """Tests for AlertManager."""
    
    def test_create_alert(self):
        """Test creating an alert."""
        manager = AlertManager()
        
        alert = manager.create_alert(
            watchlist_id="wl1",
            symbol="AAPL",
            alert_type=AlertType.PRICE_BELOW,
            threshold=170.0,
        )
        
        assert alert.symbol == "AAPL"
        assert alert.threshold == 170.0
        assert alert.is_active
    
    def test_check_price_below_alert(self):
        """Test price below alert triggering."""
        manager = AlertManager()
        
        manager.create_alert(
            watchlist_id="wl1",
            symbol="AAPL",
            alert_type=AlertType.PRICE_BELOW,
            threshold=170.0,
        )
        
        notifications = manager.check_alerts({
            "AAPL": {"price": 168.0}
        })
        
        assert len(notifications) == 1
        assert "below" in notifications[0].message.lower()
    
    def test_check_price_above_alert(self):
        """Test price above alert triggering."""
        manager = AlertManager()
        
        manager.create_alert(
            watchlist_id="wl1",
            symbol="AAPL",
            alert_type=AlertType.PRICE_ABOVE,
            threshold=190.0,
        )
        
        notifications = manager.check_alerts({
            "AAPL": {"price": 195.0}
        })
        
        assert len(notifications) == 1
    
    def test_alert_not_triggered(self):
        """Test alert not triggering when condition not met."""
        manager = AlertManager()
        
        manager.create_alert(
            watchlist_id="wl1",
            symbol="AAPL",
            alert_type=AlertType.PRICE_BELOW,
            threshold=170.0,
        )
        
        notifications = manager.check_alerts({
            "AAPL": {"price": 185.0}  # Above threshold
        })
        
        assert len(notifications) == 0


# =============================================================================
# Test Notes Manager
# =============================================================================

class TestNotesManager:
    """Tests for NotesManager."""
    
    def test_add_note(self):
        """Test adding a note."""
        manager = NotesManager()
        
        note = manager.add_note(
            watchlist_id="wl1",
            symbol="AAPL",
            title="Q4 Analysis",
            content="Strong earnings expected...",
            note_type=NoteType.EARNINGS,
        )
        
        assert note.symbol == "AAPL"
        assert note.title == "Q4 Analysis"
    
    def test_create_tag(self):
        """Test creating a tag."""
        manager = NotesManager()
        
        tag = manager.create_tag("growth", color="#2ecc71")
        
        assert tag.name == "growth"
        assert tag.color == "#2ecc71"
    
    def test_add_tag_to_note(self):
        """Test adding tags to notes."""
        manager = NotesManager()
        
        note = manager.add_note(
            watchlist_id="wl1",
            symbol="AAPL",
            title="Test",
            content="Test content",
        )
        
        manager.add_tag_to_note(note.note_id, "important")
        
        assert "important" in note.tags
    
    def test_search_notes(self):
        """Test searching notes."""
        manager = NotesManager()
        
        manager.add_note("wl1", "AAPL", "Apple Analysis", "Revenue growth strong")
        manager.add_note("wl1", "MSFT", "Microsoft Review", "Cloud revenue up")
        
        results = manager.search_notes("revenue")
        
        assert len(results) == 2


# =============================================================================
# Test Sharing Manager
# =============================================================================

class TestSharingManager:
    """Tests for SharingManager."""
    
    def test_share_with_user(self):
        """Test sharing with a user."""
        manager = SharingManager()
        
        share = manager.share_with_user(
            watchlist_id="wl1",
            user_id="user123",
            permission=Permission.VIEW,
        )
        
        assert share.shared_with == "user123"
        assert share.permission == Permission.VIEW
    
    def test_create_share_link(self):
        """Test creating a share link."""
        manager = SharingManager()
        
        share = manager.create_share_link(
            watchlist_id="wl1",
            expires_in_days=7,
        )
        
        assert share.share_link is not None
        assert share.is_link_valid
    
    def test_check_access(self):
        """Test access checking."""
        manager = SharingManager()
        
        manager.share_with_user("wl1", "user123", Permission.EDIT)
        
        assert manager.check_access("wl1", "user123", Permission.VIEW)
        assert manager.check_access("wl1", "user123", Permission.EDIT)
        assert not manager.check_access("wl1", "user123", Permission.ADMIN)
    
    def test_revoke_share(self):
        """Test revoking a share."""
        manager = SharingManager()
        
        share = manager.share_with_user("wl1", "user123")
        
        result = manager.revoke_share(share.share_id)
        
        assert result is True
        assert manager.get_share(share.share_id) is None
