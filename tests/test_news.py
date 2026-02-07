"""Tests for News & Events Integration."""

import pytest
from datetime import date, datetime, timedelta, timezone

from src.news import (
    # Config
    NewsCategory, NewsSource, SentimentLabel, ReportTime,
    EventImportance, EconomicCategory, FilingType,
    InsiderTransactionType, CorporateEventType, DividendFrequency,
    AlertTrigger, DEFAULT_NEWS_CONFIG,
    # Models
    NewsArticle, EarningsEvent, EconomicEvent, SECFiling,
    InsiderTransaction, DividendEvent, CorporateEvent, NewsAlert,
    # Managers
    NewsFeedManager, EarningsCalendar, EconomicCalendar,
    SECFilingsTracker, CorporateEventsTracker, NewsAlertManager,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def news_feed():
    """Create a NewsFeedManager with sample articles."""
    manager = NewsFeedManager()
    
    # Add sample articles
    manager.add_article(NewsArticle(
        headline="AAPL beats earnings expectations",
        summary="Apple reported strong Q4 results with EPS beating estimates.",
        source=NewsSource.REUTERS,
        symbols=["AAPL"],
        categories=[NewsCategory.EARNINGS],
        published_at=datetime.now(timezone.utc) - timedelta(hours=2),
    ))
    
    manager.add_article(NewsArticle(
        headline="Fed signals potential rate cut",
        summary="Federal Reserve indicates possible rate cuts in 2024.",
        source=NewsSource.BLOOMBERG,
        symbols=[],
        categories=[NewsCategory.MACRO],
        published_at=datetime.now(timezone.utc) - timedelta(hours=4),
        is_breaking=True,
    ))
    
    manager.add_article(NewsArticle(
        headline="MSFT announces new AI partnership",
        summary="Microsoft expands AI capabilities with new strategic partnership.",
        source=NewsSource.CNBC,
        symbols=["MSFT"],
        categories=[NewsCategory.PRODUCT],
        published_at=datetime.now(timezone.utc) - timedelta(hours=6),
    ))
    
    manager.add_article(NewsArticle(
        headline="TSLA misses delivery estimates",
        summary="Tesla deliveries fall short of analyst expectations for Q4.",
        source=NewsSource.MARKETWATCH,
        symbols=["TSLA"],
        categories=[NewsCategory.EARNINGS],
        published_at=datetime.now(timezone.utc) - timedelta(hours=8),
    ))
    
    return manager


@pytest.fixture
def earnings_calendar():
    """Create an EarningsCalendar with sample events."""
    calendar = EarningsCalendar()
    
    # Add upcoming earnings
    calendar.add_event(EarningsEvent(
        symbol="AAPL",
        company_name="Apple Inc.",
        report_date=date.today() + timedelta(days=5),
        report_time=ReportTime.AMC,
        fiscal_quarter="Q1 2024",
        eps_estimate=2.10,
        revenue_estimate=120_000_000_000,
        num_analysts=30,
    ))
    
    calendar.add_event(EarningsEvent(
        symbol="MSFT",
        company_name="Microsoft Corporation",
        report_date=date.today() + timedelta(days=10),
        report_time=ReportTime.AMC,
        fiscal_quarter="Q2 2024",
        eps_estimate=2.75,
        revenue_estimate=65_000_000_000,
        num_analysts=35,
    ))
    
    # Add historical earnings with actuals
    calendar.add_event(EarningsEvent(
        symbol="AAPL",
        company_name="Apple Inc.",
        report_date=date.today() - timedelta(days=90),
        report_time=ReportTime.AMC,
        fiscal_quarter="Q4 2023",
        eps_estimate=1.95,
        eps_actual=2.05,
        revenue_estimate=90_000_000_000,
        revenue_actual=92_000_000_000,
    ))
    
    return calendar


@pytest.fixture
def economic_calendar():
    """Create an EconomicCalendar with sample events."""
    calendar = EconomicCalendar()
    
    calendar.add_event(EconomicEvent(
        name="FOMC Meeting",
        category=EconomicCategory.CENTRAL_BANK,
        country="US",
        release_date=datetime.now(timezone.utc) + timedelta(days=3),
        importance=EventImportance.HIGH,
    ))
    
    calendar.add_event(EconomicEvent(
        name="Non-Farm Payrolls",
        category=EconomicCategory.EMPLOYMENT,
        country="US",
        release_date=datetime.now(timezone.utc) + timedelta(days=7),
        importance=EventImportance.HIGH,
        forecast=200_000,
        previous=180_000,
    ))
    
    calendar.add_event(EconomicEvent(
        name="CPI",
        category=EconomicCategory.INFLATION,
        country="US",
        release_date=datetime.now(timezone.utc) - timedelta(days=5),
        importance=EventImportance.HIGH,
        forecast=3.2,
        previous=3.4,
        actual=3.1,
    ))
    
    return calendar


@pytest.fixture
def sec_tracker():
    """Create an SECFilingsTracker with sample filings."""
    tracker = SECFilingsTracker()
    
    tracker.add_filing(SECFiling(
        symbol="AAPL",
        company_name="Apple Inc.",
        cik="0000320193",
        form_type=FilingType.FORM_10Q,
        filed_date=date.today() - timedelta(days=10),
        url="https://www.sec.gov/...",
    ))
    
    tracker.add_filing(SECFiling(
        symbol="MSFT",
        company_name="Microsoft Corporation",
        cik="0000789019",
        form_type=FilingType.FORM_8K,
        filed_date=date.today() - timedelta(days=3),
        description="Material event disclosure",
    ))
    
    tracker.add_insider_transaction(InsiderTransaction(
        symbol="AAPL",
        insider_name="Tim Cook",
        insider_title="CEO",
        transaction_date=date.today() - timedelta(days=5),
        transaction_type=InsiderTransactionType.SELL,
        shares=50000,
        price=175.50,
        is_officer=True,
    ))
    
    return tracker


@pytest.fixture
def corporate_events():
    """Create a CorporateEventsTracker with sample events."""
    tracker = CorporateEventsTracker()
    
    tracker.add_dividend(DividendEvent(
        symbol="AAPL",
        company_name="Apple Inc.",
        ex_date=date.today() + timedelta(days=10),
        record_date=date.today() + timedelta(days=12),
        pay_date=date.today() + timedelta(days=20),
        amount=0.24,
        frequency=DividendFrequency.QUARTERLY,
    ))
    
    tracker.add_event(CorporateEvent(
        symbol="TSLA",
        company_name="Tesla Inc.",
        event_type=CorporateEventType.STOCK_SPLIT,
        event_date=date.today() + timedelta(days=30),
        split_ratio="3:1",
    ))
    
    return tracker


# =============================================================================
# Test News Feed
# =============================================================================

class TestNewsFeedManager:
    """Tests for NewsFeedManager."""
    
    def test_add_article(self):
        """Test adding an article."""
        manager = NewsFeedManager()
        
        article = manager.add_article(NewsArticle(
            headline="Test headline",
            summary="Test summary",
            source=NewsSource.REUTERS,
            symbols=["AAPL"],
        ))
        
        assert article.article_id is not None
        assert article.headline == "Test headline"
    
    def test_sentiment_analysis(self):
        """Test automatic sentiment analysis."""
        manager = NewsFeedManager()
        
        positive_article = manager.add_article(NewsArticle(
            headline="Company beats expectations with strong growth",
            summary="Revenue and profit surge to record levels",
            symbols=["TEST"],
        ))
        
        negative_article = manager.add_article(NewsArticle(
            headline="Company misses estimates, warns of decline",
            summary="Loss widens as sales fall sharply",
            symbols=["TEST"],
        ))
        
        assert positive_article.sentiment_score > 0
        assert negative_article.sentiment_score < 0
    
    def test_get_feed(self, news_feed):
        """Test getting filtered news feed."""
        # All articles
        all_articles = news_feed.get_feed(limit=10)
        assert len(all_articles) == 4
        
        # Filter by symbol
        aapl_articles = news_feed.get_feed(symbols=["AAPL"])
        assert len(aapl_articles) == 1
        assert aapl_articles[0].symbols == ["AAPL"]
    
    def test_get_breaking_news(self, news_feed):
        """Test getting breaking news."""
        breaking = news_feed.get_breaking_news()
        assert len(breaking) == 1
        assert breaking[0].is_breaking is True
    
    def test_search(self, news_feed):
        """Test full-text search."""
        results = news_feed.search("AI partnership")
        assert len(results) >= 1
        assert "MSFT" in results[0].symbols
    
    def test_mark_read(self, news_feed):
        """Test marking articles as read."""
        articles = news_feed.get_feed(limit=1)
        article_id = articles[0].article_id
        
        assert news_feed.mark_read(article_id) is True
        assert news_feed.get_article(article_id).is_read is True
    
    def test_sentiment_summary(self, news_feed):
        """Test sentiment summary calculation."""
        summary = news_feed.get_sentiment_summary()
        
        assert "total_articles" in summary
        assert "average_sentiment" in summary
        assert summary["total_articles"] == 4


# =============================================================================
# Test Earnings Calendar
# =============================================================================

class TestEarningsCalendar:
    """Tests for EarningsCalendar."""
    
    def test_add_event(self):
        """Test adding an earnings event."""
        calendar = EarningsCalendar()
        
        event = calendar.add_event(EarningsEvent(
            symbol="AAPL",
            company_name="Apple Inc.",
            report_date=date.today() + timedelta(days=5),
        ))
        
        assert event.event_id is not None
        assert event.symbol == "AAPL"
    
    def test_get_upcoming(self, earnings_calendar):
        """Test getting upcoming earnings."""
        upcoming = earnings_calendar.get_upcoming(days=30)
        assert len(upcoming) == 2
        
        # Should be sorted by date
        assert upcoming[0].report_date <= upcoming[1].report_date
    
    def test_earnings_surprise(self, earnings_calendar):
        """Test earnings surprise calculation."""
        historical = earnings_calendar.get_for_symbol("AAPL", quarters=4)
        reported = [e for e in historical if e.is_reported]
        
        assert len(reported) >= 1
        event = reported[0]
        
        assert event.eps_surprise == pytest.approx(0.10, abs=0.001)  # 2.05 - 1.95
        assert event.is_beat is True
    
    def test_update_actuals(self, earnings_calendar):
        """Test updating with actual results."""
        upcoming = earnings_calendar.get_upcoming(days=30, symbols=["AAPL"])
        event = upcoming[0]
        
        updated = earnings_calendar.update_actuals(
            event.event_id,
            eps_actual=2.15,
            revenue_actual=125_000_000_000,
        )
        
        assert updated.eps_actual == 2.15
        assert updated.is_reported is True
        assert updated.is_beat is True
    
    def test_get_beats(self, earnings_calendar):
        """Test getting earnings beats."""
        beats = earnings_calendar.get_beats(days=180)
        assert len(beats) >= 1
        assert all(e.is_beat for e in beats)


# =============================================================================
# Test Economic Calendar
# =============================================================================

class TestEconomicCalendar:
    """Tests for EconomicCalendar."""
    
    def test_add_event(self):
        """Test adding an economic event."""
        calendar = EconomicCalendar()
        
        event = calendar.add_event(EconomicEvent(
            name="GDP",
            category=EconomicCategory.GROWTH,
            release_date=datetime.now(timezone.utc) + timedelta(days=5),
        ))
        
        assert event.event_id is not None
        assert event.name == "GDP"
    
    def test_get_upcoming(self, economic_calendar):
        """Test getting upcoming economic events."""
        upcoming = economic_calendar.get_upcoming(days=14)
        assert len(upcoming) >= 2
    
    def test_get_high_impact(self, economic_calendar):
        """Test getting high impact events."""
        high_impact = economic_calendar.get_high_impact_events(days=14)
        assert all(e.importance == EventImportance.HIGH for e in high_impact)
    
    def test_economic_surprise(self, economic_calendar):
        """Test economic surprise calculation."""
        # The CPI event has actual data
        cpi_events = economic_calendar.get_by_category(EconomicCategory.INFLATION)
        released = [e for e in cpi_events if e.is_released]
        
        assert len(released) >= 1
        event = released[0]
        assert event.surprise == pytest.approx(-0.1, abs=0.001)  # 3.1 - 3.2
    
    def test_get_fomc_meetings(self, economic_calendar):
        """Test getting FOMC meetings."""
        fomc = economic_calendar.get_fomc_meetings()
        assert len(fomc) >= 1


# =============================================================================
# Test SEC Filings
# =============================================================================

class TestSECFilingsTracker:
    """Tests for SECFilingsTracker."""
    
    def test_add_filing(self):
        """Test adding a filing."""
        tracker = SECFilingsTracker()
        
        filing = tracker.add_filing(SECFiling(
            symbol="AAPL",
            form_type=FilingType.FORM_8K,
            filed_date=date.today(),
        ))
        
        assert filing.filing_id is not None
        assert filing.form_type == FilingType.FORM_8K
    
    def test_get_recent_filings(self, sec_tracker):
        """Test getting recent filings."""
        filings = sec_tracker.get_recent_filings(days=30)
        assert len(filings) == 2
    
    def test_get_8k_filings(self, sec_tracker):
        """Test getting 8-K filings."""
        filings = sec_tracker.get_8k_filings(days=30)
        assert len(filings) == 1
        assert filings[0].form_type == FilingType.FORM_8K
    
    def test_insider_transactions(self, sec_tracker):
        """Test insider transaction tracking."""
        txns = sec_tracker.get_insider_transactions(days=30)
        assert len(txns) == 1
        
        txn = txns[0]
        assert txn.insider_name == "Tim Cook"
        assert txn.is_sale is True
        assert txn.value == 50000 * 175.50
    
    def test_insider_summary(self, sec_tracker):
        """Test insider summary."""
        summary = sec_tracker.get_insider_summary("AAPL", days=30)
        
        assert summary["symbol"] == "AAPL"
        assert summary["sell_count"] == 1
        assert summary["sell_shares"] == 50000


# =============================================================================
# Test Corporate Events
# =============================================================================

class TestCorporateEventsTracker:
    """Tests for CorporateEventsTracker."""
    
    def test_add_dividend(self):
        """Test adding a dividend."""
        tracker = CorporateEventsTracker()
        
        dividend = tracker.add_dividend(DividendEvent(
            symbol="MSFT",
            ex_date=date.today() + timedelta(days=5),
            amount=0.75,
        ))
        
        assert dividend.event_id is not None
        assert dividend.amount == 0.75
    
    def test_get_upcoming_dividends(self, corporate_events):
        """Test getting upcoming dividends."""
        dividends = corporate_events.get_upcoming_dividends(days=30)
        assert len(dividends) >= 1
    
    def test_dividend_stats(self, corporate_events):
        """Test dividend statistics."""
        stats = corporate_events.get_dividend_stats("AAPL")
        
        assert stats["symbol"] == "AAPL"
        assert stats["has_dividend"] is True
        assert stats["latest_amount"] == 0.24
    
    def test_get_upcoming_splits(self, corporate_events):
        """Test getting upcoming splits."""
        splits = corporate_events.get_upcoming_splits(days=60)
        assert len(splits) >= 1
        assert splits[0].split_ratio == "3:1"


# =============================================================================
# Test News Alerts
# =============================================================================

class TestNewsAlertManager:
    """Tests for NewsAlertManager."""
    
    def test_create_alert(self):
        """Test creating an alert."""
        manager = NewsAlertManager()
        
        alert = manager.create_alert(
            user_id="user1",
            name="AAPL News",
            trigger=AlertTrigger.SYMBOL_NEWS,
            symbols=["AAPL"],
        )
        
        assert alert.alert_id is not None
        assert alert.name == "AAPL News"
        assert alert.enabled is True
    
    def test_get_user_alerts(self):
        """Test getting alerts for a user."""
        manager = NewsAlertManager()
        
        manager.create_alert("user1", "Alert 1", AlertTrigger.SYMBOL_NEWS, ["AAPL"])
        manager.create_alert("user1", "Alert 2", AlertTrigger.EARNINGS_ANNOUNCE, ["MSFT"])
        manager.create_alert("user2", "Alert 3", AlertTrigger.BREAKING_NEWS)
        
        user1_alerts = manager.get_user_alerts("user1")
        assert len(user1_alerts) == 2
    
    def test_evaluate_article(self):
        """Test evaluating article against alerts."""
        manager = NewsAlertManager()
        
        manager.create_alert(
            user_id="user1",
            name="AAPL News",
            trigger=AlertTrigger.SYMBOL_NEWS,
            symbols=["AAPL"],
        )
        
        article = NewsArticle(
            headline="AAPL announces new product",
            symbols=["AAPL"],
        )
        
        notifications = manager.evaluate_article(article)
        assert len(notifications) == 1
        assert notifications[0].symbol == "AAPL"
    
    def test_evaluate_earnings(self):
        """Test evaluating earnings against alerts."""
        manager = NewsAlertManager()
        
        manager.create_alert(
            user_id="user1",
            name="Earnings Surprises",
            trigger=AlertTrigger.EARNINGS_SURPRISE,
            symbols=["AAPL"],
        )
        
        event = EarningsEvent(
            symbol="AAPL",
            company_name="Apple Inc.",
            report_date=date.today(),
            eps_estimate=2.00,
            eps_actual=2.20,  # 10% beat
        )
        
        notifications = manager.evaluate_earnings(event)
        assert len(notifications) == 1
        assert "beat" in notifications[0].message.lower()
    
    def test_disable_enable_alert(self):
        """Test disabling and enabling alerts."""
        manager = NewsAlertManager()
        
        alert = manager.create_alert(
            user_id="user1",
            name="Test",
            trigger=AlertTrigger.SYMBOL_NEWS,
        )
        
        assert manager.disable_alert(alert.alert_id) is True
        assert manager.get_alert(alert.alert_id).enabled is False
        
        assert manager.enable_alert(alert.alert_id) is True
        assert manager.get_alert(alert.alert_id).enabled is True
    
    def test_notification_tracking(self):
        """Test notification tracking."""
        manager = NewsAlertManager()
        
        manager.create_alert(
            user_id="user1",
            name="Test",
            trigger=AlertTrigger.SYMBOL_NEWS,
            symbols=["AAPL"],
        )
        
        article = NewsArticle(headline="AAPL news", symbols=["AAPL"])
        manager.evaluate_article(article)
        
        notifs = manager.get_notifications("user1")
        assert len(notifs) == 1
        assert manager.get_unread_count("user1") == 1
        
        manager.mark_read(notifs[0].notification_id)
        assert manager.get_unread_count("user1") == 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_full_news_workflow(self):
        """Test complete news workflow."""
        # Setup
        news = NewsFeedManager()
        alerts = NewsAlertManager()
        
        # Create alert
        alerts.create_alert(
            user_id="user1",
            name="Tech News",
            trigger=AlertTrigger.SYMBOL_NEWS,
            symbols=["AAPL", "MSFT", "GOOGL"],
            categories=[NewsCategory.EARNINGS],
        )
        
        # Add article
        article = news.add_article(NewsArticle(
            headline="AAPL reports record earnings",
            summary="Apple beats expectations",
            symbols=["AAPL"],
            categories=[NewsCategory.EARNINGS],
        ))
        
        # Evaluate
        notifs = alerts.evaluate_article(article)
        assert len(notifs) == 1
        
        # Get feed
        feed = news.get_for_symbol("AAPL")
        assert len(feed) == 1
    
    def test_earnings_with_alerts(self):
        """Test earnings calendar with alerts."""
        earnings = EarningsCalendar()
        alerts = NewsAlertManager()
        
        # Create alert
        alerts.create_alert(
            user_id="user1",
            name="Earnings",
            trigger=AlertTrigger.EARNINGS_ANNOUNCE,
        )
        
        # Add and report earnings
        event = earnings.add_event(EarningsEvent(
            symbol="NVDA",
            company_name="NVIDIA Corp",
            report_date=date.today(),
            eps_estimate=5.00,
        ))
        
        earnings.update_actuals(event.event_id, eps_actual=5.50)
        
        # Evaluate
        updated_event = earnings.get_event(event.event_id)
        notifs = alerts.evaluate_earnings(updated_event)
        
        assert len(notifs) >= 1
