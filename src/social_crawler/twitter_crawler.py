"""X/Twitter Crawler (PRD-140).

Crawls X/Twitter for stock-related posts using the X API v2.
Falls back to demo data when API credentials aren't available.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import logging
import time

from src.sentiment.social import SocialPost
from src.social_crawler.base import (
    CrawlConfig,
    CrawlResult,
    CrawlerStats,
    CrawlStatus,
    PlatformType,
    extract_tickers,
    estimate_sentiment,
)

logger = logging.getLogger(__name__)

_HAS_TWEEPY = False
try:
    import tweepy
    _HAS_TWEEPY = True
except ImportError:
    tweepy = None  # type: ignore


@dataclass
class TwitterConfig(CrawlConfig):
    """Twitter-specific configuration."""
    platform: PlatformType = PlatformType.TWITTER
    bearer_token: str = ""
    # Search parameters
    search_queries: list[str] = field(default_factory=lambda: [
        "$AAPL OR $MSFT OR $GOOGL OR $NVDA OR $TSLA",
        "$SPY OR $QQQ OR $IWM",
        "#stocks OR #trading OR #wallstreetbets",
    ])
    max_results_per_query: int = 50
    # Filtering
    min_likes: int = 5
    min_followers: int = 100
    exclude_retweets: bool = True
    language: str = "en"


class TwitterCrawler:
    """Crawls X/Twitter for stock-related posts.

    Uses Twitter API v2 via tweepy when available,
    falls back to demo data otherwise.

    Example:
        crawler = TwitterCrawler(TwitterConfig(bearer_token="..."))
        await crawler.connect()
        result = await crawler.crawl()
        for post in result.posts:
            print(post.tickers, post.sentiment)
    """

    def __init__(self, config: Optional[TwitterConfig] = None):
        self._config = config or TwitterConfig()
        self._client: Any = None
        self._connected = False
        self._stats = CrawlerStats(platform=PlatformType.TWITTER)

    @property
    def platform(self) -> PlatformType:
        return PlatformType.TWITTER

    @property
    def stats(self) -> CrawlerStats:
        return self._stats

    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        """Connect to Twitter API."""
        if self._config.demo_mode or not self._config.bearer_token:
            self._connected = True
            self._stats.status = CrawlStatus.RUNNING
            logger.info("Twitter crawler connected (demo mode)")
            return True

        if _HAS_TWEEPY and self._config.bearer_token:
            try:
                self._client = tweepy.Client(
                    bearer_token=self._config.bearer_token,
                    wait_on_rate_limit=True,
                )
                self._connected = True
                self._stats.status = CrawlStatus.RUNNING
                logger.info("Twitter crawler connected via API")
                return True
            except Exception as e:
                self._stats.status = CrawlStatus.ERROR
                self._stats.last_error = str(e)
                logger.error(f"Twitter connection failed: {e}")
                return False

        self._connected = True
        self._stats.status = CrawlStatus.RUNNING
        logger.info("Twitter crawler connected (demo mode — tweepy not installed)")
        return True

    async def disconnect(self) -> None:
        """Disconnect from Twitter API."""
        self._client = None
        self._connected = False
        self._stats.status = CrawlStatus.IDLE

    async def crawl(self) -> CrawlResult:
        """Execute one crawl cycle."""
        start = time.monotonic()
        posts: list[SocialPost] = []
        errors: list[str] = []

        if self._client and not self._config.demo_mode:
            posts, errors = await self._crawl_live()
        else:
            posts = self._demo_posts()

        # Extract tickers for any posts missing them
        all_tickers: set[str] = set()
        for post in posts:
            if not post.tickers:
                post.tickers = extract_tickers(post.text)
            if post.sentiment == 0.0:
                post.sentiment = estimate_sentiment(post.text)
            all_tickers.update(post.tickers)

        result = CrawlResult(
            platform=PlatformType.TWITTER,
            posts=posts,
            post_count=len(posts),
            tickers_found=sorted(all_tickers),
            crawl_duration_ms=(time.monotonic() - start) * 1000,
            errors=errors,
        )
        self._stats.record_crawl(result)
        return result

    async def _crawl_live(self) -> tuple[list[SocialPost], list[str]]:
        """Crawl live Twitter data."""
        posts: list[SocialPost] = []
        errors: list[str] = []

        for query in self._config.search_queries:
            try:
                search_query = query
                if self._config.exclude_retweets:
                    search_query += " -is:retweet"
                search_query += f" lang:{self._config.language}"

                response = self._client.search_recent_tweets(
                    query=search_query,
                    max_results=min(self._config.max_results_per_query, 100),
                    tweet_fields=["created_at", "public_metrics", "author_id", "text"],
                )

                if response.data:
                    for tweet in response.data:
                        metrics = tweet.public_metrics or {}
                        likes = metrics.get("like_count", 0)

                        if likes < self._config.min_likes:
                            continue

                        tickers = extract_tickers(tweet.text)
                        if not tickers:
                            continue

                        posts.append(SocialPost(
                            text=tweet.text,
                            source="twitter",
                            author=str(tweet.author_id),
                            timestamp=str(tweet.created_at),
                            upvotes=likes,
                            comments=metrics.get("reply_count", 0),
                            sentiment=estimate_sentiment(tweet.text),
                            tickers=tickers,
                            url=f"https://x.com/i/status/{tweet.id}",
                        ))

            except Exception as e:
                errors.append(f"Query '{query}': {str(e)}")
                logger.warning(f"Twitter crawl error: {e}")

        return posts, errors

    def _demo_posts(self) -> list[SocialPost]:
        """Generate demo Twitter posts."""
        return [
            SocialPost(
                text="$AAPL looking bullish after earnings beat. Cloud breakout on 4H chart. 🚀",
                source="twitter", author="@trader_joe", timestamp=datetime.now(timezone.utc).isoformat(),
                upvotes=142, comments=28, sentiment=0.8, tickers=["AAPL"],
            ),
            SocialPost(
                text="$NVDA and $AMD leading the semiconductor rally. AI demand is insane right now.",
                source="twitter", author="@chipanalyst", timestamp=datetime.now(timezone.utc).isoformat(),
                upvotes=89, comments=15, sentiment=0.7, tickers=["NVDA", "AMD"],
            ),
            SocialPost(
                text="Bearish on $TSLA here. Overvalued at these levels. Puts printing.",
                source="twitter", author="@bearish_mike", timestamp=datetime.now(timezone.utc).isoformat(),
                upvotes=45, comments=92, sentiment=-0.6, tickers=["TSLA"],
            ),
            SocialPost(
                text="$SPY $QQQ both showing weakness at resistance. Expecting pullback to 200MA.",
                source="twitter", author="@techtrader", timestamp=datetime.now(timezone.utc).isoformat(),
                upvotes=67, comments=23, sentiment=-0.3, tickers=["SPY", "QQQ"],
            ),
            SocialPost(
                text="$MSFT AI integration is a game changer. Long-term hold. Diamond hands 💎",
                source="twitter", author="@ai_investor", timestamp=datetime.now(timezone.utc).isoformat(),
                upvotes=234, comments=41, sentiment=0.9, tickers=["MSFT"],
            ),
            SocialPost(
                text="$META breaking out to new ATH. Strong buy signal on weekly chart.",
                source="twitter", author="@swing_queen", timestamp=datetime.now(timezone.utc).isoformat(),
                upvotes=112, comments=19, sentiment=0.8, tickers=["META"],
            ),
            SocialPost(
                text="$GOOGL undervalued vs peers. AI moat is real. Buying the dip here.",
                source="twitter", author="@value_plays", timestamp=datetime.now(timezone.utc).isoformat(),
                upvotes=78, comments=12, sentiment=0.7, tickers=["GOOGL"],
            ),
            SocialPost(
                text="$GME short squeeze incoming? SI still above 20%. Options chain loaded.",
                source="twitter", author="@meme_trader", timestamp=datetime.now(timezone.utc).isoformat(),
                upvotes=567, comments=234, sentiment=0.5, tickers=["GME"],
            ),
        ]
