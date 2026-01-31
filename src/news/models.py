"""News & Events Data Models.

Dataclasses for news articles, earnings, economic events, SEC filings, and alerts.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional
import uuid

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
    SENTIMENT_THRESHOLDS,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


# =============================================================================
# News Models
# =============================================================================

@dataclass
class NewsArticle:
    """News article with sentiment analysis."""
    article_id: str = field(default_factory=_new_id)
    headline: str = ""
    summary: str = ""
    content: str = ""
    source: NewsSource = NewsSource.REUTERS
    url: str = ""
    published_at: datetime = field(default_factory=_utc_now)
    symbols: list[str] = field(default_factory=list)
    categories: list[NewsCategory] = field(default_factory=list)
    sentiment_score: float = 0.0  # -1 to 1
    relevance_score: float = 0.5  # 0 to 1
    is_breaking: bool = False
    is_read: bool = False
    is_bookmarked: bool = False
    image_url: Optional[str] = None
    author: Optional[str] = None
    created_at: datetime = field(default_factory=_utc_now)
    
    @property
    def sentiment_label(self) -> SentimentLabel:
        """Get sentiment label from score."""
        for label, threshold in SENTIMENT_THRESHOLDS.items():
            if self.sentiment_score <= threshold:
                return label
        return SentimentLabel.VERY_POSITIVE
    
    @property
    def age_hours(self) -> float:
        """Hours since publication."""
        delta = _utc_now() - self.published_at
        return delta.total_seconds() / 3600
    
    def matches_filter(
        self,
        symbols: Optional[list[str]] = None,
        categories: Optional[list[NewsCategory]] = None,
        min_sentiment: Optional[float] = None,
        max_sentiment: Optional[float] = None,
    ) -> bool:
        """Check if article matches filter criteria."""
        if symbols and not any(s in self.symbols for s in symbols):
            return False
        if categories and not any(c in self.categories for c in categories):
            return False
        if min_sentiment is not None and self.sentiment_score < min_sentiment:
            return False
        if max_sentiment is not None and self.sentiment_score > max_sentiment:
            return False
        return True
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "article_id": self.article_id,
            "headline": self.headline,
            "summary": self.summary,
            "source": self.source.value,
            "url": self.url,
            "published_at": self.published_at.isoformat(),
            "symbols": self.symbols,
            "categories": [c.value for c in self.categories],
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label.value,
            "is_breaking": self.is_breaking,
        }


# =============================================================================
# Earnings Models
# =============================================================================

@dataclass
class EarningsEvent:
    """Earnings report event."""
    event_id: str = field(default_factory=_new_id)
    symbol: str = ""
    company_name: str = ""
    report_date: date = field(default_factory=date.today)
    report_time: ReportTime = ReportTime.UNKNOWN
    fiscal_quarter: str = ""  # e.g., "Q1 2024"
    fiscal_year: int = 2024
    
    # Estimates
    eps_estimate: Optional[float] = None
    revenue_estimate: Optional[float] = None  # In dollars
    eps_low: Optional[float] = None
    eps_high: Optional[float] = None
    num_analysts: int = 0
    
    # Actuals (populated after report)
    eps_actual: Optional[float] = None
    revenue_actual: Optional[float] = None
    
    # Guidance
    guidance_eps_low: Optional[float] = None
    guidance_eps_high: Optional[float] = None
    guidance_revenue_low: Optional[float] = None
    guidance_revenue_high: Optional[float] = None
    
    # Market reaction
    price_before: Optional[float] = None
    price_after: Optional[float] = None
    
    created_at: datetime = field(default_factory=_utc_now)
    
    @property
    def eps_surprise(self) -> Optional[float]:
        """EPS surprise (actual - estimate)."""
        if self.eps_actual is not None and self.eps_estimate is not None:
            return self.eps_actual - self.eps_estimate
        return None
    
    @property
    def eps_surprise_pct(self) -> Optional[float]:
        """EPS surprise percentage."""
        if self.eps_surprise is not None and self.eps_estimate and self.eps_estimate != 0:
            return (self.eps_surprise / abs(self.eps_estimate)) * 100
        return None
    
    @property
    def revenue_surprise(self) -> Optional[float]:
        """Revenue surprise."""
        if self.revenue_actual is not None and self.revenue_estimate is not None:
            return self.revenue_actual - self.revenue_estimate
        return None
    
    @property
    def revenue_surprise_pct(self) -> Optional[float]:
        """Revenue surprise percentage."""
        if self.revenue_surprise is not None and self.revenue_estimate and self.revenue_estimate != 0:
            return (self.revenue_surprise / self.revenue_estimate) * 100
        return None
    
    @property
    def price_change_pct(self) -> Optional[float]:
        """Price change after earnings."""
        if self.price_before and self.price_after and self.price_before != 0:
            return ((self.price_after - self.price_before) / self.price_before) * 100
        return None
    
    @property
    def is_beat(self) -> Optional[bool]:
        """Did company beat estimates?"""
        if self.eps_surprise is not None:
            return self.eps_surprise > 0
        return None
    
    @property
    def is_reported(self) -> bool:
        """Has earnings been reported?"""
        return self.eps_actual is not None
    
    @property
    def days_until(self) -> int:
        """Days until report (negative if past)."""
        return (self.report_date - date.today()).days


# =============================================================================
# Economic Models
# =============================================================================

@dataclass
class EconomicEvent:
    """Economic calendar event."""
    event_id: str = field(default_factory=_new_id)
    name: str = ""
    category: EconomicCategory = EconomicCategory.GROWTH
    country: str = "US"
    release_date: datetime = field(default_factory=_utc_now)
    importance: EventImportance = EventImportance.MEDIUM
    
    # Values
    forecast: Optional[float] = None
    previous: Optional[float] = None
    actual: Optional[float] = None
    unit: str = ""  # e.g., "%", "K", "B"
    
    # Impact assessment
    market_impact: Optional[str] = None  # 'bullish', 'bearish', 'neutral'
    affected_sectors: list[str] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=_utc_now)
    
    @property
    def surprise(self) -> Optional[float]:
        """Actual vs forecast surprise."""
        if self.actual is not None and self.forecast is not None:
            return self.actual - self.forecast
        return None
    
    @property
    def is_released(self) -> bool:
        """Has event been released?"""
        return self.actual is not None
    
    @property
    def is_upcoming(self) -> bool:
        """Is event in the future?"""
        return self.release_date > _utc_now()


# =============================================================================
# SEC Filing Models
# =============================================================================

@dataclass
class SECFiling:
    """SEC filing record."""
    filing_id: str = field(default_factory=_new_id)
    symbol: str = ""
    company_name: str = ""
    cik: str = ""  # SEC Central Index Key
    form_type: FilingType = FilingType.FORM_8K
    filed_date: date = field(default_factory=date.today)
    accepted_datetime: datetime = field(default_factory=_utc_now)
    period_of_report: Optional[date] = None
    
    # Document info
    url: str = ""
    document_count: int = 1
    file_size_bytes: int = 0
    
    # Parsed content (for supported forms)
    description: str = ""
    key_items: dict[str, Any] = field(default_factory=dict)
    
    created_at: datetime = field(default_factory=_utc_now)
    
    @property
    def is_insider_filing(self) -> bool:
        """Is this an insider transaction filing?"""
        return self.form_type == FilingType.FORM_4
    
    @property
    def is_quarterly(self) -> bool:
        """Is this a quarterly filing?"""
        return self.form_type in [FilingType.FORM_10Q, FilingType.FORM_10K]


@dataclass
class InsiderTransaction:
    """Insider transaction from Form 4."""
    transaction_id: str = field(default_factory=_new_id)
    filing_id: str = ""
    symbol: str = ""
    
    # Insider info
    insider_name: str = ""
    insider_title: str = ""
    is_director: bool = False
    is_officer: bool = False
    is_ten_percent_owner: bool = False
    
    # Transaction details
    transaction_date: date = field(default_factory=date.today)
    transaction_type: InsiderTransactionType = InsiderTransactionType.BUY
    shares: float = 0.0
    price: Optional[float] = None
    
    # Ownership
    shares_owned_after: float = 0.0
    ownership_type: str = "direct"  # 'direct' or 'indirect'
    
    created_at: datetime = field(default_factory=_utc_now)
    
    @property
    def value(self) -> Optional[float]:
        """Transaction value."""
        if self.price is not None:
            return self.shares * self.price
        return None
    
    @property
    def is_purchase(self) -> bool:
        """Is this a purchase?"""
        return self.transaction_type == InsiderTransactionType.BUY
    
    @property
    def is_sale(self) -> bool:
        """Is this a sale?"""
        return self.transaction_type == InsiderTransactionType.SELL


# =============================================================================
# Corporate Event Models
# =============================================================================

@dataclass
class DividendEvent:
    """Dividend announcement/payment."""
    event_id: str = field(default_factory=_new_id)
    symbol: str = ""
    company_name: str = ""
    
    # Key dates
    declaration_date: Optional[date] = None
    ex_date: date = field(default_factory=date.today)
    record_date: Optional[date] = None
    pay_date: Optional[date] = None
    
    # Amount
    amount: float = 0.0
    currency: str = "USD"
    frequency: DividendFrequency = DividendFrequency.QUARTERLY
    dividend_type: str = "cash"  # 'cash' or 'stock'
    
    # Yield info
    yield_on_ex_date: Optional[float] = None
    
    created_at: datetime = field(default_factory=_utc_now)
    
    @property
    def annualized_amount(self) -> float:
        """Annualized dividend amount."""
        multipliers = {
            DividendFrequency.MONTHLY: 12,
            DividendFrequency.QUARTERLY: 4,
            DividendFrequency.SEMI_ANNUAL: 2,
            DividendFrequency.ANNUAL: 1,
            DividendFrequency.SPECIAL: 1,
        }
        return self.amount * multipliers.get(self.frequency, 1)


@dataclass
class CorporateEvent:
    """General corporate event."""
    event_id: str = field(default_factory=_new_id)
    symbol: str = ""
    company_name: str = ""
    event_type: CorporateEventType = CorporateEventType.DIVIDEND
    event_date: date = field(default_factory=date.today)
    
    # Event details
    description: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    
    # For splits
    split_ratio: Optional[str] = None  # e.g., "4:1"
    
    # For M&A
    target_company: Optional[str] = None
    deal_value: Optional[float] = None
    
    created_at: datetime = field(default_factory=_utc_now)


# =============================================================================
# Alert Models
# =============================================================================

@dataclass
class NewsAlert:
    """News/event alert configuration."""
    alert_id: str = field(default_factory=_new_id)
    user_id: str = ""
    name: str = ""
    enabled: bool = True
    trigger: AlertTrigger = AlertTrigger.SYMBOL_NEWS
    
    # Filters
    symbols: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    categories: list[NewsCategory] = field(default_factory=list)
    sources: list[NewsSource] = field(default_factory=list)
    min_sentiment: Optional[float] = None
    max_sentiment: Optional[float] = None
    importance_levels: list[EventImportance] = field(default_factory=list)
    filing_types: list[FilingType] = field(default_factory=list)
    
    # Delivery
    channels: list[str] = field(default_factory=lambda: ["in_app"])
    respect_quiet_hours: bool = True
    
    # State
    last_triggered_at: Optional[datetime] = None
    trigger_count: int = 0
    
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class AlertNotification:
    """Alert notification record."""
    notification_id: str = field(default_factory=_new_id)
    alert_id: str = ""
    user_id: str = ""
    trigger: AlertTrigger = AlertTrigger.SYMBOL_NEWS
    
    # Content
    title: str = ""
    message: str = ""
    symbol: Optional[str] = None
    reference_id: Optional[str] = None  # article_id, event_id, etc.
    reference_type: str = ""  # 'article', 'earnings', 'filing', etc.
    
    # Delivery
    channels_sent: list[str] = field(default_factory=list)
    is_read: bool = False
    
    created_at: datetime = field(default_factory=_utc_now)
