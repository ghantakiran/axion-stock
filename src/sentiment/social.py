"""Social Media Sentiment Monitoring.

Monitors Reddit, Twitter/X, and StockTwits for stock mentions,
sentiment, and trending detection.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from src.sentiment.config import SocialMediaConfig

logger = logging.getLogger(__name__)


@dataclass
class TickerMention:
    """Aggregated mentions of a ticker from social media."""

    symbol: str = ""
    count: int = 0
    scores: list = field(default_factory=list)
    total_upvotes: int = 0
    total_comments: int = 0
    sources: list = field(default_factory=list)
    sample_posts: list = field(default_factory=list)

    @property
    def avg_sentiment(self) -> float:
        return float(np.mean(self.scores)) if self.scores else 0.0

    @property
    def engagement(self) -> int:
        return self.total_upvotes + self.total_comments

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "mention_count": self.count,
            "avg_sentiment": self.avg_sentiment,
            "total_upvotes": self.total_upvotes,
            "total_comments": self.total_comments,
            "engagement": self.engagement,
        }


@dataclass
class SocialPost:
    """Individual social media post."""

    text: str = ""
    source: str = ""  # reddit, twitter, stocktwits
    author: str = ""
    timestamp: str = ""
    upvotes: int = 0
    comments: int = 0
    sentiment: float = 0.0
    tickers: list = field(default_factory=list)
    url: str = ""


@dataclass
class TrendingAlert:
    """Alert for a trending ticker on social media."""

    symbol: str = ""
    source: str = ""
    current_mentions: int = 0
    avg_mentions: int = 0
    spike_ratio: float = 0.0
    sentiment: float = 0.0
    detected_at: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "source": self.source,
            "current_mentions": self.current_mentions,
            "avg_mentions": self.avg_mentions,
            "spike_ratio": self.spike_ratio,
            "sentiment": self.sentiment,
            "detected_at": self.detected_at,
        }


@dataclass
class SocialSentimentSummary:
    """Aggregated social media sentiment for a symbol."""

    symbol: str = ""
    reddit_sentiment: float = 0.0
    reddit_mentions: int = 0
    twitter_sentiment: float = 0.0
    twitter_mentions: int = 0
    stocktwits_sentiment: float = 0.0
    stocktwits_mentions: int = 0
    composite_sentiment: float = 0.0
    total_mentions: int = 0
    bullish_pct: float = 0.5
    is_trending: bool = False

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "reddit_sentiment": self.reddit_sentiment,
            "reddit_mentions": self.reddit_mentions,
            "twitter_sentiment": self.twitter_sentiment,
            "twitter_mentions": self.twitter_mentions,
            "stocktwits_sentiment": self.stocktwits_sentiment,
            "stocktwits_mentions": self.stocktwits_mentions,
            "composite_sentiment": self.composite_sentiment,
            "total_mentions": self.total_mentions,
            "bullish_pct": self.bullish_pct,
            "is_trending": self.is_trending,
        }


class SocialMediaMonitor:
    """Monitor social media for stock sentiment and trending tickers.

    Processes posts from Reddit, Twitter/X, and StockTwits to extract
    mentions, sentiment, and detect trending stocks.

    Example:
        monitor = SocialMediaMonitor()
        mentions = monitor.process_posts(posts)
        trending = monitor.detect_trending(current_mentions, historical)
        summary = monitor.get_symbol_summary("AAPL", posts)
    """

    def __init__(self, config: Optional[SocialMediaConfig] = None):
        self.config = config or SocialMediaConfig()

    def process_posts(
        self,
        posts: list[SocialPost],
    ) -> dict[str, TickerMention]:
        """Process social media posts to extract ticker mentions.

        Args:
            posts: List of social media posts.

        Returns:
            Dict of symbol -> TickerMention with aggregated data.
        """
        mentions: dict[str, TickerMention] = {}

        for post in posts:
            tickers = post.tickers
            if not tickers:
                continue

            for ticker in tickers:
                if ticker not in mentions:
                    mentions[ticker] = TickerMention(symbol=ticker)

                m = mentions[ticker]
                m.count += 1
                m.scores.append(post.sentiment)
                m.total_upvotes += post.upvotes
                m.total_comments += post.comments

                if post.source not in m.sources:
                    m.sources.append(post.source)

                if len(m.sample_posts) < 5:
                    m.sample_posts.append(post.text[:200])

        return mentions

    def detect_trending(
        self,
        current_mentions: dict[str, int],
        historical_avg: dict[str, float],
    ) -> list[TrendingAlert]:
        """Detect trending tickers by comparing to historical averages.

        Args:
            current_mentions: Current period mention counts by symbol.
            historical_avg: Historical average mention counts.

        Returns:
            List of TrendingAlert for spiking tickers.
        """
        alerts = []
        now = datetime.now().isoformat()

        for symbol, count in current_mentions.items():
            avg = historical_avg.get(symbol, 0)
            if avg <= 0:
                avg = 1.0  # Avoid division by zero; treat as new ticker

            ratio = count / avg

            if ratio >= self.config.trending_threshold_multiplier:
                alerts.append(TrendingAlert(
                    symbol=symbol,
                    source="aggregate",
                    current_mentions=count,
                    avg_mentions=int(avg),
                    spike_ratio=ratio,
                    detected_at=now,
                ))

        alerts.sort(key=lambda a: a.spike_ratio, reverse=True)
        return alerts

    def detect_mention_spike(
        self,
        mention_timeseries: pd.Series,
    ) -> bool:
        """Detect sudden spike in mention volume.

        Args:
            mention_timeseries: Hourly mention counts.

        Returns:
            True if spike detected.
        """
        if len(mention_timeseries) < self.config.spike_detection_window_hours + 1:
            return False

        recent = mention_timeseries.iloc[-1]
        baseline = mention_timeseries.iloc[
            -self.config.spike_detection_window_hours - 1:-1
        ].mean()

        if baseline <= 0:
            return bool(recent > 0)

        return bool(recent > baseline * self.config.spike_multiplier)

    def get_symbol_summary(
        self,
        symbol: str,
        posts: list[SocialPost],
        historical_avg_mentions: Optional[dict] = None,
    ) -> SocialSentimentSummary:
        """Get aggregated social sentiment for a symbol.

        Args:
            symbol: Stock ticker.
            posts: All social media posts (will filter for symbol).
            historical_avg_mentions: Historical averages for trending detection.

        Returns:
            SocialSentimentSummary for the symbol.
        """
        relevant = [p for p in posts if symbol in p.tickers]
        summary = SocialSentimentSummary(symbol=symbol)

        if not relevant:
            return summary

        # By source
        by_source: dict[str, list[SocialPost]] = {}
        for post in relevant:
            by_source.setdefault(post.source, []).append(post)

        reddit_posts = by_source.get("reddit", [])
        twitter_posts = by_source.get("twitter", [])
        stocktwits_posts = by_source.get("stocktwits", [])

        if reddit_posts:
            summary.reddit_mentions = len(reddit_posts)
            summary.reddit_sentiment = float(np.mean([p.sentiment for p in reddit_posts]))

        if twitter_posts:
            summary.twitter_mentions = len(twitter_posts)
            summary.twitter_sentiment = float(np.mean([p.sentiment for p in twitter_posts]))

        if stocktwits_posts:
            summary.stocktwits_mentions = len(stocktwits_posts)
            summary.stocktwits_sentiment = float(np.mean([p.sentiment for p in stocktwits_posts]))

        summary.total_mentions = len(relevant)
        all_sentiments = [p.sentiment for p in relevant]
        summary.composite_sentiment = float(np.mean(all_sentiments))
        summary.bullish_pct = float(np.mean([1 if s > 0 else 0 for s in all_sentiments]))

        # Trending detection
        if historical_avg_mentions:
            avg = historical_avg_mentions.get(symbol, 0)
            if avg > 0 and summary.total_mentions > avg * self.config.trending_threshold_multiplier:
                summary.is_trending = True

        return summary

    def rank_by_buzz(
        self,
        mentions: dict[str, TickerMention],
        top_n: int = 20,
    ) -> list[TickerMention]:
        """Rank tickers by social media buzz score.

        Buzz = mention_count * log(engagement + 1)

        Args:
            mentions: Dict of symbol -> TickerMention.
            top_n: Number of top tickers to return.

        Returns:
            Sorted list of top TickerMention by buzz.
        """
        for m in mentions.values():
            m._buzz = m.count * np.log1p(m.engagement)

        ranked = sorted(mentions.values(), key=lambda m: m._buzz, reverse=True)

        # Clean up temp attribute
        for m in ranked:
            if hasattr(m, "_buzz"):
                delattr(m, "_buzz")

        return ranked[:top_n]
