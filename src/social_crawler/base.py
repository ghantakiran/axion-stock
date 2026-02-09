"""Social Crawler Base (PRD-140).

Base protocol and utilities shared by all social platform crawlers.
Defines the unified crawl interface and common ticker extraction.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Protocol, runtime_checkable
import logging
import re

from src.sentiment.social import SocialPost

logger = logging.getLogger(__name__)


class PlatformType(str, Enum):
    """Supported social platforms."""
    TWITTER = "twitter"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    REDDIT = "reddit"
    WHATSAPP = "whatsapp"
    STOCKTWITS = "stocktwits"


class CrawlStatus(str, Enum):
    """Crawler status."""
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    DISCONNECTED = "disconnected"


@dataclass
class CrawlConfig:
    """Configuration for a crawler instance."""
    platform: PlatformType
    # API credentials
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    bot_token: str = ""
    # Targets
    channels: list[str] = field(default_factory=list)
    subreddits: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=lambda: [
        "stock", "market", "trading", "bullish", "bearish",
        "calls", "puts", "options", "yolo", "diamond hands",
        "moon", "squeeze", "short", "buy", "sell",
    ])
    # Rate limiting
    poll_interval: float = 60.0  # seconds between polls
    max_posts_per_poll: int = 100
    # Filtering
    min_engagement: int = 0  # minimum upvotes/reactions
    min_text_length: int = 10
    # Demo mode
    demo_mode: bool = True


@dataclass
class CrawlResult:
    """Result of a crawl operation."""
    platform: PlatformType
    posts: list[SocialPost] = field(default_factory=list)
    post_count: int = 0
    tickers_found: list[str] = field(default_factory=list)
    crawl_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "platform": self.platform.value,
            "post_count": self.post_count,
            "tickers_found": self.tickers_found,
            "crawl_duration_ms": self.crawl_duration_ms,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CrawlerStats:
    """Runtime statistics for a crawler."""
    platform: PlatformType = PlatformType.TWITTER
    status: CrawlStatus = CrawlStatus.IDLE
    total_crawls: int = 0
    total_posts: int = 0
    total_tickers: int = 0
    total_errors: int = 0
    last_crawl: Optional[datetime] = None
    last_error: Optional[str] = None
    avg_crawl_ms: float = 0.0

    def record_crawl(self, result: CrawlResult) -> None:
        self.total_crawls += 1
        self.total_posts += result.post_count
        self.total_tickers += len(result.tickers_found)
        self.total_errors += len(result.errors)
        self.last_crawl = result.timestamp
        if result.errors:
            self.last_error = result.errors[-1]
        # Running average
        self.avg_crawl_ms = (
            (self.avg_crawl_ms * (self.total_crawls - 1) + result.crawl_duration_ms)
            / self.total_crawls
        )


@runtime_checkable
class CrawlerProtocol(Protocol):
    """Protocol that all social crawlers must implement."""

    @property
    def platform(self) -> PlatformType:
        """Get the platform type."""
        ...

    @property
    def stats(self) -> CrawlerStats:
        """Get crawler stats."""
        ...

    async def connect(self) -> bool:
        """Connect to the platform API."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from the platform."""
        ...

    async def crawl(self) -> CrawlResult:
        """Execute one crawl cycle."""
        ...

    def is_connected(self) -> bool:
        """Check if connected."""
        ...


# ═══════════════════════════════════════════════════════════════════════
# Ticker Extraction Utilities
# ═══════════════════════════════════════════════════════════════════════

# Common stock tickers that are also English words (exclude from extraction)
_COMMON_WORDS = {
    "A", "I", "AM", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE",
    "IF", "IN", "IS", "IT", "ME", "MY", "NO", "OF", "OK", "ON", "OR",
    "SO", "TO", "UP", "US", "WE", "AI", "ALL", "FOR", "HAS", "HIM",
    "HIS", "HER", "HOW", "ITS", "NEW", "NOW", "OLD", "ONE", "OUR",
    "OUT", "OWN", "RUN", "SAY", "THE", "TOO", "TWO", "WAR", "WAY",
    "WHO", "WHY", "YOU", "ARE", "BIG", "CAN", "DID", "GOT", "HAD",
    "HAS", "NOT", "PUT", "SEE", "TRY", "USE", "WAS", "BUY", "CALL",
    "EVER", "EDIT", "GOOD", "HUGE", "JUST", "LIKE", "LONG", "MAKE",
    "MOST", "MUCH", "NICE", "OPEN", "REAL", "SAYS", "SOME", "TELL",
    "THAT", "THEM", "THEN", "THIS", "TRUE", "VERY", "WELL", "WILL",
    "WITH", "WORK", "BEST", "HIGH", "FAST", "NEXT", "ONLY", "OVER",
    "SAME", "BEEN", "COME", "DOWN", "FROM", "HAVE", "HERE", "INTO",
    "MANY", "MORE", "MOVE", "NEED", "ONCE", "SAFE", "SELL", "PUMP",
    "DUMP",
}

