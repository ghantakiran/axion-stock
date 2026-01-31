"""Tests for Economic Calendar Module."""

import pytest
from datetime import date, time, datetime, timedelta, timezone

from src.economic import (
    # Config
    ImpactLevel, EventCategory, Country, RateDecision, AlertTrigger,
    # Models
    EconomicEvent, HistoricalRelease, FedMeeting, EventAlert,
    # Calendar
    EconomicCalendar, generate_sample_calendar,
    # History
    HistoryAnalyzer, generate_sample_history,
    # Fed
    FedWatcher, generate_sample_fed_data,
    # Alerts
    EconomicAlertManager, create_default_alerts,
    # Impact
    ImpactAnalyzer,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_event():
    """Sample economic event."""
    return EconomicEvent(
        name="Non-Farm Payrolls",
        country=Country.US,
        category=EventCategory.EMPLOYMENT,
        release_date=date.today() + timedelta(days=1),
        release_time=time(8, 30),
        impact=ImpactLevel.HIGH,
        previous=216.0,
        forecast=180.0,
        unit="K",
    )


@pytest.fixture
def released_event():
    """Released economic event."""
    return EconomicEvent(
        name="CPI",
        country=Country.US,
        category=EventCategory.INFLATION,
        release_date=date.today(),
        release_time=time(8, 30),
        impact=ImpactLevel.HIGH,
        previous=3.2,
        forecast=3.0,
        actual=3.4,
        unit="%",
        is_released=True,
    )


@pytest.fixture
def calendar_with_events():
    """Calendar with sample events."""
    return generate_sample_calendar()


# =============================================================================
# Test Economic Event
# =============================================================================

class TestEconomicEvent:
    """Tests for EconomicEvent model."""
    
    def test_surprise_calculation(self, released_event):
        """Test surprise calculation."""
        assert released_event.surprise == pytest.approx(0.4, rel=0.01)
    
    def test_surprise_pct(self, released_event):
        """Test surprise percentage."""
        # (3.4 - 3.0) / 3.0 * 100 = 13.33%
        assert released_event.surprise_pct == pytest.approx(13.33, rel=0.1)
    
    def test_beat_or_miss(self, released_event):
        """Test beat/miss determination."""
        assert released_event.beat_or_miss == "beat"
    
    def test_miss_event(self):
        """Test miss event."""
        event = EconomicEvent(
            name="Test",
            actual=2.8,
            forecast=3.0,
            is_released=True,
        )
        assert event.beat_or_miss == "miss"


# =============================================================================
# Test Economic Calendar
# =============================================================================

class TestEconomicCalendar:
    """Tests for EconomicCalendar."""
    
    def test_add_event(self, sample_event):
        """Test adding event."""
        calendar = EconomicCalendar()
        calendar.add_event(sample_event)
        
        retrieved = calendar.get_event(sample_event.event_id)
        assert retrieved is not None
        assert retrieved.name == "Non-Farm Payrolls"
    
    def test_get_day(self, calendar_with_events):
        """Test getting events for a day."""
        tomorrow = date.today() + timedelta(days=1)
        events = calendar_with_events.get_day(tomorrow)
        
        # Should have NFP and Unemployment Rate
        assert len(events) >= 1
    
    def test_get_upcoming(self, calendar_with_events):
        """Test getting upcoming events."""
        events = calendar_with_events.get_upcoming(days=14)
        
        assert len(events) >= 5
        # Should be sorted by date
        dates = [e.release_date for e in events if e.release_date]
        assert dates == sorted(dates)
    
    def test_filter_by_impact(self, calendar_with_events):
        """Test filtering by impact level."""
        high_impact = calendar_with_events.get_upcoming(
            days=14,
            min_impact=ImpactLevel.HIGH
        )
        
        for event in high_impact:
            assert event.impact == ImpactLevel.HIGH
    
    def test_filter_by_country(self, calendar_with_events):
        """Test filtering by country."""
        us_events = calendar_with_events.get_upcoming(
            days=14,
            country=Country.US
        )
        
        for event in us_events:
            assert event.country == Country.US
    
    def test_record_release(self, sample_event):
        """Test recording event release."""
        calendar = EconomicCalendar()
        calendar.add_event(sample_event)
        
        updated = calendar.record_release(
            sample_event.event_id,
            actual=195.0,
        )
        
        assert updated is not None
        assert updated.actual == 195.0
        assert updated.is_released is True


# =============================================================================
# Test History Analyzer
# =============================================================================

class TestHistoryAnalyzer:
    """Tests for HistoryAnalyzer."""
    
    def test_add_release(self):
        """Test adding historical release."""
        analyzer = HistoryAnalyzer()
        
        release = HistoricalRelease(
            event_name="Non-Farm Payrolls",
            release_date=datetime(2024, 1, 5),
            actual=216.0,
            forecast=170.0,
            previous=199.0,
        )
        
        analyzer.add_release(release)
        history = analyzer.get_history("Non-Farm Payrolls")
        
        assert len(history) == 1
        assert history[0].surprise == 46.0
    
    def test_get_stats(self):
        """Test statistics calculation."""
        analyzer = generate_sample_history()
        stats = analyzer.get_stats("Non-Farm Payrolls")
        
        assert stats.total_releases >= 4
        assert 0 <= stats.beat_rate <= 100
    
    def test_compare_to_history(self):
        """Test comparing release to history."""
        analyzer = generate_sample_history()
        
        comparison = analyzer.compare_to_history(
            "Non-Farm Payrolls",
            actual=250.0,
            forecast=180.0,
        )
        
        assert "surprise" in comparison
        assert "z_score" in comparison
        assert comparison["surprise"] == 70.0


# =============================================================================
# Test Fed Watcher
# =============================================================================

class TestFedWatcher:
    """Tests for FedWatcher."""
    
    def test_add_meeting(self):
        """Test adding Fed meeting."""
        fed = FedWatcher()
        
        meeting = FedMeeting(
            meeting_date=date.today() + timedelta(days=30),
            meeting_type="FOMC",
            rate_before=5.50,
        )
        
        fed.add_meeting(meeting)
        retrieved = fed.get_meeting(meeting.meeting_id)
        
        assert retrieved is not None
        assert retrieved.meeting_type == "FOMC"
    
    def test_get_next_meeting(self):
        """Test getting next meeting."""
        fed = generate_sample_fed_data()
        next_meeting = fed.get_next_meeting()
        
        assert next_meeting is not None
        assert next_meeting.meeting_date >= date.today()
    
    def test_get_rate_history(self):
        """Test getting rate history."""
        fed = generate_sample_fed_data()
        history = fed.get_rate_history()
        
        assert len(history) >= 1
    
    def test_calculate_implied_rate(self):
        """Test implied rate calculation."""
        fed = FedWatcher()
        
        # 80% hold, 15% cut, 5% hike
        implied = fed.calculate_implied_rate(
            prob_hike=5.0,
            prob_cut=15.0,
            rate_step=0.25,
        )
        
        # Should be close to current rate (5.50) with slight cut bias
        assert 5.45 <= implied <= 5.55


# =============================================================================
# Test Alert Manager
# =============================================================================

class TestAlertManager:
    """Tests for EconomicAlertManager."""
    
    def test_add_alert(self):
        """Test adding alert."""
        manager = EconomicAlertManager()
        
        alert = EventAlert(
            name="High Impact Alert",
            min_impact=ImpactLevel.HIGH,
            minutes_before=30,
        )
        
        manager.add_alert(alert)
        retrieved = manager.get_alert(alert.alert_id)
        
        assert retrieved is not None
        assert retrieved.name == "High Impact Alert"
    
    def test_default_alerts(self):
        """Test creating default alerts."""
        alerts = create_default_alerts()
        
        assert len(alerts) >= 3
        # Should have Fed alert
        fed_alerts = [a for a in alerts if "Fed" in a.name]
        assert len(fed_alerts) >= 1
    
    def test_check_release_alert(self, released_event):
        """Test checking release alerts."""
        manager = EconomicAlertManager()
        
        alert = EventAlert(
            name="Release Alert",
            trigger_type=AlertTrigger.RELEASED,
            on_release=True,
        )
        manager.add_alert(alert)
        
        notifications = manager.check_alerts([released_event])
        
        assert len(notifications) >= 1
        assert "Released" in notifications[0].title


# =============================================================================
# Test Impact Analyzer
# =============================================================================

class TestImpactAnalyzer:
    """Tests for ImpactAnalyzer."""
    
    def test_analyze_event(self, sample_event):
        """Test analyzing event impact."""
        history = generate_sample_history()
        analyzer = ImpactAnalyzer(history)
        
        impact = analyzer.analyze_event(sample_event)
        
        assert impact.event_name == "Non-Farm Payrolls"
        assert impact.expected_volatility > 0
    
    def test_sector_exposure(self, sample_event):
        """Test getting sector exposure."""
        analyzer = ImpactAnalyzer()
        
        sectors = analyzer.get_sector_exposure(sample_event)
        
        # NFP should have sector sensitivities
        assert len(sectors) > 0
    
    def test_pre_event_notes(self, sample_event):
        """Test pre-event note generation."""
        history = generate_sample_history()
        analyzer = ImpactAnalyzer(history)
        
        impact = analyzer.analyze_event(sample_event)
        
        # High impact event should have warning
        assert len(impact.pre_event_notes) >= 1
