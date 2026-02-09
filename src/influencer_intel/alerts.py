"""Influencer Alert Bridge.

Generates alerts when high-impact influencers post about tickers,
change sentiment direction, or show coordinated activity.
"""

import enum
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class AlertPriority(enum.Enum):
    """Alert priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AlertConfig:
    """Configuration for influencer alerts."""

    min_tier_for_alert: str = "micro"  # mega, macro, micro, nano
    min_impact_score: float = 0.3
    sentiment_reversal_threshold: float = 0.5  # Score swing to trigger
    coordination_alert_threshold: float = 0.7
    max_alerts_per_hour: int = 50


@dataclass
class InfluencerAlert:
    """An alert triggered by influencer activity."""

    alert_id: str = ""
    alert_type: str = ""  # new_post, sentiment_reversal, coordination, mega_mention
    priority: AlertPriority = AlertPriority.MEDIUM
    author_id: str = ""
    platform: str = ""
    tier: str = ""
    ticker: str = ""
    sentiment: float = 0.0
    previous_sentiment: float = 0.0
    impact_score: float = 0.0
    message: str = ""
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type,
            "priority": self.priority.value,
            "author_id": self.author_id,
            "platform": self.platform,
            "tier": self.tier,
            "ticker": self.ticker,
            "sentiment": round(self.sentiment, 3),
            "impact_score": round(self.impact_score, 3),
            "message": self.message,
        }


# Tier hierarchy for comparison
_TIER_RANK = {"mega": 4, "macro": 3, "micro": 2, "nano": 1}


class InfluencerAlertBridge:
    """Generate alerts from influencer activity.

    Monitors influencer signals and generates alerts for:
    - Mega/macro influencer new posts
    - Sentiment direction reversals
    - Coordinated multi-influencer activity
    - High-confidence ticker mentions

    Example::

        bridge = InfluencerAlertBridge()
        alerts = bridge.check_signals(signals, profiles)
        for alert in alerts:
            print(f"{alert.priority.value}: {alert.message}")
    """

    def __init__(self, config: Optional[AlertConfig] = None):
        self.config = config or AlertConfig()
        self._alert_counter = 0
        self._alerts: list[InfluencerAlert] = []
        self._last_sentiments: dict[str, float] = {}  # author_key → last sentiment

    def check_signals(
        self,
        signals: list,
        profiles: Optional[dict] = None,
    ) -> list[InfluencerAlert]:
        """Check influencer signals and generate alerts.

        Args:
            signals: List of InfluencerSignal-like objects.
            profiles: Optional dict of author_key → InfluencerProfile.

        Returns:
            List of new alerts generated.
        """
        new_alerts = []
        min_tier_rank = _TIER_RANK.get(self.config.min_tier_for_alert, 2)

        for signal in signals:
            tier = getattr(signal, "tier", "nano")
            tier_rank = _TIER_RANK.get(tier, 1)
            impact = getattr(signal, "impact_score", 0.0)
            author = getattr(signal, "author_id", "")
            platform = getattr(signal, "platform", "")
            ticker = getattr(signal, "symbol", "")
            sentiment = getattr(signal, "sentiment", 0.0)

            if tier_rank < min_tier_rank and impact < self.config.min_impact_score:
                continue

            key = f"{platform}:{author}"

            # Check for mega/macro mention
            if tier_rank >= 3:  # macro or mega
                priority = AlertPriority.HIGH if tier == "mega" else AlertPriority.MEDIUM
                alert = self._create_alert(
                    alert_type="mega_mention",
                    priority=priority,
                    author_id=author,
                    platform=platform,
                    tier=tier,
                    ticker=ticker,
                    sentiment=sentiment,
                    impact_score=impact,
                    message=f"{tier.title()} influencer {author} posted about {ticker} (sentiment: {sentiment:+.2f})",
                )
                new_alerts.append(alert)

            # Check for sentiment reversal
            prev_sentiment = self._last_sentiments.get(key, 0.0)
            swing = abs(sentiment - prev_sentiment)
            if swing >= self.config.sentiment_reversal_threshold and prev_sentiment != 0.0:
                alert = self._create_alert(
                    alert_type="sentiment_reversal",
                    priority=AlertPriority.HIGH,
                    author_id=author,
                    platform=platform,
                    tier=tier,
                    ticker=ticker,
                    sentiment=sentiment,
                    previous_sentiment=prev_sentiment,
                    impact_score=impact,
                    message=f"Sentiment reversal by {author}: {prev_sentiment:+.2f} → {sentiment:+.2f} on {ticker}",
                )
                new_alerts.append(alert)

            self._last_sentiments[key] = sentiment

        self._alerts.extend(new_alerts)
        return new_alerts

    def check_coordination(
        self,
        ticker: str,
        signals: list,
        time_window_hours: float = 4.0,
    ) -> Optional[InfluencerAlert]:
        """Check for coordinated influencer activity on a ticker.

        Args:
            ticker: Ticker to check.
            signals: Recent signals mentioning this ticker.
            time_window_hours: Time window for coordination check.

        Returns:
            Alert if coordination detected, else None.
        """
        # Filter signals for this ticker
        ticker_signals = [
            s for s in signals
            if getattr(s, "symbol", "") == ticker
        ]

        if len(ticker_signals) < 3:
            return None

        # Check if multiple influencers mention same direction
        directions = [getattr(s, "direction", "neutral") for s in ticker_signals]
        bullish_count = sum(1 for d in directions if d == "bullish")
        bearish_count = sum(1 for d in directions if d == "bearish")

        total = len(ticker_signals)
        consensus_ratio = max(bullish_count, bearish_count) / total

        if consensus_ratio >= self.config.coordination_alert_threshold:
            dominant = "bullish" if bullish_count > bearish_count else "bearish"
            alert = self._create_alert(
                alert_type="coordination",
                priority=AlertPriority.CRITICAL,
                ticker=ticker,
                sentiment=1.0 if dominant == "bullish" else -1.0,
                impact_score=consensus_ratio,
                message=f"Coordinated {dominant} activity: {total} influencers on {ticker} ({consensus_ratio:.0%} consensus)",
            )
            self._alerts.append(alert)
            return alert

        return None

    def get_recent_alerts(self, n: int = 20) -> list[InfluencerAlert]:
        """Get most recent alerts."""
        return self._alerts[-n:]

    @property
    def alert_count(self) -> int:
        return len(self._alerts)

    def clear(self):
        """Reset alert state."""
        self._alerts.clear()
        self._last_sentiments.clear()
        self._alert_counter = 0

    def _create_alert(self, **kwargs) -> InfluencerAlert:
        """Create a new alert with auto-incrementing ID."""
        self._alert_counter += 1
        return InfluencerAlert(
            alert_id=f"inf_alert_{self._alert_counter}",
            created_at=datetime.now(timezone.utc),
            **kwargs,
        )