# Well-known tickers unlikely to be confused with words
_KNOWN_TICKERS = {
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "V", "JNJ", "WMT", "PG", "MA", "UNH", "HD", "DIS", "PYPL",
    "NFLX", "ADBE", "CRM", "INTC", "AMD", "QCOM", "AVGO", "TXN",
    "MU", "AMAT", "LRCX", "KLAC", "MRVL", "SNPS", "CDNS", "ASML",
    "BA", "CAT", "GS", "MS", "C", "BAC", "WFC", "BRK", "BLK",
    "COST", "TGT", "LOW", "NKE", "SBUX", "MCD", "KO", "PEP",
    "LLY", "PFE", "MRK", "ABBV", "TMO", "ABT", "BMY", "GILD",
    "XOM", "CVX", "COP", "SLB", "OXY", "EOG", "PSX", "VLO",
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "ARKK", "SQQQ", "TQQQ",
    "GME", "AMC", "PLTR", "SOFI", "RIVN", "LCID", "NIO", "COIN",
    "SNAP", "UBER", "LYFT", "ABNB", "DASH", "RBLX", "U", "SE",
    "BTC", "ETH", "SOL", "DOGE", "XRP", "ADA", "AVAX", "MATIC",
}

# Cashtag pattern: $AAPL
_CASHTAG_RE = re.compile(r"\$([A-Z]{1,5})\b")
# All-caps pattern (not at start of sentence): AAPL
_ALLCAPS_RE = re.compile(r"(?<![.!?]\s)\b([A-Z]{2,5})\b")


def extract_tickers(text: str) -> list[str]:
    """Extract stock tickers from text.

    Uses a multi-strategy approach:
    1. Cashtags ($AAPL) — highest confidence
    2. Known ticker matches — medium confidence
    3. All-caps words not in common word list — lower confidence

    Args:
        text: Input text to extract tickers from.

    Returns:
        Deduplicated list of ticker symbols.
    """
    tickers: set[str] = set()

    # Strategy 1: Cashtags (highest confidence)
    for match in _CASHTAG_RE.finditer(text):
        ticker = match.group(1)
        if ticker not in _COMMON_WORDS or ticker in _KNOWN_TICKERS:
            tickers.add(ticker)

    # Strategy 2: Known tickers
    upper = text.upper()
    for ticker in _KNOWN_TICKERS:
        if ticker in upper:
            # Verify word boundary
            pattern = r"\b" + re.escape(ticker) + r"\b"
            if re.search(pattern, upper):
                tickers.add(ticker)

    # Strategy 3: All-caps words (lower confidence — only if 3+ chars)
    for match in _ALLCAPS_RE.finditer(text):
        word = match.group(1)
        if len(word) >= 3 and word not in _COMMON_WORDS:
            tickers.add(word)

    return sorted(tickers)


def estimate_sentiment(text: str) -> float:
    """Simple rule-based sentiment estimation.

    Returns a score between -1.0 (bearish) and 1.0 (bullish).
    Uses keyword matching as a lightweight alternative to ML models.
    """
    text_lower = text.lower()

    bullish_words = [
        "bullish", "moon", "rocket", "buy", "long", "calls",
        "breakout", "squeeze", "undervalued", "gem", "dip",
        "diamond hands", "to the moon", "all in", "green",
        "surge", "rally", "soaring", "pump", "strong",
        "bull", "growth", "upgrade", "outperform",
    ]
    bearish_words = [
        "bearish", "short", "puts", "sell", "dump",
        "overvalued", "crash", "bubble", "bag holder",
        "red", "tank", "plunge", "drop", "weak",
        "bear", "downgrade", "underperform", "avoid",
        "scam", "fraud", "ponzi", "rug pull",
    ]

    bull_count = sum(1 for w in bullish_words if w in text_lower)
    bear_count = sum(1 for w in bearish_words if w in text_lower)

    total = bull_count + bear_count
    if total == 0:
        return 0.0

    return (bull_count - bear_count) / total
