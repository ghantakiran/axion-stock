"""Reddit Crawler (PRD-140).

Crawls Reddit subreddits for stock-related posts and comments.
Uses PRAW (Python Reddit API Wrapper) when available.
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

_HAS_PRAW = False
try:
    import praw
    _HAS_PRAW = True
except ImportError:
    praw = None  # type: ignore


@dataclass
class RedditConfig(CrawlConfig):
    """Reddit-specific configuration."""
    platform: PlatformType = PlatformType.REDDIT
    client_id: str = ""
    client_secret: str = ""
    user_agent: str = "axion-platform:v1.0 (by /u/axion_bot)"
    # Subreddits to monitor
    subreddits: list[str] = field(default_factory=lambda: [
        "wallstreetbets", "stocks", "investing", "options",
        "stockmarket", "thetagang", "SPACs",
    ])
    # Sorting
    sort: str = "hot"  # hot, new, top, rising
    time_filter: str = "day"  # hour, day, week, month
    post_limit: int = 25
    include_comments: bool = True
    comments_per_post: int = 10
    # Filtering
    min_score: int = 10


class RedditCrawler:
    """Crawls Reddit for stock-related posts and comments.

    Example:
        crawler = RedditCrawler(RedditConfig(
            client_id="...", client_secret="...",
        ))
        await crawler.connect()
        result = await crawler.crawl()
    """

    def __init__(self, config: Optional[RedditConfig] = None):
        self._config = config or RedditConfig()
        self._reddit: Any = None
        self._connected = False
        self._stats = CrawlerStats(platform=PlatformType.REDDIT)

    @property
    def platform(self) -> PlatformType:
        return PlatformType.REDDIT

    @property
    def stats(self) -> CrawlerStats:
        return self._stats

    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        """Connect to Reddit API."""
        if (
            not self._config.demo_mode
            and _HAS_PRAW
            and self._config.client_id
        ):
            try:
                self._reddit = praw.Reddit(
                    client_id=self._config.client_id,
                    client_secret=self._config.client_secret,
                    user_agent=self._config.user_agent,
                )
                self._connected = True
                self._stats.status = CrawlStatus.RUNNING
                logger.info("Reddit crawler connected via PRAW")
                return True
            except Exception as e:
                logger.error(f"Reddit connection failed: {e}")
                self._stats.last_error = str(e)

        self._connected = True
        self._stats.status = CrawlStatus.RUNNING
        logger.info("Reddit crawler connected (demo mode)")
        return True

    async def disconnect(self) -> None:
        self._reddit = None
        self._connected = False
        self._stats.status = CrawlStatus.IDLE

    async def crawl(self) -> CrawlResult:
        """Execute one crawl cycle."""
        start = time.monotonic()
        posts: list[SocialPost] = []
        errors: list[str] = []

        if self._reddit and not self._config.demo_mode:
            posts, errors = self._crawl_live()
        else:
            posts = self._demo_posts()

        all_tickers: set[str] = set()
        for post in posts:
            if not post.tickers:
                post.tickers = extract_tickers(post.text)
            if post.sentiment == 0.0:
                post.sentiment = estimate_sentiment(post.text)
            all_tickers.update(post.tickers)

        result = CrawlResult(
            platform=PlatformType.REDDIT,
            posts=posts,
            post_count=len(posts),
            tickers_found=sorted(all_tickers),
            crawl_duration_ms=(time.monotonic() - start) * 1000,
            errors=errors,
        )
        self._stats.record_crawl(result)
        return result

    def _crawl_live(self) -> tuple[list[SocialPost], list[str]]:
        """Crawl live Reddit posts."""
        posts: list[SocialPost] = []
        errors: list[str] = []

        for sub_name in self._config.subreddits:
            try:
                subreddit = self._reddit.subreddit(sub_name)
                submissions = getattr(subreddit, self._config.sort)(
                    limit=self._config.post_limit,
                    time_filter=self._config.time_filter,
                ) if self._config.sort == "top" else getattr(
                    subreddit, self._config.sort
                )(limit=self._config.post_limit)

                for submission in submissions:
                    if submission.score < self._config.min_score:
                        continue

                    text = f"{submission.title}\n{submission.selftext or ''}"
                    tickers = extract_tickers(text)
                    if not tickers:
                        continue

                    posts.append(SocialPost(
                        text=text[:1000],
                        source="reddit",
                        author=str(submission.author),
                        timestamp=str(datetime.fromtimestamp(
                            submission.created_utc, tz=timezone.utc
                        )),
                        upvotes=submission.score,
                        comments=submission.num_comments,
                        sentiment=estimate_sentiment(text),
                        tickers=tickers,
                        url=f"https://reddit.com{submission.permalink}",
                    ))

                    # Also crawl top comments
                    if self._config.include_comments:
                        submission.comments.replace_more(limit=0)
                        for comment in submission.comments[:self._config.comments_per_post]:
                            c_tickers = extract_tickers(comment.body)
                            if c_tickers and comment.score >= self._config.min_score:
                                posts.append(SocialPost(
                                    text=comment.body[:500],
                                    source="reddit",
                                    author=str(comment.author),
                                    timestamp=str(datetime.fromtimestamp(
                                        comment.created_utc, tz=timezone.utc
                                    )),
                                    upvotes=comment.score,
                                    comments=0,
                                    sentiment=estimate_sentiment(comment.body),
                                    tickers=c_tickers,
                                    url=f"https://reddit.com{comment.permalink}",
                                ))

            except Exception as e:
                errors.append(f"r/{sub_name}: {str(e)}")
                logger.warning(f"Reddit crawl error for r/{sub_name}: {e}")

        return posts, errors

    def _demo_posts(self) -> list[SocialPost]:
        """Generate demo Reddit posts."""
        now = datetime.now(timezone.utc).isoformat()
        return [
            SocialPost(
                text="YOLO: $50K into NVDA calls expiring Friday\n"
                     "Earnings are gonna be massive. AI demand through the roof.",
                source="reddit", author="WSB_yolo_king", timestamp=now,
                upvotes=4523, comments=892, sentiment=0.7, tickers=["NVDA"],
            ),
            SocialPost(
                text="DD: Why AAPL is the best long-term hold right now\n"
                     "Services revenue growing 15% YoY. Massive buyback program. "
                     "PE ratio reasonable at 28x vs 5yr avg of 25x.",
                source="reddit", author="value_investor_dd", timestamp=now,
                upvotes=1234, comments=345, sentiment=0.8, tickers=["AAPL"],
            ),
            SocialPost(
                text="Technical Analysis: $SPY showing head & shoulders pattern\n"
                     "Neckline at 460. If it breaks, target is 440. Selling calls here.",
                source="reddit", author="TA_master", timestamp=now,
                upvotes=567, comments=178, sentiment=-0.5, tickers=["SPY"],
            ),
            SocialPost(
                text="TSLA bear case: Competition catching up fast\n"
                     "BYD just passed Tesla in global EV sales. Margins compressing. "
                     "Stock is still priced for perfection at 60x forward PE.",
                source="reddit", author="rational_bear", timestamp=now,
                upvotes=890, comments=456, sentiment=-0.7, tickers=["TSLA"],
            ),
            SocialPost(
                text="Just bought 1000 shares of PLTR at $22. AI government contracts "
                     "are a goldmine. This is a $50 stock in 2 years.",
                source="reddit", author="pltr_believer", timestamp=now,
                upvotes=345, comments=123, sentiment=0.6, tickers=["PLTR"],
            ),
            SocialPost(
                text="$MSFT and $GOOGL both undervalued relative to AI potential. "
                     "Loading up on both. Cloud + AI = unstoppable.",
                source="reddit", author="tech_bull", timestamp=now,
                upvotes=678, comments=234, sentiment=0.8, tickers=["MSFT", "GOOGL"],
            ),
        ]
