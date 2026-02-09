"""Cross-Platform Correlator (PRD-141).

Analyzes sentiment agreement/disagreement across social media
platforms. Consensus signals (all platforms agree) receive higher
confidence than divergent signals.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from src.sentiment.social import SocialPost

logger = logging.getLogger(__name__)


@dataclass
class CorrelatorConfig:
    """Configuration for cross-platform correlation."""
    # Minimum platforms for consensus
    min_platforms_for_consensus: int = 2
    # Agreement threshold (sentiment diff within this = agree)
    agreement_threshold: float = 0.3
    # Minimum posts per platform to include
    min_posts_per_platform: int = 1
    # Platform weighting for consensus
    platform_weights: dict = field(default_factory=lambda: {
        "twitter": 0.30,
        "reddit": 0.25,
        "discord": 0.20,
        "telegram": 0.15,
        "whatsapp": 0.10,
    })


@dataclass
class PlatformConsensus:
    """Sentiment data from a single platform for a ticker."""
    platform: str = ""
    avg_sentiment: float = 0.0
    post_count: int = 0
    total_engagement: int = 0
    direction: str = "neutral"

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "avg_sentiment": round(self.avg_sentiment, 2),
            "post_count": self.post_count,
            "direction": self.direction,
        }


@dataclass
class CorrelationResult:
    """Cross-platform correlation result for a ticker."""
    symbol: str = ""
    platforms: list = field(default_factory=list)  # list[PlatformConsensus]
    consensus_sentiment: float = 0.0
    consensus_direction: str = "neutral"
    agreement_score: float = 0.0  # 0-1, higher = more platforms agree
    platform_count: int = 0
    is_consensus: bool = False
    is_divergent: bool = False
    confidence: float = 0.0
    strongest_platform: str = ""
    weakest_platform: str = ""
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "consensus_sentiment": round(self.consensus_sentiment, 2),
            "consensus_direction": self.consensus_direction,
            "agreement_score": round(self.agreement_score, 2),
            "platform_count": self.platform_count,
            "is_consensus": self.is_consensus,
            "is_divergent": self.is_divergent,
            "confidence": round(self.confidence, 2),
            "platforms": [p.to_dict() for p in self.platforms],
        }


class CrossPlatformCorrelator:
    """Correlates social signals across platforms.

    Analyzes whether platforms agree or disagree on sentiment
    for each ticker. Consensus signals (3+ platforms bullish)
    receive higher confidence than single-platform signals.

    Example:
        correlator = CrossPlatformCorrelator()
        results = correlator.correlate(posts)
        for r in results:
            if r.is_consensus:
                print(f"{r.symbol}: {r.consensus_direction} consensus")
    """

    def __init__(self, config: Optional[CorrelatorConfig] = None):
        self.config = config or CorrelatorConfig()

    def correlate(
        self,
        posts: list[SocialPost],
    ) -> list[CorrelationResult]:
        """Correlate sentiment across platforms.

        Args:
            posts: Social media posts from multiple platforms.

        Returns:
            List of CorrelationResult per ticker, sorted by agreement.
        """
        if not posts:
            return []

        # Group: ticker -> platform -> posts
        grouped: dict[str, dict[str, list[SocialPost]]] = {}
        for post in posts:
            for ticker in post.tickers:
                if ticker not in grouped:
                    grouped[ticker] = {}
                platform = post.source
                grouped[ticker].setdefault(platform, []).append(post)

        results = []
        for symbol, by_platform in grouped.items():
            result = self._analyze_ticker(symbol, by_platform)
            results.append(result)

        results.sort(key=lambda r: r.agreement_score, reverse=True)
        return results

    def correlate_mentions(
        self,
        platform_sentiments: dict[str, dict[str, float]],
    ) -> list[CorrelationResult]:
        """Correlate from pre-aggregated per-platform sentiment.

        Args:
            platform_sentiments: Dict of symbol -> {platform: avg_sentiment}.

        Returns:
            List of CorrelationResult.
        """
        results = []
        for symbol, by_platform in platform_sentiments.items():
            platforms = []
            for platform, sentiment in by_platform.items():
                direction = "bullish" if sentiment > 0.1 else (
                    "bearish" if sentiment < -0.1 else "neutral"
                )
                platforms.append(PlatformConsensus(
                    platform=platform,
                    avg_sentiment=sentiment,
                    post_count=1,
                    direction=direction,
                ))

            result = self._build_result(symbol, platforms)
            results.append(result)

        results.sort(key=lambda r: r.agreement_score, reverse=True)
        return results

    def _analyze_ticker(
        self,
        symbol: str,
        by_platform: dict[str, list[SocialPost]],
    ) -> CorrelationResult:
        """Analyze cross-platform sentiment for one ticker."""
        cfg = self.config
        platforms = []

        for platform, plat_posts in by_platform.items():
            if len(plat_posts) < cfg.min_posts_per_platform:
                continue

            sentiments = [p.sentiment for p in plat_posts]
            avg_sent = float(np.mean(sentiments))
            engagement = sum(p.upvotes + p.comments for p in plat_posts)

            direction = "bullish" if avg_sent > 0.1 else (
                "bearish" if avg_sent < -0.1 else "neutral"
            )

            platforms.append(PlatformConsensus(
                platform=platform,
                avg_sentiment=avg_sent,
                post_count=len(plat_posts),
                total_engagement=engagement,
                direction=direction,
            ))

        return self._build_result(symbol, platforms)

    def _build_result(
        self,
        symbol: str,
        platforms: list[PlatformConsensus],
    ) -> CorrelationResult:
        """Build CorrelationResult from platform consensus data."""
        cfg = self.config
        result = CorrelationResult(symbol=symbol, platforms=platforms)

        if not platforms:
            return result

        result.platform_count = len(platforms)

        # Weighted consensus sentiment
        total_weight = 0.0
        weighted_sum = 0.0
        for pc in platforms:
            w = cfg.platform_weights.get(pc.platform, 0.1)
            weighted_sum += pc.avg_sentiment * w
            total_weight += w

        result.consensus_sentiment = (
            weighted_sum / total_weight if total_weight > 0 else 0.0
        )
        result.consensus_direction = (
            "bullish" if result.consensus_sentiment > 0.1
            else ("bearish" if result.consensus_sentiment < -0.1 else "neutral")
        )

        # Agreement: check how many platforms agree on direction
        directions = [pc.direction for pc in platforms]
        if directions:
            most_common = max(set(directions), key=directions.count)
            agree_count = directions.count(most_common)
            result.agreement_score = agree_count / len(directions)

            # Also check sentiment spread
            sentiments = [pc.avg_sentiment for pc in platforms]
            spread = max(sentiments) - min(sentiments) if len(sentiments) > 1 else 0
            if spread <= cfg.agreement_threshold:
                result.agreement_score = min(1.0, result.agreement_score + 0.2)

        # Consensus and divergence flags
        result.is_consensus = (
            result.platform_count >= cfg.min_platforms_for_consensus
            and result.agreement_score >= 0.7
        )
        result.is_divergent = (
            result.platform_count >= cfg.min_platforms_for_consensus
            and result.agreement_score < 0.5
        )

        # Confidence
        platform_bonus = min(1.0, result.platform_count / 3)
        result.confidence = result.agreement_score * 0.6 + platform_bonus * 0.4

        # Strongest/weakest
        if platforms:
            by_engagement = sorted(
                platforms,
                key=lambda p: p.total_engagement,
                reverse=True,
            )
            result.strongest_platform = by_engagement[0].platform
            result.weakest_platform = by_engagement[-1].platform

        return result
