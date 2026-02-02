"""Alternative Data Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class DataSource(Enum):
    """Alternative data source types."""
    SATELLITE = "satellite"
    WEB_TRAFFIC = "web_traffic"
    SOCIAL = "social"
    APP_STORE = "app_store"


class SignalQuality(Enum):
    """Signal quality classification."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NOISE = "noise"


class SentimentSource(Enum):
    """Social sentiment data sources."""
    REDDIT = "reddit"
    TWITTER = "twitter"
    STOCKTWITS = "stocktwits"
    NEWS = "news"


class SatelliteType(Enum):
    """Satellite imagery signal types."""
    PARKING_LOT = "parking_lot"
    OIL_STORAGE = "oil_storage"
    SHIPPING = "shipping"
    CONSTRUCTION = "construction"


@dataclass
class SatelliteConfig:
    """Satellite signal analyzer configuration."""
    anomaly_threshold: float = 2.0
    min_observations: int = 5
    lookback_days: int = 90
    trend_min_points: int = 3


@dataclass
class WebTrafficConfig:
    """Web traffic analyzer configuration."""
    growth_window: int = 7
    engagement_bounce_weight: float = 0.4
    engagement_duration_weight: float = 0.6
    momentum_window: int = 14
    significant_growth_pct: float = 10.0


@dataclass
class SocialConfig:
    """Social sentiment aggregator configuration."""
    source_weights: dict[str, float] = field(default_factory=lambda: {
        "reddit": 0.25,
        "twitter": 0.30,
        "stocktwits": 0.25,
        "news": 0.20,
    })
    spike_threshold: float = 2.0
    min_mentions: int = 5
    sentiment_lookback: int = 30


@dataclass
class ScoringConfig:
    """Alternative data scorer configuration."""
    source_weights: dict[str, float] = field(default_factory=lambda: {
        "satellite": 0.25,
        "web_traffic": 0.25,
        "social": 0.30,
        "app_store": 0.20,
    })
    high_quality_threshold: float = 0.7
    medium_quality_threshold: float = 0.4
    low_quality_threshold: float = 0.2
    min_sources: int = 2


@dataclass
class AltDataConfig:
    """Top-level alternative data configuration."""
    satellite: SatelliteConfig = field(default_factory=SatelliteConfig)
    web_traffic: WebTrafficConfig = field(default_factory=WebTrafficConfig)
    social: SocialConfig = field(default_factory=SocialConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)


DEFAULT_SATELLITE_CONFIG = SatelliteConfig()
DEFAULT_WEB_TRAFFIC_CONFIG = WebTrafficConfig()
DEFAULT_SOCIAL_CONFIG = SocialConfig()
DEFAULT_SCORING_CONFIG = ScoringConfig()
DEFAULT_CONFIG = AltDataConfig()
