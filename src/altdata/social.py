"""Social Sentiment Aggregator.

Aggregates social media mentions from multiple sources (Reddit, Twitter/X,
StockTwits, news), computes sentiment scores, detects volume spikes,
and provides cross-source sentiment aggregation.
"""

import logging
from typing import Optional

import numpy as np

from src.altdata.config import (
    SocialConfig,
    SentimentSource,
    DEFAULT_SOCIAL_CONFIG,
)
from src.altdata.models import SocialMention, SocialSentiment

logger = logging.getLogger(__name__)


class SocialSentimentAggregator:
    """Aggregates social sentiment across sources."""

    def __init__(self, config: Optional[SocialConfig] = None) -> None:
        self.config = config or DEFAULT_SOCIAL_CONFIG
        self._mentions: dict[str, list[SocialMention]] = {}

    def add_mention(self, mention: SocialMention) -> None:
        """Add a social media mention."""
        if mention.symbol not in self._mentions:
            self._mentions[mention.symbol] = []
        self._mentions[mention.symbol].append(mention)

    def add_mentions(self, mentions: list[SocialMention]) -> None:
        """Add multiple mentions."""
        for m in mentions:
            self.add_mention(m)

    def analyze(
        self, symbol: str, source: SentimentSource
    ) -> SocialSentiment:
        """Analyze sentiment for a symbol from a specific source.

        Returns:
            SocialSentiment with aggregated metrics.
        """
        all_mentions = self._mentions.get(symbol, [])
        source_mentions = [m for m in all_mentions if m.source == source]

        if len(source_mentions) < self.config.min_mentions:
            return SocialSentiment(symbol=symbol, source=source)

        sentiments = np.array(
            [m.sentiment for m in source_mentions], dtype=float
        )

        bullish = int(np.sum(sentiments > 0.1))
        bearish = int(np.sum(sentiments < -0.1))
        total = len(source_mentions)

        # Volume change vs historical average
        volume_change = self._volume_change(symbol, source, total)

        # Spike detection
        is_spike = volume_change >= self.config.spike_threshold

        return SocialSentiment(
            symbol=symbol,
            source=source,
            mentions=total,
            sentiment_score=round(float(np.mean(sentiments)), 4),
            volume_change=round(volume_change, 2),
            bullish_pct=round(bullish / total, 4) if total > 0 else 0.0,
            bearish_pct=round(bearish / total, 4) if total > 0 else 0.0,
            is_spike=is_spike,
        )

    def aggregate(self, symbol: str) -> SocialSentiment:
        """Aggregate sentiment across all sources with weighted scoring.

        Returns:
            Combined SocialSentiment weighted by source config.
        """
        all_mentions = self._mentions.get(symbol, [])
        if not all_mentions:
            return SocialSentiment(
                symbol=symbol, source=SentimentSource.REDDIT
            )

        total_weight = 0.0
        weighted_sentiment = 0.0
        total_mentions = 0
        total_bullish = 0
        total_bearish = 0
        total_counted = 0

        for source in SentimentSource:
            source_mentions = [m for m in all_mentions if m.source == source]
            if len(source_mentions) < self.config.min_mentions:
                continue

            weight = self.config.source_weights.get(source.value, 0.25)
            sentiments = [m.sentiment for m in source_mentions]
            avg_sent = float(np.mean(sentiments))

            weighted_sentiment += weight * avg_sent
            total_weight += weight
            total_mentions += len(source_mentions)

            total_bullish += sum(1 for s in sentiments if s > 0.1)
            total_bearish += sum(1 for s in sentiments if s < -0.1)
            total_counted += len(source_mentions)

        if total_weight == 0:
            return SocialSentiment(
                symbol=symbol, source=SentimentSource.REDDIT
            )

        final_sentiment = weighted_sentiment / total_weight

        return SocialSentiment(
            symbol=symbol,
            source=SentimentSource.REDDIT,  # placeholder for aggregate
            mentions=total_mentions,
            sentiment_score=round(final_sentiment, 4),
            volume_change=0.0,
            bullish_pct=round(total_bullish / total_counted, 4) if total_counted > 0 else 0.0,
            bearish_pct=round(total_bearish / total_counted, 4) if total_counted > 0 else 0.0,
            is_spike=False,
        )

    def _volume_change(
        self, symbol: str, source: SentimentSource, current_count: int
    ) -> float:
        """Compute volume change ratio vs historical average.

        Returns ratio: 2.0 means 2x the historical average.
        """
        all_mentions = self._mentions.get(symbol, [])
        source_mentions = [m for m in all_mentions if m.source == source]

        total = len(source_mentions)
        if total <= current_count:
            return 1.0

        historical_count = total - current_count
        if historical_count == 0:
            return 1.0

        # Simple ratio of current vs average historical
        return current_count / (historical_count / max(1, self.config.sentiment_lookback))

    def get_mentions(
        self, symbol: str, source: Optional[SentimentSource] = None
    ) -> list[SocialMention]:
        mentions = self._mentions.get(symbol, [])
        if source:
            return [m for m in mentions if m.source == source]
        return mentions

    def reset(self) -> None:
        self._mentions.clear()
