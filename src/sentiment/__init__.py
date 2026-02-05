"""Social & Sentiment Intelligence Module.

Provides news sentiment analysis, social media monitoring,
insider trading signals, analyst consensus tracking,
earnings call NLP, and composite sentiment scoring.
"""

from src.sentiment.config import (
    SentimentConfig,
    NewsSentimentConfig,
    SocialMediaConfig,
    InsiderConfig,
    AnalystConfig,
    EarningsNLPConfig,
    CompositeConfig,
)
from src.sentiment.news import (
    NewsSentimentEngine,
    SentimentScore,
    Article,
)
from src.sentiment.social import (
    SocialMediaMonitor,
    TickerMention,
    SocialPost,
    TrendingAlert,
    SocialSentimentSummary,
)
from src.sentiment.insider import (
    InsiderTracker,
    InsiderFiling,
    InsiderReport,
)
from src.sentiment.analyst import (
    AnalystConsensusTracker,
    AnalystRating,
    EstimateRevision,
    ConsensusReport,
)
from src.sentiment.earnings import (
    EarningsCallAnalyzer,
    EarningsTranscript,
    CallAnalysis,
)
from src.sentiment.composite import (
    SentimentComposite,
    SentimentBreakdown,
)
from src.sentiment.decay_weighting import (
    SentimentObservation,
    DecayedScore,
    DecayProfile,
    DecayConfig,
    DecayWeightingEngine,
)
from src.sentiment.fusion import (
    SourceSignal,
    FusionResult,
    SourceReliability,
    FusionComparison,
    SentimentFusionEngine,
)
from src.sentiment.consensus import (
    SourceVote,
    ConsensusResult,
    ConsensusShift,
    MarketConsensus,
    ConsensusScorer,
)
from src.sentiment.momentum import (
    SentimentSnapshot,
    MomentumResult,
    TrendReversal,
    MomentumSummary,
    SentimentMomentumTracker,
)

__all__ = [
    # Config
    "SentimentConfig",
    "NewsSentimentConfig",
    "SocialMediaConfig",
    "InsiderConfig",
    "AnalystConfig",
    "EarningsNLPConfig",
    "CompositeConfig",
    # News
    "NewsSentimentEngine",
    "SentimentScore",
    "Article",
    # Social
    "SocialMediaMonitor",
    "TickerMention",
    "SocialPost",
    "TrendingAlert",
    "SocialSentimentSummary",
    # Insider
    "InsiderTracker",
    "InsiderFiling",
    "InsiderReport",
    # Analyst
    "AnalystConsensusTracker",
    "AnalystRating",
    "EstimateRevision",
    "ConsensusReport",
    # Earnings
    "EarningsCallAnalyzer",
    "EarningsTranscript",
    "CallAnalysis",
    # Composite
    "SentimentComposite",
    "SentimentBreakdown",
    # Decay Weighting (PRD-63)
    "SentimentObservation",
    "DecayedScore",
    "DecayProfile",
    "DecayConfig",
    "DecayWeightingEngine",
    # Fusion (PRD-63)
    "SourceSignal",
    "FusionResult",
    "SourceReliability",
    "FusionComparison",
    "SentimentFusionEngine",
    # Consensus (PRD-63)
    "SourceVote",
    "ConsensusResult",
    "ConsensusShift",
    "MarketConsensus",
    "ConsensusScorer",
    # Momentum (PRD-63)
    "SentimentSnapshot",
    "MomentumResult",
    "TrendReversal",
    "MomentumSummary",
    "SentimentMomentumTracker",
]
