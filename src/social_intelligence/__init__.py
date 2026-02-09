"""Social Signal Intelligence (PRD-141).

Advanced analytics layer on top of Social Signal Crawler (PRD-140).
Produces actionable trading signals from social media data using
signal scoring, volume anomaly detection, influencer tracking,
and cross-platform correlation.

Example:
    from src.social_intelligence import (
        SignalScorer, VolumeAnalyzer, InfluencerTracker,
        CrossPlatformCorrelator, SocialSignalGenerator,
    )

    # Score posts
    scorer = SignalScorer()
    scored = scorer.score_posts(posts)

    # Detect anomalies
    analyzer = VolumeAnalyzer()
    anomalies = analyzer.detect_anomalies(mention_history)

    # Generate trading signals
    generator = SocialSignalGenerator()
    signals = generator.generate(scored, anomalies)
"""

from src.social_intelligence.scorer import (
    SignalScorer,
    ScorerConfig,
    ScoredTicker,
    SignalStrength,
)
from src.social_intelligence.volume import (
    VolumeAnalyzer,
    VolumeConfig,
    VolumeAnomaly,
    MentionTimeseries,
)
from src.social_intelligence.influencer import (
    InfluencerTracker,
    InfluencerConfig,
    InfluencerProfile,
    InfluencerSignal,
)
from src.social_intelligence.correlator import (
    CrossPlatformCorrelator,
    CorrelatorConfig,
    PlatformConsensus,
    CorrelationResult,
)
from src.social_intelligence.generator import (
    SocialSignalGenerator,
    GeneratorConfig,
    SocialTradingSignal,
    SignalAction,
    IntelligenceReport,
)

__all__ = [
    # Scorer
    "SignalScorer",
    "ScorerConfig",
    "ScoredTicker",
    "SignalStrength",
    # Volume
    "VolumeAnalyzer",
    "VolumeConfig",
    "VolumeAnomaly",
    "MentionTimeseries",
    # Influencer
    "InfluencerTracker",
    "InfluencerConfig",
    "InfluencerProfile",
    "InfluencerSignal",
    # Correlator
    "CrossPlatformCorrelator",
    "CorrelatorConfig",
    "PlatformConsensus",
    "CorrelationResult",
    # Generator
    "SocialSignalGenerator",
    "GeneratorConfig",
    "SocialTradingSignal",
    "SignalAction",
    "IntelligenceReport",
]
