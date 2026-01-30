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
]
