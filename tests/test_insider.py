"""Tests for Insider Trading Tracker Module."""

import pytest
from datetime import date, timedelta

from src.insider import (
    # Config
    InsiderType, TransactionType, SignalStrength, InstitutionType,
    # Models
    InsiderTransaction, InsiderCluster, InstitutionalHolding, InsiderProfile,
    # Tracker
    TransactionTracker, generate_sample_transactions,
    # Clusters
    ClusterDetector,
    # Institutions
    InstitutionalTracker, generate_sample_institutional,
    # Profiles
    ProfileManager,
    # Signals
    SignalGenerator, AlertManager, create_default_alerts,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_transaction():
    """Sample insider transaction."""
    return InsiderTransaction(
        symbol="AAPL",
        company_name="Apple Inc.",
        insider_name="Tim Cook",
        insider_title="CEO",
        insider_type=InsiderType.CEO,
        transaction_type=TransactionType.BUY,
        transaction_date=date.today() - timedelta(days=5),
        shares=50000,
        price=185.0,
        value=9_250_000,
    )


@pytest.fixture
def tracker_with_data():
    """Transaction tracker with sample data."""
    return generate_sample_transactions()


# =============================================================================
# Test Insider Transaction
# =============================================================================

class TestInsiderTransaction:
    """Tests for InsiderTransaction model."""
    
    def test_is_buy(self, sample_transaction):
        """Test is_buy property."""
        assert sample_transaction.is_buy is True
        assert sample_transaction.is_sell is False
    
    def test_is_bullish(self, sample_transaction):
        """Test is_bullish property."""
        assert sample_transaction.is_bullish is True
    
    def test_is_significant(self, sample_transaction):
        """Test is_significant property."""
        assert sample_transaction.is_significant is True
        
        small_txn = InsiderTransaction(value=50_000)
        assert small_txn.is_significant is False
    
    def test_value_calculation(self):
        """Test that tracker calculates value."""
        tracker = TransactionTracker()
        txn = InsiderTransaction(
            symbol="TEST",
            insider_name="Test Person",
            transaction_type=TransactionType.BUY,
            transaction_date=date.today(),
            shares=1000,
            price=50.0,
            value=0,  # Not set
        )
        tracker.add_transaction(txn)
        
        retrieved = tracker.get_transaction(txn.transaction_id)
        assert retrieved.value == 50_000


# =============================================================================
# Test Transaction Tracker
# =============================================================================

class TestTransactionTracker:
    """Tests for TransactionTracker."""
    
    def test_add_transaction(self, sample_transaction):
        """Test adding transaction."""
        tracker = TransactionTracker()
        tracker.add_transaction(sample_transaction)
        
        retrieved = tracker.get_transaction(sample_transaction.transaction_id)
        assert retrieved is not None
        assert retrieved.symbol == "AAPL"
    
    def test_get_by_symbol(self, tracker_with_data):
        """Test getting transactions by symbol."""
        aapl_txns = tracker_with_data.get_by_symbol("AAPL", days=90)
        
        assert len(aapl_txns) >= 3
        assert all(t.symbol == "AAPL" for t in aapl_txns)
    
    def test_get_recent_buys(self, tracker_with_data):
        """Test getting recent buys."""
        buys = tracker_with_data.get_recent_buys(days=30)
        
        assert len(buys) >= 1
        assert all(t.is_buy for t in buys)
    
    def test_get_ceo_transactions(self, tracker_with_data):
        """Test getting CEO transactions."""
        ceo_txns = tracker_with_data.get_ceo_transactions(days=90)
        
        assert len(ceo_txns) >= 1
        assert all(t.insider_type == InsiderType.CEO for t in ceo_txns)
    
    def test_get_summary(self, tracker_with_data):
        """Test getting summary."""
        summary = tracker_with_data.get_summary("AAPL", days=90)
        
        assert summary.symbol == "AAPL"
        assert summary.total_transactions >= 3
        assert summary.buy_count >= 3
    
    def test_top_bought(self, tracker_with_data):
        """Test getting top bought symbols."""
        top = tracker_with_data.get_top_bought(days=30, limit=5)
        
        assert len(top) >= 1
        # Should be sorted by value descending
        values = [v for _, v in top]
        assert values == sorted(values, reverse=True)


# =============================================================================
# Test Cluster Detection
# =============================================================================

class TestClusterDetector:
    """Tests for ClusterDetector."""
    
    def test_detect_clusters(self, tracker_with_data):
        """Test cluster detection."""
        detector = ClusterDetector(tracker_with_data)
        clusters = detector.detect_clusters(days=90)
        
        # Should detect AAPL cluster (3 insiders) and XYZ cluster (3 insiders)
        assert len(clusters) >= 2
    
    def test_cluster_properties(self, tracker_with_data):
        """Test cluster properties."""
        detector = ClusterDetector(tracker_with_data)
        clusters = detector.detect_clusters(days=90)
        
        for cluster in clusters:
            assert cluster.insider_count >= 2
            assert cluster.total_value > 0
            assert len(cluster.transactions) >= 2
    
    def test_strongest_clusters(self, tracker_with_data):
        """Test getting strongest clusters."""
        detector = ClusterDetector(tracker_with_data)
        detector.detect_clusters(days=90)
        
        strongest = detector.get_strongest_clusters(limit=5)
        
        # Should be sorted by score
        scores = [c.cluster_score for c in strongest]
        assert scores == sorted(scores, reverse=True)


# =============================================================================
# Test Institutional Tracker
# =============================================================================

class TestInstitutionalTracker:
    """Tests for InstitutionalTracker."""
    
    def test_add_holding(self):
        """Test adding holding."""
        tracker = InstitutionalTracker()
        
        holding = InstitutionalHolding(
            institution_name="Vanguard",
            symbol="AAPL",
            shares=1_000_000,
            value=185_000_000,
        )
        tracker.add_holding(holding)
        
        retrieved = tracker.get_holding(holding.holding_id)
        assert retrieved is not None
    
    def test_get_top_holders(self):
        """Test getting top holders."""
        tracker = generate_sample_institutional()
        
        holders = tracker.get_top_holders("AAPL", limit=5)
        
        assert len(holders) == 5
        # Should be sorted by value
        values = [h.value for h in holders]
        assert values == sorted(values, reverse=True)
    
    def test_new_positions(self):
        """Test getting new positions."""
        tracker = generate_sample_institutional()
        
        new = tracker.get_new_positions()
        
        assert len(new) >= 1
        assert all(h.is_new_position for h in new)
    
    def test_summary(self):
        """Test institutional summary."""
        tracker = generate_sample_institutional()
        
        summary = tracker.get_summary("AAPL")
        
        assert summary.total_institutions == 5
        assert summary.total_value > 0


# =============================================================================
# Test Profile Manager
# =============================================================================

class TestProfileManager:
    """Tests for ProfileManager."""
    
    def test_build_profiles(self, tracker_with_data):
        """Test building profiles."""
        manager = ProfileManager(tracker_with_data)
        manager.build_profiles()
        
        profiles = manager.get_all_profiles()
        assert len(profiles) >= 5
    
    def test_get_profile(self, tracker_with_data):
        """Test getting specific profile."""
        manager = ProfileManager(tracker_with_data)
        manager.build_profiles()
        
        profile = manager.get_profile("Tim Cook")
        
        assert profile is not None
        assert profile.name == "Tim Cook"
        assert "AAPL" in profile.companies
    
    def test_top_buyers(self, tracker_with_data):
        """Test getting top buyers."""
        manager = ProfileManager(tracker_with_data)
        manager.build_profiles()
        
        top = manager.get_top_buyers(limit=5)
        
        assert len(top) >= 1
        # Should be sorted by buy value
        values = [p.total_buy_value for p in top]
        assert values == sorted(values, reverse=True)


# =============================================================================
# Test Signal Generator
# =============================================================================

class TestSignalGenerator:
    """Tests for SignalGenerator."""
    
    def test_generate_signals(self, tracker_with_data):
        """Test generating signals."""
        detector = ClusterDetector(tracker_with_data)
        generator = SignalGenerator(tracker_with_data, detector)
        
        signals = generator.generate_signals(days=90)
        
        assert len(signals) >= 1
    
    def test_signal_types(self, tracker_with_data):
        """Test signal types are set."""
        detector = ClusterDetector(tracker_with_data)
        generator = SignalGenerator(tracker_with_data, detector)
        
        signals = generator.generate_signals(days=90)
        
        signal_types = set(s.signal_type for s in signals)
        # Should have cluster_buy signals
        assert "cluster_buy" in signal_types or "ceo_buy" in signal_types
    
    def test_strongest_signals(self, tracker_with_data):
        """Test getting strongest signals."""
        detector = ClusterDetector(tracker_with_data)
        generator = SignalGenerator(tracker_with_data, detector)
        generator.generate_signals(days=90)
        
        strongest = generator.get_strongest_signals(limit=5)
        
        assert len(strongest) >= 1


# =============================================================================
# Test Alert Manager
# =============================================================================

class TestAlertManager:
    """Tests for AlertManager."""
    
    def test_default_alerts(self):
        """Test creating default alerts."""
        alerts = create_default_alerts()
        
        assert len(alerts) >= 3
    
    def test_check_alerts(self, tracker_with_data):
        """Test checking alerts."""
        detector = ClusterDetector(tracker_with_data)
        generator = SignalGenerator(tracker_with_data, detector)
        signals = generator.generate_signals(days=90)
        
        manager = AlertManager(generator)
        for alert in create_default_alerts():
            manager.add_alert(alert)
        
        notifications = manager.check_alerts(signals)
        
        # Should trigger some alerts
        assert isinstance(notifications, list)
