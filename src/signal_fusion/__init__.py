"""Autonomous Signal Fusion Agent (PRD-147).

Fuses signals from EMA Cloud, Social Intelligence, Factor Engine,
ML models, Sentiment, Technical, Fundamental, and News sources into
unified trade recommendations with confidence scoring.

Pipeline: collect -> fuse -> recommend -> (optionally execute)
"""

from src.signal_fusion.collector import (
    DEMO_TICKERS,
    RawSignal,
    SignalCollector,
    SignalSource,
    VALID_DIRECTIONS,
)
from src.signal_fusion.fusion import (
    DEFAULT_SOURCE_WEIGHTS,
    FusedSignal,
    FusionConfig,
    SignalFusion,
)
from src.signal_fusion.recommender import (
    Action,
    Recommendation,
    RecommenderConfig,
    TradeRecommender,
    STRONG_BUY_THRESHOLD,
    BUY_THRESHOLD,
    SELL_THRESHOLD,
    STRONG_SELL_THRESHOLD,
)
from src.signal_fusion.agent import (
    AgentConfig,
    AgentState,
    FusionAgent,
)

__all__ = [
    # Collector
    "SignalSource",
    "RawSignal",
    "SignalCollector",
    "DEMO_TICKERS",
    "VALID_DIRECTIONS",
    # Fusion
    "FusionConfig",
    "FusedSignal",
    "SignalFusion",
    "DEFAULT_SOURCE_WEIGHTS",
    # Recommender
    "Action",
    "Recommendation",
    "RecommenderConfig",
    "TradeRecommender",
    "STRONG_BUY_THRESHOLD",
    "BUY_THRESHOLD",
    "SELL_THRESHOLD",
    "STRONG_SELL_THRESHOLD",
    # Agent
    "AgentConfig",
    "AgentState",
    "FusionAgent",
]
