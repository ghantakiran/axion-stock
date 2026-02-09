"""LLM-Powered Sentiment Engine (PRD-151).

Uses multi-model AI providers (Claude, GPT, Gemini, DeepSeek, Ollama)
for nuanced financial sentiment analysis with aspect-level extraction,
entity resolution, and predictive momentum scoring.
"""

from src.llm_sentiment.analyzer import (
    LLMSentimentAnalyzer,
    AnalyzerConfig,
    LLMSentimentResult,
    SentimentAspect,
)
from src.llm_sentiment.aspects import (
    AspectExtractor,
    AspectConfig,
    AspectCategory,
    AspectReport,
)
from src.llm_sentiment.entity import (
    EntityResolver,
    EntityConfig,
    EntitySentiment,
    EntityType,
    EntityReport,
)
from src.llm_sentiment.predictor import (
    SentimentPredictor,
    PredictorConfig,
    SentimentForecast,
    ForecastHorizon,
    PredictionReport,
)

__all__ = [
    # Analyzer
    "LLMSentimentAnalyzer",
    "AnalyzerConfig",
    "LLMSentimentResult",
    "SentimentAspect",
    # Aspects
    "AspectExtractor",
    "AspectConfig",
    "AspectCategory",
    "AspectReport",
    # Entity
    "EntityResolver",
    "EntityConfig",
    "EntitySentiment",
    "EntityType",
    "EntityReport",
    # Predictor
    "SentimentPredictor",
    "PredictorConfig",
    "SentimentForecast",
    "ForecastHorizon",
    "PredictionReport",
]
