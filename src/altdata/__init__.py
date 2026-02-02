"""Alternative Data Module.

Satellite imagery signals, web traffic analytics,
social sentiment aggregation, and composite alt-data scoring.

Example:
    from src.altdata import SatelliteAnalyzer, AltDataScorer

    sat = SatelliteAnalyzer()
    sat.add_observation("WMT", SatelliteType.PARKING_LOT, 850)
    signal = sat.analyze("WMT", SatelliteType.PARKING_LOT)

    scorer = AltDataScorer()
    sat_signal = scorer.score_satellite([signal])
    composite = scorer.composite("WMT", satellite_signal=sat_signal)
"""

from src.altdata.config import (
    DataSource,
    SignalQuality,
    SentimentSource,
    SatelliteType,
    SatelliteConfig,
    WebTrafficConfig,
    SocialConfig,
    ScoringConfig,
    AltDataConfig,
    DEFAULT_SATELLITE_CONFIG,
    DEFAULT_WEB_TRAFFIC_CONFIG,
    DEFAULT_SOCIAL_CONFIG,
    DEFAULT_SCORING_CONFIG,
    DEFAULT_CONFIG,
)

from src.altdata.models import (
    SatelliteSignal,
    WebTrafficSnapshot,
    SocialMention,
    SocialSentiment,
    AltDataSignal,
    AltDataComposite,
)

from src.altdata.satellite import SatelliteAnalyzer
from src.altdata.webtraffic import WebTrafficAnalyzer
from src.altdata.social import SocialSentimentAggregator
from src.altdata.scoring import AltDataScorer

__all__ = [
    # Config
    "DataSource",
    "SignalQuality",
    "SentimentSource",
    "SatelliteType",
    "SatelliteConfig",
    "WebTrafficConfig",
    "SocialConfig",
    "ScoringConfig",
    "AltDataConfig",
    "DEFAULT_SATELLITE_CONFIG",
    "DEFAULT_WEB_TRAFFIC_CONFIG",
    "DEFAULT_SOCIAL_CONFIG",
    "DEFAULT_SCORING_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "SatelliteSignal",
    "WebTrafficSnapshot",
    "SocialMention",
    "SocialSentiment",
    "AltDataSignal",
    "AltDataComposite",
    # Components
    "SatelliteAnalyzer",
    "WebTrafficAnalyzer",
    "SocialSentimentAggregator",
    "AltDataScorer",
]
