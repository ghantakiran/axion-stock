"""Alternative Data Scorer.

Computes composite alternative data scores from multiple sources,
assesses signal quality, and provides confidence-weighted scoring.
"""

import logging
from typing import Optional

import numpy as np

from src.altdata.config import (
    DataSource,
    SignalQuality,
    ScoringConfig,
    DEFAULT_SCORING_CONFIG,
)
from src.altdata.models import (
    SatelliteSignal,
    WebTrafficSnapshot,
    SocialSentiment,
    AltDataSignal,
    AltDataComposite,
)

logger = logging.getLogger(__name__)


class AltDataScorer:
    """Scores and combines alternative data signals."""

    def __init__(self, config: Optional[ScoringConfig] = None) -> None:
        self.config = config or DEFAULT_SCORING_CONFIG

    def score_satellite(
        self, signals: list[SatelliteSignal]
    ) -> AltDataSignal:
        """Score satellite signals into a single signal."""
        if not signals:
            return AltDataSignal(
                symbol="", source=DataSource.SATELLITE,
            )

        symbol = signals[0].symbol
        z_scores = [s.z_score for s in signals]
        avg_z = float(np.mean(z_scores))
        strength = float(np.mean([abs(z) for z in z_scores]))

        # Quality based on number of signals and consistency
        quality = self._assess_quality(strength, len(signals))
        confidence = min(len(signals) / 4.0, 1.0) * min(strength / 2.0, 1.0)

        return AltDataSignal(
            symbol=symbol,
            source=DataSource.SATELLITE,
            signal_strength=round(strength, 4),
            quality=quality,
            confidence=round(confidence, 4),
            raw_score=round(avg_z, 4),
        )

    def score_web_traffic(
        self, snapshot: WebTrafficSnapshot
    ) -> AltDataSignal:
        """Score web traffic into a signal."""
        if not snapshot.domain:
            return AltDataSignal(
                symbol=snapshot.symbol, source=DataSource.WEB_TRAFFIC,
            )

        # Combine growth and engagement into a score
        growth_signal = np.tanh(snapshot.growth_rate / 50.0)
        engagement_signal = snapshot.engagement_score * 2 - 1  # map 0-1 to -1,1

        raw = 0.6 * growth_signal + 0.4 * engagement_signal
        strength = abs(raw)

        quality = self._assess_quality(strength, 1)
        confidence = min(strength / 0.5, 1.0) * snapshot.engagement_score

        return AltDataSignal(
            symbol=snapshot.symbol,
            source=DataSource.WEB_TRAFFIC,
            signal_strength=round(strength, 4),
            quality=quality,
            confidence=round(confidence, 4),
            raw_score=round(float(raw), 4),
        )

    def score_social(self, sentiment: SocialSentiment) -> AltDataSignal:
        """Score social sentiment into a signal."""
        if sentiment.mentions == 0:
            return AltDataSignal(
                symbol=sentiment.symbol, source=DataSource.SOCIAL,
            )

        raw = sentiment.sentiment_score
        strength = abs(raw)

        # Boost strength if volume spike
        if sentiment.is_spike:
            strength = min(strength * 1.5, 1.0)

        quality = self._assess_quality(strength, 1)

        # Confidence from mention count and sentiment consistency
        mention_factor = min(sentiment.mentions / 50.0, 1.0)
        consistency = max(sentiment.bullish_pct, sentiment.bearish_pct)
        confidence = mention_factor * consistency

        return AltDataSignal(
            symbol=sentiment.symbol,
            source=DataSource.SOCIAL,
            signal_strength=round(strength, 4),
            quality=quality,
            confidence=round(confidence, 4),
            raw_score=round(raw, 4),
        )

    def composite(
        self,
        symbol: str,
        satellite_signal: Optional[AltDataSignal] = None,
        web_signal: Optional[AltDataSignal] = None,
        social_signal: Optional[AltDataSignal] = None,
        app_signal: Optional[AltDataSignal] = None,
    ) -> AltDataComposite:
        """Compute composite score from all available signals.

        Weights signals by source config and confidence.
        """
        signals: list[AltDataSignal] = []
        scores: dict[str, float] = {}

        for key, signal in [
            ("satellite", satellite_signal),
            ("web_traffic", web_signal),
            ("social", social_signal),
            ("app_store", app_signal),
        ]:
            if signal and signal.signal_strength > 0:
                signals.append(signal)
                scores[key] = signal.raw_score

        n_sources = len(signals)

        if n_sources == 0:
            return AltDataComposite(symbol=symbol)

        # Weighted composite
        total_weight = 0.0
        weighted_score = 0.0

        for key, score in scores.items():
            weight = self.config.source_weights.get(key, 0.25)
            # Confidence-adjust the weight
            matching = [s for s in signals if s.source.value == key]
            if matching:
                weight *= matching[0].confidence
            weighted_score += weight * score
            total_weight += weight

        composite_val = weighted_score / total_weight if total_weight > 0 else 0.0

        # Overall quality
        avg_strength = float(np.mean([s.signal_strength for s in signals]))
        quality = self._assess_quality(avg_strength, n_sources)

        # Overall confidence
        avg_confidence = float(np.mean([s.confidence for s in signals]))
        source_coverage = n_sources / 4.0
        confidence = avg_confidence * source_coverage

        return AltDataComposite(
            symbol=symbol,
            satellite_score=scores.get("satellite", 0.0),
            web_score=scores.get("web_traffic", 0.0),
            social_score=scores.get("social", 0.0),
            app_score=scores.get("app_store", 0.0),
            composite=round(composite_val, 4),
            n_sources=n_sources,
            quality=quality,
            confidence=round(confidence, 4),
            signals=signals,
        )

    def _assess_quality(
        self, strength: float, n_signals: int
    ) -> SignalQuality:
        """Assess signal quality from strength and coverage."""
        adjusted = strength * min(n_signals / 2.0, 1.0)

        if adjusted >= self.config.high_quality_threshold:
            return SignalQuality.HIGH
        elif adjusted >= self.config.medium_quality_threshold:
            return SignalQuality.MEDIUM
        elif adjusted >= self.config.low_quality_threshold:
            return SignalQuality.LOW
        return SignalQuality.NOISE
