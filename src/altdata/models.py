"""Alternative Data Models."""

from dataclasses import dataclass, field
from datetime import datetime

from src.altdata.config import (
    DataSource,
    SignalQuality,
    SentimentSource,
    SatelliteType,
)


@dataclass
class SatelliteSignal:
    """Satellite observation signal."""
    symbol: str
    satellite_type: SatelliteType
    raw_value: float
    normalized_value: float = 0.0
    z_score: float = 0.0
    is_anomaly: bool = False
    trend: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def signal_strength(self) -> float:
        """Absolute z-score as signal strength."""
        return abs(self.z_score)

    @property
    def direction(self) -> str:
        """Signal direction based on z-score."""
        if self.z_score > 0.5:
            return "bullish"
        elif self.z_score < -0.5:
            return "bearish"
        return "neutral"


@dataclass
class WebTrafficSnapshot:
    """Point-in-time web traffic metrics."""
    symbol: str
    domain: str
    visits: int = 0
    unique_visitors: int = 0
    bounce_rate: float = 0.0
    avg_duration: float = 0.0
    growth_rate: float = 0.0
    engagement_score: float = 0.0
    momentum: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def conversion_proxy(self) -> float:
        """Proxy for conversion using engagement metrics."""
        if self.bounce_rate >= 1.0:
            return 0.0
        return (1.0 - self.bounce_rate) * min(self.avg_duration / 300.0, 1.0)

    @property
    def is_growing(self) -> bool:
        return self.growth_rate > 0


@dataclass
class SocialMention:
    """Individual social media mention."""
    symbol: str
    source: SentimentSource
    sentiment: float  # -1.0 to 1.0
    text: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_bullish(self) -> bool:
        return self.sentiment > 0.1

    @property
    def is_bearish(self) -> bool:
        return self.sentiment < -0.1


@dataclass
class SocialSentiment:
    """Aggregated social sentiment for a symbol."""
    symbol: str
    source: SentimentSource
    mentions: int = 0
    sentiment_score: float = 0.0
    volume_change: float = 0.0
    bullish_pct: float = 0.0
    bearish_pct: float = 0.0
    is_spike: bool = False

    @property
    def neutral_pct(self) -> float:
        return max(0.0, 1.0 - self.bullish_pct - self.bearish_pct)

    @property
    def net_sentiment(self) -> float:
        return self.bullish_pct - self.bearish_pct


@dataclass
class AltDataSignal:
    """Single-source scored alternative data signal."""
    symbol: str
    source: DataSource
    signal_strength: float = 0.0
    quality: SignalQuality = SignalQuality.NOISE
    confidence: float = 0.0
    raw_score: float = 0.0

    @property
    def is_actionable(self) -> bool:
        return self.quality in (SignalQuality.HIGH, SignalQuality.MEDIUM)


@dataclass
class AltDataComposite:
    """Multi-source composite alternative data score."""
    symbol: str
    satellite_score: float = 0.0
    web_score: float = 0.0
    social_score: float = 0.0
    app_score: float = 0.0
    composite: float = 0.0
    n_sources: int = 0
    quality: SignalQuality = SignalQuality.NOISE
    confidence: float = 0.0
    signals: list[AltDataSignal] = field(default_factory=list)

    @property
    def has_consensus(self) -> bool:
        """True if majority of signals agree on direction."""
        if not self.signals:
            return False
        positive = sum(1 for s in self.signals if s.raw_score > 0)
        negative = sum(1 for s in self.signals if s.raw_score < 0)
        total = len(self.signals)
        return max(positive, negative) / total > 0.6 if total > 0 else False
