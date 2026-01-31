"""News & Events Configuration.

Enums, constants, and configuration for news, earnings, economic events, and filings.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class NewsCategory(str, Enum):
    """News article categories."""
    EARNINGS = "earnings"
    MACRO = "macro"
    ANALYST = "analyst"
    MERGER = "merger"
    IPO = "ipo"
    REGULATORY = "regulatory"
    PRODUCT = "product"
    MANAGEMENT = "management"
    LEGAL = "legal"
    DIVIDEND = "dividend"
    GUIDANCE = "guidance"
    GENERAL = "general"


class NewsSource(str, Enum):
    """News sources."""
    REUTERS = "reuters"
    BLOOMBERG = "bloomberg"
    MARKETWATCH = "marketwatch"
    CNBC = "cnbc"
    WSJ = "wsj"
    SEC = "sec"
    PR_NEWSWIRE = "pr_newswire"
    BUSINESS_WIRE = "business_wire"
    YAHOO = "yahoo"
    BENZINGA = "benzinga"
    SEEKING_ALPHA = "seeking_alpha"


class SentimentLabel(str, Enum):
    """Sentiment classification."""
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


class ReportTime(str, Enum):
    """Earnings report timing."""
    BMO = "bmo"  # Before Market Open
    AMC = "amc"  # After Market Close
    DMH = "dmh"  # During Market Hours
    UNKNOWN = "unknown"


class EventImportance(str, Enum):
    """Event importance level."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EconomicCategory(str, Enum):
    """Economic event categories."""
    CENTRAL_BANK = "central_bank"
    EMPLOYMENT = "employment"
    INFLATION = "inflation"
    GROWTH = "growth"
    HOUSING = "housing"
    SENTIMENT = "sentiment"
    TRADE = "trade"
    MANUFACTURING = "manufacturing"
    INTERNATIONAL = "international"


class FilingType(str, Enum):
    """SEC filing types."""
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    FORM_4 = "4"
    FORM_13F = "13F"
    FORM_S1 = "S-1"
    DEF_14A = "DEF 14A"
    FORM_13D = "13D"
    FORM_13G = "13G"


class InsiderTransactionType(str, Enum):
    """Insider transaction types."""
    BUY = "buy"
    SELL = "sell"
    GRANT = "grant"
    EXERCISE = "exercise"
    GIFT = "gift"


class CorporateEventType(str, Enum):
    """Corporate event types."""
    DIVIDEND = "dividend"
    STOCK_SPLIT = "stock_split"
    REVERSE_SPLIT = "reverse_split"
    MERGER = "merger"
    ACQUISITION = "acquisition"
    SPINOFF = "spinoff"
    IPO = "ipo"
    BUYBACK = "buyback"
    DELISTING = "delisting"
    NAME_CHANGE = "name_change"


class DividendFrequency(str, Enum):
    """Dividend payment frequency."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    SPECIAL = "special"


class AlertTrigger(str, Enum):
    """News alert trigger types."""
    SYMBOL_NEWS = "symbol_news"
    BREAKING_NEWS = "breaking_news"
    EARNINGS_ANNOUNCE = "earnings_announce"
    EARNINGS_SURPRISE = "earnings_surprise"
    INSIDER_TRANSACTION = "insider_transaction"
    SEC_FILING = "sec_filing"
    ECONOMIC_RELEASE = "economic_release"
    DIVIDEND_DECLARED = "dividend_declared"
    PRICE_TARGET = "price_target"
    RATING_CHANGE = "rating_change"


# =============================================================================
# Constants
# =============================================================================

# Major economic events
MAJOR_ECONOMIC_EVENTS = [
    "FOMC Meeting",
    "Fed Interest Rate Decision",
    "Non-Farm Payrolls",
    "Unemployment Rate",
    "CPI",
    "Core CPI",
    "PPI",
    "GDP",
    "Retail Sales",
    "Consumer Confidence",
    "ISM Manufacturing PMI",
    "ISM Services PMI",
    "Housing Starts",
    "Initial Jobless Claims",
]

# High importance filing types
HIGH_IMPORTANCE_FILINGS = [
    FilingType.FORM_10K,
    FilingType.FORM_10Q,
    FilingType.FORM_8K,
    FilingType.FORM_4,
]

# Sentiment score thresholds
SENTIMENT_THRESHOLDS = {
    SentimentLabel.VERY_NEGATIVE: -0.6,
    SentimentLabel.NEGATIVE: -0.2,
    SentimentLabel.NEUTRAL: 0.2,
    SentimentLabel.POSITIVE: 0.6,
    SentimentLabel.VERY_POSITIVE: 1.0,
}


# =============================================================================
# Configuration Dataclasses
# =============================================================================

@dataclass
class NewsFeedConfig:
    """News feed configuration."""
    max_articles_per_symbol: int = 100
    max_articles_per_page: int = 20
    default_lookback_days: int = 7
    cache_ttl_seconds: int = 300
    enable_sentiment_analysis: bool = True
    min_relevance_score: float = 0.3
    breaking_news_threshold: float = 0.8


@dataclass
class EarningsConfig:
    """Earnings calendar configuration."""
    lookback_quarters: int = 8
    lookahead_days: int = 90
    surprise_threshold_pct: float = 5.0  # For alerts
    track_guidance: bool = True
    track_revisions: bool = True


@dataclass
class EconomicConfig:
    """Economic calendar configuration."""
    countries: list[str] = field(default_factory=lambda: ["US", "EU", "UK", "JP", "CN"])
    min_importance: EventImportance = EventImportance.MEDIUM
    lookahead_days: int = 30


@dataclass
class FilingsConfig:
    """SEC filings configuration."""
    tracked_forms: list[FilingType] = field(
        default_factory=lambda: list(HIGH_IMPORTANCE_FILINGS)
    )
    parse_form_4: bool = True
    parse_8k_items: bool = True
    lookback_days: int = 30


@dataclass
class NewsAlertsConfig:
    """News alerts configuration."""
    max_alerts_per_user: int = 50
    cooldown_seconds: int = 300
    batch_similar_alerts: bool = True
    quiet_hours_start: int = 22
    quiet_hours_end: int = 7


@dataclass
class NewsConfig:
    """Main news & events configuration."""
    news_feed: NewsFeedConfig = field(default_factory=NewsFeedConfig)
    earnings: EarningsConfig = field(default_factory=EarningsConfig)
    economic: EconomicConfig = field(default_factory=EconomicConfig)
    filings: FilingsConfig = field(default_factory=FilingsConfig)
    alerts: NewsAlertsConfig = field(default_factory=NewsAlertsConfig)


DEFAULT_NEWS_CONFIG = NewsConfig()
