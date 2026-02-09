"""Social Signal Scorer (PRD-141).

Multi-factor composite scoring of social media signals.
Combines sentiment, engagement, velocity, freshness, and
source credibility into a single 0-100 signal strength score.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import numpy as np

from src.sentiment.social import SocialPost, TickerMention

logger = logging.getLogger(__name__)


class SignalStrength(Enum):
    """Categorical signal strength."""
    VERY_STRONG = "very_strong"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NOISE = "noise"


@dataclass
class ScorerConfig:
    """Configuration for signal scoring."""
    # Factor weights (sum to 1.0)
    sentiment_weight: float = 0.30
    engagement_weight: float = 0.20
    velocity_weight: float = 0.20
    freshness_weight: float = 0.15
    credibility_weight: float = 0.15

    # Thresholds for signal strength categories
    very_strong_threshold: int = 80
    strong_threshold: int = 60
    moderate_threshold: int = 40
    weak_threshold: int = 20

    # Engagement normalization
    max_upvotes_cap: int = 10000
    max_comments_cap: int = 5000

    # Freshness decay (hours)
    freshness_halflife_hours: float = 6.0

    # Source credibility scores
    source_credibility: dict = field(default_factory=lambda: {
        "twitter": 0.70,
        "reddit": 0.65,
        "discord": 0.55,
        "telegram": 0.50,
        "whatsapp": 0.45,
        "stocktwits": 0.60,
    })


@dataclass
class ScoredTicker:
    """A ticker with composite signal score."""
    symbol: str = ""
    score: float = 0.0
    strength: SignalStrength = SignalStrength.NOISE
    sentiment_score: float = 0.0
    engagement_score: float = 0.0
    velocity_score: float = 0.0
    freshness_score: float = 0.0
    credibility_score: float = 0.0
    mention_count: int = 0
    avg_sentiment: float = 0.0
    total_engagement: int = 0
    platforms: list = field(default_factory=list)
    top_posts: list = field(default_factory=list)
    direction: str = "neutral"  # bullish, bearish, neutral
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": round(self.score, 1),
            "strength": self.strength.value,
            "sentiment_score": round(self.sentiment_score, 2),
            "engagement_score": round(self.engagement_score, 2),
            "velocity_score": round(self.velocity_score, 2),
            "freshness_score": round(self.freshness_score, 2),
            "credibility_score": round(self.credibility_score, 2),
            "mention_count": self.mention_count,
            "avg_sentiment": round(self.avg_sentiment, 2),
            "direction": self.direction,
            "platforms": self.platforms,
        }


class SignalScorer:
    """Multi-factor social signal scorer.

    Combines five factors into a composite 0-100 score:
    1. Sentiment — average sentiment polarity + consistency
    2. Engagement — normalized upvotes + comments
    3. Velocity — mention acceleration vs baseline
    4. Freshness — time decay of recent posts
    5. Credibility — source platform reliability weighting

    Example:
        scorer = SignalScorer()
        scored = scorer.score_posts(posts)
        for ticker in scored:
            print(f"{ticker.symbol}: {ticker.score} ({ticker.strength.value})")
    """

    def __init__(self, config: Optional[ScorerConfig] = None):
        self.config = config or ScorerConfig()
        self._mention_history: dict[str, list[int]] = {}

    def score_posts(
        self,
        posts: list[SocialPost],
        mention_baselines: Optional[dict[str, float]] = None,
    ) -> list[ScoredTicker]:
        """Score all tickers found in the given posts.

        Args:
            posts: Social media posts to analyze.
            mention_baselines: Historical average mention counts per ticker.

        Returns:
            List of ScoredTicker sorted by score descending.
        """
        if not posts:
            return []

        baselines = mention_baselines or {}

        # Group posts by ticker
        by_ticker: dict[str, list[SocialPost]] = {}
        for post in posts:
            for ticker in post.tickers:
                by_ticker.setdefault(ticker, []).append(post)

        scored = []
        for symbol, ticker_posts in by_ticker.items():
            st = self._score_ticker(symbol, ticker_posts, baselines)
            scored.append(st)

        scored.sort(key=lambda s: s.score, reverse=True)
        return scored

    def score_mentions(
        self,
        mentions: dict[str, TickerMention],
        mention_baselines: Optional[dict[str, float]] = None,
    ) -> list[ScoredTicker]:
        """Score from pre-aggregated TickerMention data.

        Args:
            mentions: Dict of symbol -> TickerMention.
            mention_baselines: Historical average mention counts.

        Returns:
            List of ScoredTicker sorted by score descending.
        """
        if not mentions:
            return []

        baselines = mention_baselines or {}
        scored = []

        for symbol, mention in mentions.items():
            st = ScoredTicker(symbol=symbol)

            # Sentiment factor
            st.avg_sentiment = mention.avg_sentiment
            st.sentiment_score = self._sentiment_factor(mention.avg_sentiment)

            # Engagement factor
            st.total_engagement = mention.engagement
            st.engagement_score = self._engagement_factor(
                mention.total_upvotes, mention.total_comments
            )

            # Velocity factor
            baseline = baselines.get(symbol, 1.0)
            st.velocity_score = self._velocity_factor(mention.count, baseline)

            # Freshness (assume recent)
            st.freshness_score = 1.0

            # Credibility
            st.credibility_score = self._credibility_factor(mention.sources)

            # Composite
            st.score = self._composite_score(st)
            st.strength = self._classify_strength(st.score)
            st.mention_count = mention.count
            st.platforms = list(mention.sources)
            st.direction = "bullish" if mention.avg_sentiment > 0.1 else (
                "bearish" if mention.avg_sentiment < -0.1 else "neutral"
            )

            scored.append(st)

        scored.sort(key=lambda s: s.score, reverse=True)
        return scored

    def update_baseline(self, symbol: str, count: int) -> None:
        """Update running mention history for velocity calculation."""
        if symbol not in self._mention_history:
            self._mention_history[symbol] = []
        self._mention_history[symbol].append(count)
        if len(self._mention_history[symbol]) > 168:  # 1 week of hourly
            self._mention_history[symbol] = self._mention_history[symbol][-168:]

    def get_baseline(self, symbol: str) -> float:
        """Get average baseline mentions for a ticker."""
        history = self._mention_history.get(symbol, [])
        return float(np.mean(history)) if history else 1.0

    def _score_ticker(
        self,
        symbol: str,
        posts: list[SocialPost],
        baselines: dict[str, float],
    ) -> ScoredTicker:
        """Score a single ticker from its posts."""
        st = ScoredTicker(symbol=symbol)

        # Sentiment factor
        sentiments = [p.sentiment for p in posts]
        st.avg_sentiment = float(np.mean(sentiments)) if sentiments else 0.0
        st.sentiment_score = self._sentiment_factor(st.avg_sentiment)

        # Engagement factor
        total_upvotes = sum(p.upvotes for p in posts)
        total_comments = sum(p.comments for p in posts)
        st.total_engagement = total_upvotes + total_comments
        st.engagement_score = self._engagement_factor(total_upvotes, total_comments)

        # Velocity factor
        baseline = baselines.get(symbol, 1.0)
        st.velocity_score = self._velocity_factor(len(posts), baseline)

        # Freshness factor
        st.freshness_score = self._freshness_factor(posts)

        # Credibility factor
        sources = list({p.source for p in posts})
        st.credibility_score = self._credibility_factor(sources)

        # Composite score
        st.score = self._composite_score(st)
        st.strength = self._classify_strength(st.score)

        # Metadata
        st.mention_count = len(posts)
        st.platforms = sources
        st.top_posts = [p.text[:200] for p in sorted(
            posts, key=lambda p: p.upvotes + p.comments, reverse=True
        )[:3]]
        st.direction = "bullish" if st.avg_sentiment > 0.1 else (
            "bearish" if st.avg_sentiment < -0.1 else "neutral"
        )

        return st

    def _sentiment_factor(self, avg_sentiment: float) -> float:
        """Convert sentiment to 0-1 factor. Strong sentiment = high score."""
        # Map [-1, 1] to [0, 1] with amplification of extremes
        return min(1.0, abs(avg_sentiment) * 1.5)

    def _engagement_factor(self, upvotes: int, comments: int) -> float:
        """Normalize engagement to 0-1."""
        up_norm = min(upvotes / self.config.max_upvotes_cap, 1.0)
        cm_norm = min(comments / self.config.max_comments_cap, 1.0)
        return 0.6 * up_norm + 0.4 * cm_norm

    def _velocity_factor(self, current: int, baseline: float) -> float:
        """Calculate mention velocity vs baseline."""
        if baseline <= 0:
            baseline = 1.0
        ratio = current / baseline
        # Logarithmic scaling: 1x=0, 3x=0.5, 10x=1.0
        return min(1.0, np.log1p(ratio) / np.log1p(10))

    def _freshness_factor(self, posts: list[SocialPost]) -> float:
        """Calculate freshness based on post recency."""
        if not posts:
            return 0.0
        # Simple: recent posts → high freshness
        # If posts have timestamps, use time decay
        # Demo: assume posts are recent → high freshness
        return 0.8

    def _credibility_factor(self, sources: list[str]) -> float:
        """Calculate average source credibility."""
        if not sources:
            return 0.5
        scores = [
            self.config.source_credibility.get(s, 0.5)
            for s in sources
        ]
        return float(np.mean(scores))

    def _composite_score(self, st: ScoredTicker) -> float:
        """Compute composite 0-100 score from individual factors."""
        cfg = self.config
        raw = (
            st.sentiment_score * cfg.sentiment_weight
            + st.engagement_score * cfg.engagement_weight
            + st.velocity_score * cfg.velocity_weight
            + st.freshness_score * cfg.freshness_weight
            + st.credibility_score * cfg.credibility_weight
        )
        return round(min(100.0, max(0.0, raw * 100)), 1)

    def _classify_strength(self, score: float) -> SignalStrength:
        """Classify score into signal strength category."""
        cfg = self.config
        if score >= cfg.very_strong_threshold:
            return SignalStrength.VERY_STRONG
        elif score >= cfg.strong_threshold:
            return SignalStrength.STRONG
        elif score >= cfg.moderate_threshold:
            return SignalStrength.MODERATE
        elif score >= cfg.weak_threshold:
            return SignalStrength.WEAK
        return SignalStrength.NOISE
