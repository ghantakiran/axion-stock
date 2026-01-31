"""Tests for Earnings Calendar & Analysis."""

import pytest
from datetime import date, timedelta

from src.earnings import (
    # Config
    EarningsTime, SurpriseType, AlertType, QualityRating,
    # Models
    EarningsEvent, EarningsEstimate, QuarterlyEarnings,
    # Calendar
    EarningsCalendar, generate_sample_calendar,
    # Estimates
    EstimateTracker, generate_sample_estimates,
    # History
    HistoryAnalyzer, generate_sample_history,
    # Quality
    QualityAnalyzer, FinancialData,
    # Reactions
    ReactionAnalyzer,
    # Alerts
    EarningsAlertManager,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_event():
    """Sample earnings event."""
    return EarningsEvent(
        symbol="AAPL",
        company_name="Apple Inc.",
        report_date=date.today() + timedelta(days=3),
        report_time=EarningsTime.AFTER_MARKET,
        fiscal_quarter="Q1 2025",
        fiscal_year=2025,
        eps_estimate=2.10,
        revenue_estimate=94.5e9,
    )


@pytest.fixture
def reported_event():
    """Event with actuals reported."""
    return EarningsEvent(
        symbol="MSFT",
        company_name="Microsoft Corp.",
        report_date=date.today() - timedelta(days=1),
        report_time=EarningsTime.AFTER_MARKET,
        fiscal_quarter="Q4 2024",
        eps_estimate=2.95,
        eps_actual=3.05,
        revenue_estimate=62.0e9,
        revenue_actual=63.2e9,
        is_reported=True,
    )


@pytest.fixture
def sample_financial_data():
    """Sample financial data for quality analysis."""
    return FinancialData(
        revenue=100e9,
        cost_of_revenue=60e9,
        gross_profit=40e9,
        operating_income=25e9,
        net_income=20e9,
        operating_cash_flow=25e9,
        receivables=15e9,
        current_assets=50e9,
        total_assets=200e9,
        ppe=80e9,
        total_liabilities=100e9,
        long_term_debt=40e9,
        depreciation=10e9,
        sga_expense=10e9,
        # Prior period
        revenue_prior=90e9,
        gross_profit_prior=36e9,
        receivables_prior=12e9,
        current_assets_prior=45e9,
        total_assets_prior=180e9,
        ppe_prior=75e9,
        depreciation_prior=9e9,
        sga_expense_prior=9e9,
        long_term_debt_prior=35e9,
    )


# =============================================================================
# Test Earnings Event
# =============================================================================

class TestEarningsEvent:
    """Tests for EarningsEvent model."""
    
    def test_eps_surprise(self, reported_event):
        """Test EPS surprise calculation."""
        assert reported_event.eps_surprise == pytest.approx(0.10, rel=0.01)
    
    def test_eps_surprise_pct(self, reported_event):
        """Test EPS surprise percentage."""
        # (3.05 - 2.95) / 2.95 = 3.39%
        assert reported_event.eps_surprise_pct == pytest.approx(0.0339, rel=0.01)
    
    def test_surprise_type_beat(self, reported_event):
        """Test surprise type detection for beat."""
        assert reported_event.surprise_type == SurpriseType.BEAT
    
    def test_surprise_type_miss(self):
        """Test surprise type detection for miss."""
        event = EarningsEvent(
            eps_estimate=2.00,
            eps_actual=1.80,
            is_reported=True,
        )
        assert event.surprise_type == SurpriseType.MISS


# =============================================================================
# Test Earnings Calendar
# =============================================================================

class TestEarningsCalendar:
    """Tests for EarningsCalendar."""
    
    def test_add_event(self, sample_event):
        """Test adding an event."""
        calendar = EarningsCalendar()
        calendar.add_event(sample_event)
        
        retrieved = calendar.get_event(sample_event.event_id)
        assert retrieved is not None
        assert retrieved.symbol == "AAPL"
    
    def test_get_events_for_symbol(self, sample_event):
        """Test getting events by symbol."""
        calendar = EarningsCalendar()
        calendar.add_event(sample_event)
        
        events = calendar.get_events_for_symbol("AAPL")
        assert len(events) == 1
        assert events[0].symbol == "AAPL"
    
    def test_get_next_event(self, sample_event):
        """Test getting next upcoming event."""
        calendar = EarningsCalendar()
        calendar.add_event(sample_event)
        
        next_event = calendar.get_next_event("AAPL")
        assert next_event is not None
        assert next_event.symbol == "AAPL"
    
    def test_get_day(self, sample_event):
        """Test getting events for a specific day."""
        calendar = EarningsCalendar()
        calendar.add_event(sample_event)
        
        events = calendar.get_day(sample_event.report_date)
        assert len(events) == 1
    
    def test_get_upcoming(self, sample_event):
        """Test getting upcoming events."""
        calendar = EarningsCalendar()
        calendar.add_event(sample_event)
        
        upcoming = calendar.get_upcoming(days=7)
        assert len(upcoming) >= 1
    
    def test_generate_sample_calendar(self):
        """Test sample calendar generation."""
        calendar = generate_sample_calendar()
        events = calendar.get_all_events()
        
        assert len(events) >= 5


# =============================================================================
# Test Estimate Tracker
# =============================================================================

class TestEstimateTracker:
    """Tests for EstimateTracker."""
    
    def test_add_estimate(self):
        """Test adding an estimate."""
        tracker = EstimateTracker()
        
        estimate = EarningsEstimate(
            symbol="AAPL",
            fiscal_quarter="Q1 2025",
            eps_consensus=2.10,
            eps_high=2.25,
            eps_low=1.95,
        )
        
        tracker.add_estimate(estimate)
        retrieved = tracker.get_estimate("AAPL", "Q1 2025")
        
        assert retrieved is not None
        assert retrieved.eps_consensus == 2.10
    
    def test_eps_spread(self):
        """Test EPS spread calculation."""
        estimate = EarningsEstimate(
            eps_consensus=2.10,
            eps_high=2.25,
            eps_low=1.95,
        )
        
        assert estimate.eps_spread == pytest.approx(0.30, rel=0.01)
    
    def test_revision_trend(self):
        """Test revision trend detection."""
        estimate = EarningsEstimate(
            eps_revisions_up=5,
            eps_revisions_down=2,
        )
        assert estimate.revision_trend == "positive"
        
        estimate2 = EarningsEstimate(
            eps_revisions_up=1,
            eps_revisions_down=4,
        )
        assert estimate2.revision_trend == "negative"
    
    def test_generate_sample_estimates(self):
        """Test sample estimates generation."""
        tracker = generate_sample_estimates()
        
        aapl = tracker.get_estimate("AAPL", "Q4 2025")
        assert aapl is not None


# =============================================================================
# Test History Analyzer
# =============================================================================

class TestHistoryAnalyzer:
    """Tests for HistoryAnalyzer."""
    
    def test_add_quarterly_data(self):
        """Test adding quarterly data."""
        analyzer = HistoryAnalyzer()
        
        quarters = [
            QuarterlyEarnings(
                symbol="TEST", fiscal_quarter="Q1 2024",
                report_date=date(2024, 1, 30),
                eps_estimate=1.00, eps_actual=1.10,
                revenue_estimate=10e9, revenue_actual=10.5e9,
            ),
            QuarterlyEarnings(
                symbol="TEST", fiscal_quarter="Q2 2024",
                report_date=date(2024, 4, 30),
                eps_estimate=1.05, eps_actual=1.08,
                revenue_estimate=10.5e9, revenue_actual=10.7e9,
            ),
        ]
        
        history = analyzer.add_quarterly_data("TEST", quarters)
        
        assert history.beat_rate_eps == 1.0  # Both quarters beat
        assert history.consecutive_beats == 2
    
    def test_generate_sample_history(self):
        """Test sample history generation."""
        analyzer = generate_sample_history()
        
        history = analyzer.get_history("AAPL")
        assert history is not None
        assert len(history.quarters) >= 4


# =============================================================================
# Test Quality Analyzer
# =============================================================================

class TestQualityAnalyzer:
    """Tests for QualityAnalyzer."""
    
    def test_analyze_quality(self, sample_financial_data):
        """Test quality analysis."""
        analyzer = QualityAnalyzer()
        
        quality = analyzer.analyze("TEST", sample_financial_data)
        
        assert quality is not None
        assert quality.symbol == "TEST"
        assert 0 <= quality.overall_quality_score <= 100
    
    def test_beneish_mscore(self, sample_financial_data):
        """Test Beneish M-Score calculation."""
        analyzer = QualityAnalyzer()
        
        quality = analyzer.analyze("TEST", sample_financial_data)
        
        # M-Score should be calculated
        assert quality.beneish_m_score != 0
    
    def test_cash_conversion(self, sample_financial_data):
        """Test cash conversion calculation."""
        analyzer = QualityAnalyzer()
        
        quality = analyzer.analyze("TEST", sample_financial_data)
        
        # CFO/NI = 25/20 = 1.25
        assert quality.cash_conversion == pytest.approx(1.25, rel=0.01)
    
    def test_quality_rating(self, sample_financial_data):
        """Test quality rating determination."""
        analyzer = QualityAnalyzer()
        
        quality = analyzer.analyze("TEST", sample_financial_data)
        
        assert quality.quality_rating in [
            QualityRating.HIGH,
            QualityRating.MEDIUM,
            QualityRating.LOW,
            QualityRating.WARNING,
        ]


# =============================================================================
# Test Reaction Analyzer
# =============================================================================

class TestReactionAnalyzer:
    """Tests for ReactionAnalyzer."""
    
    def test_record_reaction(self):
        """Test recording a price reaction."""
        analyzer = ReactionAnalyzer()
        
        reaction = analyzer.record_reaction(
            symbol="AAPL",
            fiscal_quarter="Q1 2025",
            report_date=date(2025, 1, 30),
            price_5d_before=180.0,
            price_1d_before=185.0,
            volume_avg=50e6,
            open_price=195.0,  # Gap up
            close_price=192.0,
            high_price=198.0,
            low_price=190.0,
            volume=100e6,
            price_1d_after=193.0,
            price_5d_after=195.0,
        )
        
        assert reaction.gap_open_pct == pytest.approx(0.054, rel=0.01)
        assert reaction.volume_ratio == pytest.approx(2.0, rel=0.01)
    
    def test_get_reaction(self):
        """Test getting a recorded reaction."""
        analyzer = ReactionAnalyzer()
        
        analyzer.record_reaction(
            symbol="TEST",
            fiscal_quarter="Q1 2025",
            report_date=date(2025, 1, 30),
            price_5d_before=100.0,
            price_1d_before=100.0,
            volume_avg=1e6,
        )
        
        reaction = analyzer.get_reaction("TEST", "Q1 2025")
        assert reaction is not None


# =============================================================================
# Test Alert Manager
# =============================================================================

class TestEarningsAlertManager:
    """Tests for EarningsAlertManager."""
    
    def test_upcoming_alerts(self, sample_event):
        """Test upcoming earnings alerts."""
        manager = EarningsAlertManager()
        
        # Set event to trigger alert (3 days out)
        sample_event.report_date = date.today() + timedelta(days=3)
        
        alerts = manager.check_upcoming_earnings([sample_event])
        
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.UPCOMING
    
    def test_released_alert(self, reported_event):
        """Test earnings released alert."""
        manager = EarningsAlertManager()
        
        alert = manager.check_earnings_released(reported_event)
        
        assert alert is not None
        assert alert.alert_type == AlertType.RELEASED
    
    def test_surprise_alert(self, reported_event):
        """Test surprise alert for significant beat/miss."""
        manager = EarningsAlertManager()
        
        # Large beat
        reported_event.eps_estimate = 2.00
        reported_event.eps_actual = 2.30  # 15% beat
        
        alert = manager.check_surprise_alert(reported_event)
        
        assert alert is not None
        assert alert.alert_type == AlertType.SURPRISE
    
    def test_revision_alert(self):
        """Test estimate revision alert."""
        manager = EarningsAlertManager()
        
        alert = manager.check_revision_alert(
            symbol="AAPL",
            old_estimate=2.00,
            new_estimate=2.20,  # 10% increase
            fiscal_quarter="Q1 2025",
        )
        
        assert alert is not None
        assert alert.alert_type == AlertType.REVISION
    
    def test_get_alerts_filtered(self, sample_event, reported_event):
        """Test filtering alerts."""
        manager = EarningsAlertManager()
        
        # Generate different alert types
        sample_event.report_date = date.today() + timedelta(days=3)
        manager.check_upcoming_earnings([sample_event])
        manager.check_earnings_released(reported_event)
        
        # Filter by symbol
        aapl_alerts = manager.get_alerts(symbol="AAPL")
        assert all(a.symbol == "AAPL" for a in aapl_alerts)
        
        # Filter by type
        upcoming_alerts = manager.get_alerts(alert_type=AlertType.UPCOMING)
        assert all(a.alert_type == AlertType.UPCOMING for a in upcoming_alerts)
