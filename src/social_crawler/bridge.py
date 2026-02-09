"""Social Crawler Bridge (PRD-140).

Bridges the social crawler output to the existing SocialMediaMonitor
(src/sentiment/social.py), enabling the crawled data to flow into
the platform's sentiment analysis pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import logging

from src.sentiment.social import (
    SocialMediaMonitor,
    SocialPost,
    SocialSentimentSummary,
    TickerMention,
    TrendingAlert,
)
from src.social_crawler.aggregator import AggregatedFeed, FeedAggregator

logger = logging.getLogger(__name__)


@dataclass
class BridgeResult:
    """Result of bridging crawler data to sentiment pipeline."""
    mentions: dict[str, TickerMention] = field(default_factory=dict)
    trending: list[TrendingAlert] = field(default_factory=list)
    summaries: dict[str, SocialSentimentSummary] = field(default_factory=dict)
    total_posts_processed: int = 0
    total_tickers_found: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "total_posts_processed": self.total_posts_processed,
            "total_tickers_found": self.total_tickers_found,
            "trending_count": len(self.trending),
            "top_mentions": [
                m.to_dict()
                for m in sorted(
                    self.mentions.values(),
                    key=lambda m: m.count,
                    reverse=True,
                )[:10]
            ],
            "trending": [t.to_dict() for t in self.trending[:5]],
        }


class SocialCrawlerBridge:
    """Bridges crawler output into the sentiment analysis pipeline.

    Takes an AggregatedFeed from the FeedAggregator and processes it
    through SocialMediaMonitor to produce TickerMentions, TrendingAlerts,
    and SocialSentimentSummaries.

    Example:
        bridge = SocialCrawlerBridge()
        feed = await aggregator.crawl_all()
        result = bridge.process_feed(feed)
        # result.mentions has per-ticker aggregated data
        # result.trending has spike alerts
    """

    def __init__(
        self,
        monitor: Optional[SocialMediaMonitor] = None,
        historical_mentions: Optional[dict[str, float]] = None,
    ):
        self._monitor = monitor or SocialMediaMonitor()
        self._historical_mentions = historical_mentions or {}
        # Running averages for trending detection
        self._mention_history: dict[str, list[int]] = {}
        self._history_window = 24  # hours

    def process_feed(self, feed: AggregatedFeed) -> BridgeResult:
        """Process an aggregated feed through the sentiment pipeline.

        Args:
            feed: AggregatedFeed from FeedAggregator.crawl_all()

        Returns:
            BridgeResult with mentions, trending alerts, and summaries.
        """
        result = BridgeResult()

        if not feed.posts:
            return result

        # Step 1: Process posts through SocialMediaMonitor
        mentions = self._monitor.process_posts(feed.posts)
        result.mentions = mentions
        result.total_posts_processed = feed.total_posts
        result.total_tickers_found = len(mentions)

        # Step 2: Detect trending tickers
        current_counts = {sym: m.count for sym, m in mentions.items()}
        historical = self._get_historical_averages(current_counts)
        result.trending = self._monitor.detect_trending(current_counts, historical)

        # Step 3: Build per-ticker summaries
        for symbol in mentions:
            summary = self._monitor.get_symbol_summary(
                symbol, feed.posts, historical
            )
            result.summaries[symbol] = summary

        # Step 4: Update historical mention tracking
        self._update_history(current_counts)

        return result

    def process_posts(self, posts: list[SocialPost]) -> BridgeResult:
        """Process a list of posts directly (without aggregator)."""
        from src.social_crawler.aggregator import AggregatedFeed

        feed = AggregatedFeed(
            posts=posts,
            total_posts=len(posts),
        )
        return self.process_feed(feed)

    def get_top_mentions(self, n: int = 10) -> list[TickerMention]:
        """Get top N most-mentioned tickers from the last feed."""
        if not hasattr(self, "_last_result"):
            return []
        mentions = list(self._last_result.mentions.values())
        return sorted(mentions, key=lambda m: m.count, reverse=True)[:n]

    def _get_historical_averages(
        self, current: dict[str, int]
    ) -> dict[str, float]:
        """Get historical mention averages for trending detection."""
        # Merge provided historical data with running averages
        averages = dict(self._historical_mentions)

        for symbol, history in self._mention_history.items():
            if history:
                averages[symbol] = sum(history) / len(history)

        return averages

    def _update_history(self, current_counts: dict[str, int]) -> None:
        """Update running mention history."""
        for symbol, count in current_counts.items():
            if symbol not in self._mention_history:
                self._mention_history[symbol] = []

            self._mention_history[symbol].append(count)

            # Trim to window
            if len(self._mention_history[symbol]) > self._history_window:
                self._mention_history[symbol] = self._mention_history[symbol][
                    -self._history_window:
                ]
