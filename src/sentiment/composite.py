"""Composite Sentiment Score.

Aggregates news, social, insider, analyst, earnings, and
options flow signals into a single composite sentiment factor.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.sentiment.config import CompositeConfig

logger = logging.getLogger(__name__)


@dataclass
class SentimentBreakdown:
    """Breakdown of composite sentiment by source."""

    symbol: str = ""
    news_sentiment: Optional[float] = None
    social_sentiment: Optional[float] = None
    insider_signal: Optional[float] = None
    analyst_revision: Optional[float] = None
    earnings_tone: Optional[float] = None
    options_flow: Optional[float] = None
    composite_score: float = 0.0
    composite_normalized: float = 0.5  # 0-1 range
    sources_available: int = 0
    confidence: str = "low"  # low, medium, high

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "news_sentiment": self.news_sentiment,
            "social_sentiment": self.social_sentiment,
            "insider_signal": self.insider_signal,
            "analyst_revision": self.analyst_revision,
            "earnings_tone": self.earnings_tone,
            "options_flow": self.options_flow,
            "composite_score": self.composite_score,
            "composite_normalized": self.composite_normalized,
            "sources_available": self.sources_available,
            "confidence": self.confidence,
        }


class SentimentComposite:
    """Compute composite sentiment score from multiple sources.

    Aggregates news, social media, insider trading, analyst consensus,
    earnings call, and options flow signals with configurable weights.

    Example:
        composite = SentimentComposite()
        result = composite.compute("AAPL", {
            "news_sentiment": 0.6,
            "social_sentiment": 0.8,
            "insider_signal": 0.3,
        })
    """

    def __init__(self, config: Optional[CompositeConfig] = None):
        self.config = config or CompositeConfig()

    def compute(
        self,
        symbol: str,
        scores: dict[str, Optional[float]],
    ) -> SentimentBreakdown:
        """Compute composite sentiment for a symbol.

        Args:
            symbol: Stock ticker.
            scores: Dict of source_name -> score (-1 to 1).
                    None values are treated as unavailable.

        Returns:
            SentimentBreakdown with composite and per-source scores.
        """
        breakdown = SentimentBreakdown(symbol=symbol)

        # Set individual scores
        breakdown.news_sentiment = scores.get("news_sentiment")
        breakdown.social_sentiment = scores.get("social_sentiment")
        breakdown.insider_signal = scores.get("insider_signal")
        breakdown.analyst_revision = scores.get("analyst_revision")
        breakdown.earnings_tone = scores.get("earnings_tone")
        breakdown.options_flow = scores.get("options_flow")

        # Compute weighted average of available scores
        weighted_sum = 0.0
        weight_total = 0.0
        sources_used = 0

        for source, weight in self.config.weights.items():
            value = scores.get(source)
            if value is not None:
                weighted_sum += weight * value
                weight_total += weight
                sources_used += 1

        breakdown.sources_available = sources_used

        if sources_used < self.config.min_sources_required or weight_total == 0:
            breakdown.composite_score = 0.0
            breakdown.composite_normalized = 0.5
            breakdown.confidence = "low"
            return breakdown

        # Normalize by available weight (so missing sources don't dilute)
        composite = weighted_sum / weight_total
        breakdown.composite_score = float(np.clip(composite, -1.0, 1.0))
        breakdown.composite_normalized = float((breakdown.composite_score + 1) / 2)

        # Confidence based on source coverage
        if sources_used >= 5:
            breakdown.confidence = "high"
        elif sources_used >= 3:
            breakdown.confidence = "medium"
        else:
            breakdown.confidence = "low"

        return breakdown

    def compute_batch(
        self,
        scores_by_symbol: dict[str, dict[str, Optional[float]]],
    ) -> dict[str, SentimentBreakdown]:
        """Compute composite sentiment for multiple symbols.

        Args:
            scores_by_symbol: Dict of symbol -> source scores.

        Returns:
            Dict of symbol -> SentimentBreakdown.
        """
        return {
            symbol: self.compute(symbol, scores)
            for symbol, scores in scores_by_symbol.items()
        }

    def rank_symbols(
        self,
        breakdowns: dict[str, SentimentBreakdown],
    ) -> pd.DataFrame:
        """Rank symbols by composite sentiment.

        Args:
            breakdowns: Dict of symbol -> SentimentBreakdown.

        Returns:
            DataFrame sorted by composite_score descending.
        """
        rows = []
        for symbol, bd in breakdowns.items():
            rows.append({
                "symbol": symbol,
                "composite_score": bd.composite_score,
                "composite_normalized": bd.composite_normalized,
                "confidence": bd.confidence,
                "sources": bd.sources_available,
                "news": bd.news_sentiment,
                "social": bd.social_sentiment,
                "insider": bd.insider_signal,
                "analyst": bd.analyst_revision,
                "earnings": bd.earnings_tone,
                "options": bd.options_flow,
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("composite_score", ascending=False).reset_index(drop=True)
        return df

    def compute_factor_score(
        self,
        breakdowns: dict[str, SentimentBreakdown],
    ) -> pd.Series:
        """Convert composite sentiment to cross-sectional factor score.

        Ranks and normalizes to 0-1 for use in the factor model.

        Args:
            breakdowns: Dict of symbol -> SentimentBreakdown.

        Returns:
            Series of factor scores indexed by symbol.
        """
        scores = {
            symbol: bd.composite_score
            for symbol, bd in breakdowns.items()
            if bd.sources_available >= self.config.min_sources_required
        }

        if not scores:
            return pd.Series(dtype=float)

        series = pd.Series(scores)

        # Cross-sectional rank normalization to 0-1
        ranked = series.rank(pct=True)
        return ranked

    def get_sentiment_regime(
        self,
        breakdowns: dict[str, SentimentBreakdown],
    ) -> dict:
        """Determine overall market sentiment regime.

        Args:
            breakdowns: All symbols' sentiment.

        Returns:
            Dict with regime classification and stats.
        """
        scores = [
            bd.composite_score for bd in breakdowns.values()
            if bd.sources_available >= self.config.min_sources_required
        ]

        if not scores:
            return {"regime": "neutral", "avg_score": 0.0, "breadth": 0.5}

        avg = float(np.mean(scores))
        bullish_pct = float(np.mean([1 if s > 0.1 else 0 for s in scores]))

        if avg > 0.3 and bullish_pct > 0.6:
            regime = "extreme_bullish"
        elif avg > 0.1:
            regime = "bullish"
        elif avg > -0.1:
            regime = "neutral"
        elif avg > -0.3:
            regime = "bearish"
        else:
            regime = "extreme_bearish"

        return {
            "regime": regime,
            "avg_score": avg,
            "breadth": bullish_pct,
            "num_symbols": len(scores),
        }
