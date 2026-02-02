"""Event-Driven Signal Generator.

Generates trading signals from earnings, M&A, and corporate action
events with composite multi-event scoring.
"""

import logging
from typing import Optional

import numpy as np

from src.events.config import (
    EventType,
    SignalStrength,
    SignalConfig,
    DEFAULT_EVENT_CONFIG,
)
from src.events.models import (
    EarningsEvent,
    EarningsSummary,
    MergerEvent,
    CorporateAction,
    EventSignal,
    CompositeEventScore,
)

logger = logging.getLogger(__name__)


class EventSignalGenerator:
    """Generates event-driven trading signals."""

    def __init__(self, config: Optional[SignalConfig] = None) -> None:
        self.config = config or DEFAULT_EVENT_CONFIG.signal

    def earnings_signal(
        self, event: EarningsEvent, summary: Optional[EarningsSummary] = None
    ) -> EventSignal:
        """Generate signal from an earnings event.

        Considers surprise magnitude, historical pattern (beat rate),
        and post-earnings drift.

        Args:
            event: The earnings event.
            summary: Optional historical summary for context.

        Returns:
            EventSignal.
        """
        surprise = event.eps_surprise
        abs_surprise = abs(surprise)

        # Base score from surprise magnitude
        score = float(np.tanh(surprise * 5))  # maps to (-1, 1)

        # Adjust for consistency if history available
        if summary and summary.total_reports >= 4:
            if event.is_beat and summary.beat_rate > 0.7:
                score *= 0.8  # discount expected beats
            elif event.is_miss and summary.miss_rate < 0.2:
                score *= 1.3  # amplify unexpected misses

            # Streak bonus
            if abs(summary.streak) >= 3:
                streak_factor = 0.1 * min(abs(summary.streak), 5)
                if summary.streak > 0 and event.is_beat:
                    score += streak_factor
                elif summary.streak < 0 and event.is_miss:
                    score -= streak_factor

        score = max(-1.0, min(1.0, score))

        # Drift adds to confidence
        drift_factor = abs(event.post_drift) if event.post_drift != 0 else abs_surprise * 0.5
        confidence = min(abs_surprise + drift_factor, 1.0)

        direction = "bullish" if score > 0.1 else ("bearish" if score < -0.1 else "neutral")
        strength = self._classify_strength(abs(score))

        return EventSignal(
            symbol=event.symbol,
            event_type=EventType.EARNINGS,
            strength=strength,
            direction=direction,
            score=round(score, 4),
            confidence=round(confidence, 4),
            description=f"EPS surprise {surprise:+.1%}, {event.result.value}",
        )

    def merger_signal(self, arb_result: dict) -> EventSignal:
        """Generate signal from risk arbitrage analysis.

        Args:
            arb_result: Output from MergerAnalyzer.risk_arb_signal().

        Returns:
            EventSignal.
        """
        signal_map = {
            "strong_buy": (0.9, "bullish", SignalStrength.STRONG),
            "buy": (0.6, "bullish", SignalStrength.MODERATE),
            "neutral": (0.0, "neutral", SignalStrength.WEAK),
            "avoid": (-0.5, "bearish", SignalStrength.MODERATE),
            "none": (0.0, "neutral", SignalStrength.NONE),
        }

        sig = arb_result.get("signal", "none")
        score, direction, strength = signal_map.get(sig, (0.0, "neutral", SignalStrength.NONE))

        confidence = arb_result.get("probability", 0.0)
        target = arb_result.get("target", "")

        return EventSignal(
            symbol=target,
            event_type=EventType.MERGER,
            strength=strength,
            direction=direction,
            score=round(score, 4),
            confidence=round(confidence, 4),
            description=f"Arb spread {arb_result.get('spread', 0):.1%}, prob {confidence:.0%}",
        )

    def corporate_signal(self, action: CorporateAction) -> EventSignal:
        """Generate signal from a corporate action.

        Args:
            action: Corporate action event.

        Returns:
            EventSignal.
        """
        score = 0.0
        direction = "neutral"
        confidence = 0.3

        if action.action_type == EventType.DIVIDEND:
            if action.amount > 0:
                score = 0.3
                direction = "bullish"
                confidence = 0.5

        elif action.action_type == EventType.BUYBACK:
            if action.amount > 0:
                score = 0.4
                direction = "bullish"
                confidence = 0.5

        elif action.action_type == EventType.SPLIT:
            score = 0.2
            direction = "bullish"
            confidence = 0.3

        elif action.action_type == EventType.SPINOFF:
            score = 0.1
            direction = "neutral"
            confidence = 0.2

        strength = self._classify_strength(abs(score))

        return EventSignal(
            symbol=action.symbol,
            event_type=action.action_type,
            strength=strength,
            direction=direction,
            score=round(score, 4),
            confidence=round(confidence, 4),
            description=f"{action.action_type.value}: amount={action.amount}",
        )

    def composite(
        self, symbol: str, signals: list[EventSignal]
    ) -> CompositeEventScore:
        """Compute composite score from multiple event signals.

        Weights signals by event type and confidence.

        Args:
            symbol: Stock symbol.
            signals: List of event signals.

        Returns:
            CompositeEventScore.
        """
        if not signals:
            return CompositeEventScore(symbol=symbol)

        weight_map = {
            EventType.EARNINGS: self.config.earnings_weight,
            EventType.MERGER: self.config.merger_weight,
            EventType.DIVIDEND: self.config.corporate_weight,
            EventType.BUYBACK: self.config.corporate_weight,
            EventType.SPLIT: self.config.corporate_weight,
            EventType.SPINOFF: self.config.corporate_weight,
        }

        earnings_scores = []
        merger_scores = []
        corporate_scores = []

        total_weight = 0.0
        weighted_score = 0.0

        for sig in signals:
            base_weight = weight_map.get(sig.event_type, 0.25)
            eff_weight = base_weight * sig.confidence
            weighted_score += eff_weight * sig.score
            total_weight += eff_weight

            if sig.event_type == EventType.EARNINGS:
                earnings_scores.append(sig.score)
            elif sig.event_type == EventType.MERGER:
                merger_scores.append(sig.score)
            else:
                corporate_scores.append(sig.score)

        composite_val = weighted_score / total_weight if total_weight > 0 else 0.0
        composite_val = max(-1.0, min(1.0, composite_val))

        direction = "bullish" if composite_val > 0.1 else (
            "bearish" if composite_val < -0.1 else "neutral"
        )
        strength = self._classify_strength(abs(composite_val))

        return CompositeEventScore(
            symbol=symbol,
            earnings_score=float(np.mean(earnings_scores)) if earnings_scores else 0.0,
            merger_score=float(np.mean(merger_scores)) if merger_scores else 0.0,
            corporate_score=float(np.mean(corporate_scores)) if corporate_scores else 0.0,
            composite=round(composite_val, 4),
            n_signals=len(signals),
            strength=strength,
            direction=direction,
            signals=signals,
        )

    def _classify_strength(self, abs_score: float) -> SignalStrength:
        """Classify signal strength from absolute score."""
        if abs_score >= self.config.strong_threshold:
            return SignalStrength.STRONG
        elif abs_score >= self.config.moderate_threshold:
            return SignalStrength.MODERATE
        elif abs_score >= self.config.weak_threshold:
            return SignalStrength.WEAK
        return SignalStrength.NONE
