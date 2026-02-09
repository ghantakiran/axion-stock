"""Influencer Discovery Engine.

Discovers emerging influencers from social post streams.
Ranks candidates by engagement velocity, topic expertise,
and early-mover advantage detection.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryConfig:
    """Configuration for influencer discovery."""

    min_posts: int = 3
    min_engagement_rate: float = 0.5  # upvotes / posts
    lookback_days: int = 30
    max_candidates: int = 50
    velocity_window_days: int = 7
    early_mover_boost: float = 1.5  # Multiplier for first-to-mention


@dataclass
class CandidateProfile:
    """A discovered influencer candidate."""

    author_id: str = ""
    platform: str = ""
    post_count: int = 0
    total_upvotes: int = 0
    engagement_rate: float = 0.0  # upvotes per post
    engagement_velocity: float = 0.0  # upvotes per day
    top_tickers: list[str] = field(default_factory=list)
    sentiment_consistency: float = 0.0  # 0-1 (1 = always same direction)
    first_mention_count: int = 0  # Times they mentioned ticker before crowd
    discovery_score: float = 0.0  # Composite ranking score
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "author_id": self.author_id,
            "platform": self.platform,
            "post_count": self.post_count,
            "total_upvotes": self.total_upvotes,
            "engagement_rate": round(self.engagement_rate, 2),
            "engagement_velocity": round(self.engagement_velocity, 2),
            "top_tickers": self.top_tickers[:5],
            "sentiment_consistency": round(self.sentiment_consistency, 2),
            "first_mention_count": self.first_mention_count,
            "discovery_score": round(self.discovery_score, 3),
        }


@dataclass
class DiscoveryResult:
    """Result of an influencer discovery scan."""

    candidates: list[CandidateProfile] = field(default_factory=list)
    total_posts_analyzed: int = 0
    total_authors_seen: int = 0
    discovery_timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "candidates": [c.to_dict() for c in self.candidates],
            "total_posts_analyzed": self.total_posts_analyzed,
            "total_authors_seen": self.total_authors_seen,
            "discovery_timestamp": self.discovery_timestamp,
        }

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)


@dataclass
class _AuthorStats:
    """Internal author tracking during discovery."""

    author_id: str = ""
    platform: str = ""
    posts: int = 0
    upvotes: int = 0
    sentiments: list[float] = field(default_factory=list)
    tickers: dict[str, int] = field(default_factory=dict)
    timestamps: list[datetime] = field(default_factory=list)
    first_mentions: int = 0  # How many tickers they mentioned first


class InfluencerDiscovery:
    """Discover emerging influencers from social post streams.

    Analyzes posts to find authors with high engagement growth,
    consistent directional calls, and early-mover tendencies.

    Example::

        discovery = InfluencerDiscovery()
        discovery.ingest_posts(posts)
        result = discovery.discover()
        for candidate in result.candidates[:10]:
            print(f"{candidate.author_id}: score={candidate.discovery_score}")
    """

    def __init__(self, config: Optional[DiscoveryConfig] = None):
        self.config = config or DiscoveryConfig()
        self._authors: dict[str, _AuthorStats] = {}
        self._ticker_first_seen: dict[str, tuple[str, datetime]] = {}
        self._total_posts = 0

    def ingest_posts(self, posts: list) -> int:
        """Ingest social posts and build author statistics.

        Args:
            posts: List of SocialPost-like objects with author,
                   source, upvotes, sentiment, tickers, timestamp.

        Returns:
            Number of posts ingested.
        """
        ingested = 0

        for post in posts:
            author = getattr(post, "author", "") or ""
            source = getattr(post, "source", "") or ""
            if not author:
                continue

            key = f"{source}:{author}"

            if key not in self._authors:
                self._authors[key] = _AuthorStats(
                    author_id=author, platform=source
                )

            stats = self._authors[key]
            stats.posts += 1
            stats.upvotes += getattr(post, "upvotes", 0)
            stats.sentiments.append(getattr(post, "sentiment", 0.0))

            ts_str = getattr(post, "timestamp", "")
            ts = None
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    ts = datetime.now(timezone.utc)
            else:
                ts = datetime.now(timezone.utc)

            stats.timestamps.append(ts)

            # Track tickers
            tickers = getattr(post, "tickers", []) or []
            for ticker in tickers:
                stats.tickers[ticker] = stats.tickers.get(ticker, 0) + 1

                # Track first mention
                if ticker not in self._ticker_first_seen:
                    self._ticker_first_seen[ticker] = (key, ts)
                elif self._ticker_first_seen[ticker][0] == key:
                    pass  # Already the first
                # Don't overwrite with later mention

            ingested += 1
            self._total_posts += 1

        # Update first-mention counts
        for ticker, (first_key, _) in self._ticker_first_seen.items():
            if first_key in self._authors:
                # Only increment if this is new (avoid double counting)
                pass

        return ingested

    def discover(self) -> DiscoveryResult:
        """Run discovery to find emerging influencer candidates.

        Returns:
            DiscoveryResult with ranked candidates.
        """
        candidates = []

        for key, stats in self._authors.items():
            if stats.posts < self.config.min_posts:
                continue

            engagement_rate = stats.upvotes / max(stats.posts, 1)
            if engagement_rate < self.config.min_engagement_rate:
                continue

            # Engagement velocity (upvotes per day)
            if stats.timestamps:
                span_days = max(
                    (max(stats.timestamps) - min(stats.timestamps)).total_seconds() / 86400,
                    1.0,
                )
                velocity = stats.upvotes / span_days
            else:
                velocity = 0.0

            # Sentiment consistency (standard deviation → consistency)
            if len(stats.sentiments) > 1:
                mean_s = sum(stats.sentiments) / len(stats.sentiments)
                variance = sum((s - mean_s) ** 2 for s in stats.sentiments) / len(stats.sentiments)
                consistency = max(0, 1 - variance ** 0.5 * 2)
            else:
                consistency = 0.5

            # First mention count
            first_mentions = sum(
                1 for t, (fk, _) in self._ticker_first_seen.items()
                if fk == key
            )

            # Top tickers
            sorted_tickers = sorted(stats.tickers.items(), key=lambda x: -x[1])
            top_tickers = [t for t, _ in sorted_tickers[:5]]

            # Discovery score: weighted composite
            score = (
                0.30 * min(velocity / 100, 1.0)  # velocity component
                + 0.25 * min(engagement_rate / 50, 1.0)  # engagement rate
                + 0.20 * consistency  # consistency
                + 0.15 * min(first_mentions * self.config.early_mover_boost / 5, 1.0)
                + 0.10 * min(stats.posts / 20, 1.0)  # activity volume
            )

            candidate = CandidateProfile(
                author_id=stats.author_id,
                platform=stats.platform,
                post_count=stats.posts,
                total_upvotes=stats.upvotes,
                engagement_rate=engagement_rate,
                engagement_velocity=velocity,
                top_tickers=top_tickers,
                sentiment_consistency=consistency,
                first_mention_count=first_mentions,
                discovery_score=score,
                first_seen=min(stats.timestamps) if stats.timestamps else None,
                last_seen=max(stats.timestamps) if stats.timestamps else None,
            )
            candidates.append(candidate)

        # Sort by discovery score
        candidates.sort(key=lambda c: c.discovery_score, reverse=True)
        candidates = candidates[:self.config.max_candidates]

        return DiscoveryResult(
            candidates=candidates,
            total_posts_analyzed=self._total_posts,
            total_authors_seen=len(self._authors),
            discovery_timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def clear(self):
        """Reset all discovery state."""
        self._authors.clear()
        self._ticker_first_seen.clear()
        self._total_posts = 0
