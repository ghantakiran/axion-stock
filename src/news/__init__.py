"""News & Events Integration.

Comprehensive news and events system including:
- Real-time news feed with sentiment analysis
- Earnings calendar with estimates and surprises
- Economic calendar with market impact
- SEC filings tracking (10-K, 10-Q, 8-K, Form 4)
- Corporate events (dividends, splits, M&A, IPOs)
- Customizable news alerts

Example:
    from src.news import NewsFeedManager, EarningsCalendar, EconomicCalendar
    
    # News feed
    news = NewsFeedManager()
    articles = news.get_for_symbol("AAPL", limit=10)
    
    # Earnings calendar
    earnings = EarningsCalendar()
    upcoming = earnings.get_upcoming(days=14)
    
    # Economic calendar
    econ = EconomicCalendar()
    high_impact = econ.get_high_impact_events(days=7)
"""

from src.news.config import (
    NewsCategory,
    NewsSource,
    SentimentLabel,
    ReportTime,
    EventImportance,
    EconomicCategory,
    FilingType,
    InsiderTransactionType,
    CorporateEventType,
    DividendFrequency,
    AlertTrigger,
    MAJOR_ECONOMIC_EVENTS,
    HIGH_IMPORTANCE_FILINGS,
    SENTIMENT_THRESHOLDS,
    NewsFeedConfig,
    EarningsConfig,
    EconomicConfig,
    FilingsConfig,
    NewsAlertsConfig,
    NewsConfig,
    DEFAULT_NEWS_CONFIG,
)

from src.news.models import (
    NewsArticle,
    EarningsEvent,
    EconomicEvent,
    SECFiling,
    InsiderTransaction,
    DividendEvent,
    CorporateEvent,
    NewsAlert,
    AlertNotification,
)

from src.news.news_feed import NewsFeedManager
from src.news.earnings import EarningsCalendar
from src.news.economic import EconomicCalendar
from src.news.filings import SECFilingsTracker
from src.news.events import CorporateEventsTracker
from src.news.alerts import NewsAlertManager

__all__ = [
    # Config - Enums
    "NewsCategory",
    "NewsSource",
    "SentimentLabel",
    "ReportTime",
    "EventImportance",
    "EconomicCategory",
    "FilingType",
    "InsiderTransactionType",
    "CorporateEventType",
    "DividendFrequency",
    "AlertTrigger",
    # Config - Constants
    "MAJOR_ECONOMIC_EVENTS",
    "HIGH_IMPORTANCE_FILINGS",
    "SENTIMENT_THRESHOLDS",
    # Config - Dataclasses
    "NewsFeedConfig",
    "EarningsConfig",
    "EconomicConfig",
    "FilingsConfig",
    "NewsAlertsConfig",
    "NewsConfig",
    "DEFAULT_NEWS_CONFIG",
    # Models
    "NewsArticle",
    "EarningsEvent",
    "EconomicEvent",
    "SECFiling",
    "InsiderTransaction",
    "DividendEvent",
    "CorporateEvent",
    "NewsAlert",
    "AlertNotification",
    # Managers
    "NewsFeedManager",
    "EarningsCalendar",
    "EconomicCalendar",
    "SECFilingsTracker",
    "CorporateEventsTracker",
    "NewsAlertManager",
]
