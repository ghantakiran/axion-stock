"""Influencer Tracking (PRD-141).

Identifies high-impact social media authors and tracks their
sentiment predictions for accuracy weighting. Influencer signals
receive higher weight in the composite scoring.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from src.sentiment.social import SocialPost

logger = logging.getLogger(__name__)


@dataclass
class InfluencerConfig:
    """Configuration for influencer tracking."""
    # Minimum engagement to be considered an influencer
    min_total_upvotes: int = 500
    min_posts: int = 5
    # Accuracy tracking
    accuracy_window_days: int = 30
    # Impact tiers
    mega_influencer_threshold: int = 10000  # total upvotes
    macro_influencer_threshold: int = 5000
    micro_influencer_threshold: int = 1000
    # Prediction evaluation
    price_move_threshold_pct: float = 2.0  # min price move to count


@dataclass
class InfluencerProfile:
    """Profile of a tracked social media influencer."""
    author_id: str = ""
    platform: str = ""
    total_posts: int = 0
    total_upvotes: int = 0
    total_comments: int = 0
    avg_sentiment: float = 0.0
    accuracy_rate: float = 0.0  # % of predictions that moved in predicted direction
    predictions_tracked: int = 0
    correct_predictions: int = 0
    tier: str = "nano"  # mega, macro, micro, nano
    impact_score: float = 0.0  # 0-1 composite of reach + accuracy
    top_tickers: list = field(default_factory=list)
    last_seen: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "author_id": self.author_id,
            "platform": self.platform,
            "tier": self.tier,
            "total_posts": self.total_posts,
            "total_upvotes": self.total_upvotes,
            "accuracy_rate": round(self.accuracy_rate, 2),
            "impact_score": round(self.impact_score, 2),
            "top_tickers": self.top_tickers[:5],
        }


@dataclass
class InfluencerSignal:
    """A signal from a tracked influencer."""
    author_id: str = ""
    platform: str = ""
    symbol: str = ""
    sentiment: float = 0.0
    direction: str = "neutral"
    impact_score: float = 0.0
    tier: str = "nano"
    confidence: float = 0.0  # impact_score * abs(sentiment)
    text: str = ""
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "author_id": self.author_id,
            "platform": self.platform,
            "symbol": self.symbol,
            "direction": self.direction,
            "impact_score": round(self.impact_score, 2),
            "confidence": round(self.confidence, 2),
            "tier": self.tier,
        }


class InfluencerTracker:
    """Tracks and scores social media influencers.

    Builds profiles of high-engagement authors across platforms,
    tracks their prediction accuracy, and generates weighted signals
    based on their historical impact.

    Example:
        tracker = InfluencerTracker()
        tracker.process_posts(posts)
        top = tracker.get_top_influencers(n=10)
        signals = tracker.get_influencer_signals(posts)
    """

    def __init__(self, config: Optional[InfluencerConfig] = None):
        self.config = config or InfluencerConfig()
        self._profiles: dict[str, InfluencerProfile] = {}

    def process_posts(self, posts: list[SocialPost]) -> int:
        """Process posts to update influencer profiles.

        Args:
            posts: Social media posts to analyze.

        Returns:
            Number of influencer profiles updated.
        """
        updated = 0
        for post in posts:
            if not post.author:
                continue

            key = f"{post.source}:{post.author}"

            if key not in self._profiles:
                self._profiles[key] = InfluencerProfile(
                    author_id=post.author,
                    platform=post.source,
                )

            profile = self._profiles[key]
            profile.total_posts += 1
            profile.total_upvotes += post.upvotes
            profile.total_comments += post.comments
            profile.last_seen = datetime.now(timezone.utc)

            # Update running sentiment average
            if profile.total_posts == 1:
                profile.avg_sentiment = post.sentiment
            else:
                profile.avg_sentiment = (
                    profile.avg_sentiment * (profile.total_posts - 1)
                    + post.sentiment
                ) / profile.total_posts

            # Track tickers
            for ticker in post.tickers:
                if ticker not in profile.top_tickers:
                    profile.top_tickers.append(ticker)

            # Update tier
            profile.tier = self._classify_tier(profile.total_upvotes)

            # Update impact score
            profile.impact_score = self._compute_impact(profile)

            updated += 1

        return updated

    def get_influencer_signals(
        self,
        posts: list[SocialPost],
    ) -> list[InfluencerSignal]:
        """Extract signals from posts by tracked influencers.

        Args:
            posts: Social media posts to check.

        Returns:
            List of InfluencerSignal for posts by known influencers.
        """
        signals = []

        for post in posts:
            if not post.author:
                continue

            key = f"{post.source}:{post.author}"
            profile = self._profiles.get(key)

            if not profile or not self._is_influencer(profile):
                continue

            for ticker in post.tickers:
                direction = "bullish" if post.sentiment > 0.1 else (
                    "bearish" if post.sentiment < -0.1 else "neutral"
                )

                signal = InfluencerSignal(
                    author_id=post.author,
                    platform=post.source,
                    symbol=ticker,
                    sentiment=post.sentiment,
                    direction=direction,
                    impact_score=profile.impact_score,
                    tier=profile.tier,
                    confidence=profile.impact_score * abs(post.sentiment),
                    text=post.text[:200],
                )
                signals.append(signal)

        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals

    def get_top_influencers(self, n: int = 10) -> list[InfluencerProfile]:
        """Get top N influencers by impact score.

        Args:
            n: Number of top influencers to return.

        Returns:
            Sorted list of InfluencerProfile.
        """
        influencers = [
            p for p in self._profiles.values()
            if self._is_influencer(p)
        ]
        influencers.sort(key=lambda p: p.impact_score, reverse=True)
        return influencers[:n]

    def get_profile(self, platform: str, author: str) -> Optional[InfluencerProfile]:
        """Look up a specific influencer profile."""
        return self._profiles.get(f"{platform}:{author}")

    def record_prediction(
        self,
        platform: str,
        author: str,
        was_correct: bool,
    ) -> None:
        """Record whether an influencer's prediction was correct.

        Args:
            platform: Source platform.
            author: Author identifier.
            was_correct: Whether the price moved in predicted direction.
        """
        key = f"{platform}:{author}"
        profile = self._profiles.get(key)
        if not profile:
            return

        profile.predictions_tracked += 1
        if was_correct:
            profile.correct_predictions += 1

        if profile.predictions_tracked > 0:
            profile.accuracy_rate = (
                profile.correct_predictions / profile.predictions_tracked
            )

        # Recompute impact with new accuracy data
        profile.impact_score = self._compute_impact(profile)

    @property
    def profiles(self) -> dict[str, InfluencerProfile]:
        """Get all tracked profiles."""
        return dict(self._profiles)

    def _is_influencer(self, profile: InfluencerProfile) -> bool:
        """Check if a profile meets influencer thresholds."""
        return (
            profile.total_upvotes >= self.config.min_total_upvotes
            and profile.total_posts >= self.config.min_posts
        )

    def _classify_tier(self, total_upvotes: int) -> str:
        """Classify influencer tier by engagement."""
        cfg = self.config
        if total_upvotes >= cfg.mega_influencer_threshold:
            return "mega"
        elif total_upvotes >= cfg.macro_influencer_threshold:
            return "macro"
        elif total_upvotes >= cfg.micro_influencer_threshold:
            return "micro"
        return "nano"

    def _compute_impact(self, profile: InfluencerProfile) -> float:
        """Compute composite impact score (0-1)."""
        # Reach component (0-1)
        reach = min(1.0, profile.total_upvotes / self.config.mega_influencer_threshold)

        # Accuracy component (0-1) — default 0.5 if no predictions tracked
        accuracy = (
            profile.accuracy_rate
            if profile.predictions_tracked >= 5
            else 0.5
        )

        # Consistency (posts per day proxy)
        consistency = min(1.0, profile.total_posts / 50)

        return 0.4 * reach + 0.4 * accuracy + 0.2 * consistency
