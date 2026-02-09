"""Social Feed Aggregator (PRD-140).

Combines feeds from all crawlers, deduplicates, ranks by relevance,
and produces a unified stream of SocialPost objects.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import asyncio
import logging
import time

from src.sentiment.social import SocialPost
from src.social_crawler.base import (
    CrawlResult,
    CrawlerProtocol,
    CrawlerStats,
    PlatformType,
)

logger = logging.getLogger(__name__)


@dataclass
class AggregatedFeed:
    """Combined feed from all crawlers."""
    posts: list[SocialPost] = field(default_factory=list)
    by_platform: dict[str, list[SocialPost]] = field(default_factory=dict)
    by_ticker: dict[str, list[SocialPost]] = field(default_factory=dict)
    total_posts: int = 0
    unique_tickers: list[str] = field(default_factory=list)
    platform_counts: dict[str, int] = field(default_factory=dict)
    crawl_results: list[CrawlResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_posts": self.total_posts,
            "unique_tickers": self.unique_tickers,
            "platform_counts": self.platform_counts,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AggregatorConfig:
    """Configuration for the feed aggregator."""
    # Deduplication
    dedup_window_minutes: int = 60  # Consider posts within this window for dedup
    similarity_threshold: float = 0.8  # Text similarity threshold for dedup
    # Filtering
    min_tickers: int = 1  # Posts must mention at least N tickers
    # Sorting
    sort_by: str = "engagement"  # "engagement", "recency", "sentiment_strength"
    # Limits
    max_posts_per_platform: int = 200
    max_total_posts: int = 500
    # Concurrent crawling
    crawl_timeout: float = 30.0  # seconds per crawler


class FeedAggregator:
    """Aggregates feeds from multiple social platform crawlers.

    Runs all crawlers concurrently, deduplicates, filters,
    and produces a unified feed.

    Example:
        agg = FeedAggregator()
        agg.add_crawler(twitter_crawler)
        agg.add_crawler(reddit_crawler)
        agg.add_crawler(discord_crawler)
        feed = await agg.crawl_all()
        print(feed.unique_tickers)
    """

    def __init__(self, config: Optional[AggregatorConfig] = None):
        self._config = config or AggregatorConfig()
        self._crawlers: list[CrawlerProtocol] = []
        self._last_feed: Optional[AggregatedFeed] = None
        self._seen_texts: set[str] = set()  # For dedup

    @property
    def crawlers(self) -> list[CrawlerProtocol]:
        return list(self._crawlers)

    @property
    def last_feed(self) -> Optional[AggregatedFeed]:
        return self._last_feed

    def add_crawler(self, crawler: CrawlerProtocol) -> None:
        """Add a crawler to the aggregator."""
        self._crawlers.append(crawler)

    def remove_crawler(self, platform: PlatformType) -> None:
        """Remove a crawler by platform type."""
        self._crawlers = [c for c in self._crawlers if c.platform != platform]

    async def connect_all(self) -> dict[str, bool]:
        """Connect all crawlers."""
        results = {}
        for crawler in self._crawlers:
            try:
                success = await crawler.connect()
                results[crawler.platform.value] = success
            except Exception as e:
                results[crawler.platform.value] = False
                logger.error(f"Connect failed for {crawler.platform.value}: {e}")
        return results

    async def disconnect_all(self) -> None:
        """Disconnect all crawlers."""
        for crawler in self._crawlers:
            try:
                await crawler.disconnect()
            except Exception as e:
                logger.error(f"Disconnect failed for {crawler.platform.value}: {e}")

    async def crawl_all(self) -> AggregatedFeed:
        """Run all crawlers concurrently and aggregate results."""
        start = time.monotonic()

        # Run crawlers concurrently with timeout
        tasks = [
            asyncio.wait_for(
                crawler.crawl(),
                timeout=self._config.crawl_timeout,
            )
            for crawler in self._crawlers
        ]

        results: list[CrawlResult] = []
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                results.append(result)
            except asyncio.TimeoutError:
                logger.warning("Crawler timed out")
            except Exception as e:
                logger.error(f"Crawler error: {e}")

        # Merge all posts
        all_posts: list[SocialPost] = []
        for result in results:
            posts = result.posts[:self._config.max_posts_per_platform]
            all_posts.extend(posts)

        # Deduplicate
        unique_posts = self._deduplicate(all_posts)

        # Filter
        filtered = [
            p for p in unique_posts
            if len(p.tickers) >= self._config.min_tickers
        ]

        # Sort
        filtered = self._sort_posts(filtered)

        # Limit
        filtered = filtered[:self._config.max_total_posts]

        # Build aggregated feed
        feed = AggregatedFeed(
            posts=filtered,
            total_posts=len(filtered),
            crawl_results=results,
            duration_ms=(time.monotonic() - start) * 1000,
        )

        # Index by platform
        for post in filtered:
            feed.by_platform.setdefault(post.source, []).append(post)
            for ticker in post.tickers:
                feed.by_ticker.setdefault(ticker, []).append(post)

        feed.unique_tickers = sorted(feed.by_ticker.keys())
        feed.platform_counts = {k: len(v) for k, v in feed.by_platform.items()}

        self._last_feed = feed
        return feed

    def get_stats(self) -> list[CrawlerStats]:
        """Get stats from all crawlers."""
        return [c.stats for c in self._crawlers]

    def _deduplicate(self, posts: list[SocialPost]) -> list[SocialPost]:
        """Remove duplicate posts based on text similarity."""
        unique: list[SocialPost] = []

        for post in posts:
            # Simple dedup: check if first 100 chars of text already seen
            text_key = post.text[:100].lower().strip()
            if text_key in self._seen_texts:
                continue

            self._seen_texts.add(text_key)
            unique.append(post)

        # Trim seen set if too large
        if len(self._seen_texts) > 10000:
            self._seen_texts = set(list(self._seen_texts)[-5000:])

        return unique

    def _sort_posts(self, posts: list[SocialPost]) -> list[SocialPost]:
        """Sort posts by configured criteria."""
        if self._config.sort_by == "engagement":
            return sorted(
                posts,
                key=lambda p: p.upvotes + p.comments,
                reverse=True,
            )
        elif self._config.sort_by == "sentiment_strength":
            return sorted(
                posts,
                key=lambda p: abs(p.sentiment),
                reverse=True,
            )
        else:  # recency
            return sorted(
                posts,
                key=lambda p: p.timestamp,
                reverse=True,
            )
