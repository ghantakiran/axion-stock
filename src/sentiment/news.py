"""News Sentiment Engine.

NLP-based sentiment analysis for financial news articles.
Uses FinBERT when available, falls back to keyword-based scoring.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

from src.sentiment.config import NewsSentimentConfig

logger = logging.getLogger(__name__)

# Try importing FinBERT / transformers
try:
    from transformers import pipeline as hf_pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


# Common financial ticker patterns
_TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b')
_TICKER_WORD_PATTERN = re.compile(r'\b([A-Z]{2,5})\b')

# Well-known tickers for disambiguation
_COMMON_TICKERS = {
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "NVDA",
    "JPM", "V", "JNJ", "UNH", "HD", "PG", "MA", "DIS", "NFLX", "PYPL",
    "INTC", "AMD", "CRM", "ADBE", "CSCO", "ORCL", "IBM", "QCOM",
    "BA", "CAT", "GS", "WMT", "KO", "PEP", "MRK", "PFE", "ABBV",
    "XOM", "CVX", "COP", "SLB", "BRK", "SPY", "QQQ", "IWM", "DIA",
}

# Common English words to exclude from ticker matching
_EXCLUDED_WORDS = {
    "CEO", "CFO", "CTO", "COO", "IPO", "ETF", "SEC", "FDA", "GDP",
    "EPS", "PE", "AI", "US", "UK", "EU", "CEO", "NYSE", "IMF",
    "API", "IT", "IS", "AT", "ON", "OR", "AN", "AS", "BE", "BY",
    "DO", "GO", "IF", "IN", "NO", "OF", "SO", "TO", "UP", "WE",
    "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN",
    "HER", "WAS", "ONE", "OUR", "OUT", "HAS", "HIS", "HOW", "NEW",
}

# Keyword-based sentiment fallback
_POSITIVE_KEYWORDS = {
    "beat", "beats", "exceeded", "record", "surge", "surges", "rally",
    "rallied", "growth", "strong", "upgrade", "upgraded", "outperform",
    "buy", "bullish", "positive", "gain", "gains", "profit", "revenue",
    "innovation", "breakthrough", "expansion", "optimistic", "confidence",
    "momentum", "recovery", "rebound", "dividend", "raised", "boost",
}

_NEGATIVE_KEYWORDS = {
    "miss", "misses", "missed", "decline", "declined", "loss", "losses",
    "sell", "selloff", "crash", "plunge", "plunged", "downgrade",
    "downgraded", "underperform", "bearish", "negative", "weak",
    "concern", "risk", "warning", "layoff", "layoffs", "recession",
    "default", "fraud", "investigation", "lawsuit", "penalty", "fine",
    "cut", "slash", "slashed", "bankruptcy", "restructuring",
}


@dataclass
class Article:
    """News article data."""

    title: str = ""
    summary: str = ""
    source: str = "unknown"
    url: str = ""
    published_at: str = ""
    symbols: list = field(default_factory=list)


@dataclass
class SentimentScore:
    """Scored sentiment result for an article."""

    sentiment: str = "neutral"  # positive, negative, neutral
    score: float = 0.0  # -1 to +1
    confidence: float = 0.0
    symbols: list = field(default_factory=list)
    topic: str = "general"
    source: str = "unknown"
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "sentiment": self.sentiment,
            "score": self.score,
            "confidence": self.confidence,
            "symbols": self.symbols,
            "topic": self.topic,
            "source": self.source,
            "timestamp": self.timestamp,
        }


class NewsSentimentEngine:
    """NLP-based news sentiment analysis.

    Uses FinBERT for finance-specific sentiment when available,
    falls back to keyword-based scoring otherwise.

    Example:
        engine = NewsSentimentEngine()
        score = engine.score_article(article)
        agg = engine.aggregate_sentiment(scores, window_hours=24)
    """

    def __init__(self, config: Optional[NewsSentimentConfig] = None):
        self.config = config or NewsSentimentConfig()
        self._model = None
        self._model_loaded = False

    def _load_model(self):
        """Lazy-load the NLP model."""
        if self._model_loaded:
            return

        if TRANSFORMERS_AVAILABLE:
            try:
                self._model = hf_pipeline(
                    "sentiment-analysis",
                    model="ProsusAI/finbert",
                    truncation=True,
                )
                logger.info("FinBERT model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load FinBERT: {e}. Using keyword fallback.")
                self._model = None

        self._model_loaded = True

    def score_article(self, article: Article) -> SentimentScore:
        """Score sentiment of a news article.

        Args:
            article: Article with title and summary.

        Returns:
            SentimentScore with sentiment label and numeric score.
        """
        text = f"{article.title}. {article.summary}".strip()
        if not text or text == ".":
            return SentimentScore(
                sentiment="neutral", score=0.0, confidence=0.0,
                symbols=article.symbols, source=article.source,
                timestamp=article.published_at,
            )

        # Extract tickers from text
        symbols = article.symbols or self.extract_tickers(text)

        # Classify topic
        topic = self.classify_topic(text)

        # Score sentiment
        self._load_model()

        if self._model is not None:
            score_result = self._score_with_model(text)
        else:
            score_result = self._score_with_keywords(text)

        return SentimentScore(
            sentiment=score_result["label"],
            score=score_result["score"],
            confidence=score_result["confidence"],
            symbols=symbols,
            topic=topic,
            source=article.source,
            timestamp=article.published_at,
        )

    def score_text(self, text: str) -> dict:
        """Score raw text sentiment.

        Args:
            text: Text to analyze.

        Returns:
            Dict with label, score (-1 to 1), confidence.
        """
        if not text:
            return {"label": "neutral", "score": 0.0, "confidence": 0.0}

        self._load_model()

        if self._model is not None:
            return self._score_with_model(text)
        return self._score_with_keywords(text)

    def aggregate_sentiment(
        self,
        scores: list[SentimentScore],
        window_hours: Optional[int] = None,
    ) -> float:
        """Compute time-decay weighted aggregate sentiment.

        Args:
            scores: List of sentiment scores.
            window_hours: Only include scores within this window.

        Returns:
            Aggregate sentiment score (-1 to 1).
        """
        if not scores:
            return 0.0

        window_hours = window_hours or self.config.default_window_hours
        now = datetime.now()

        filtered = []
        for s in scores:
            if s.timestamp:
                try:
                    ts = datetime.fromisoformat(s.timestamp)
                    if (now - ts).total_seconds() > window_hours * 3600:
                        continue
                except (ValueError, TypeError):
                    pass
            filtered.append(s)

        if not filtered:
            return 0.0

        # Time-decay weights
        time_weights = np.exp(
            -self.config.time_decay_rate * np.arange(len(filtered))
        )

        # Source credibility weights
        source_weights = np.array([
            self.config.source_credibility.get(s.source, 0.5)
            for s in filtered
        ])

        final_weights = time_weights * source_weights
        values = np.array([s.score for s in filtered])

        if final_weights.sum() == 0:
            return 0.0

        return float(np.average(values, weights=final_weights))

    def extract_tickers(self, text: str) -> list[str]:
        """Extract stock ticker symbols from text.

        Args:
            text: Text to search for tickers.

        Returns:
            List of unique ticker symbols found.
        """
        tickers = set()

        # $AAPL style cashtags
        for match in _TICKER_PATTERN.finditer(text):
            ticker = match.group(1)
            if ticker not in _EXCLUDED_WORDS:
                tickers.add(ticker)

        # Plain uppercase words that match known tickers
        for match in _TICKER_WORD_PATTERN.finditer(text):
            word = match.group(1)
            if word in _COMMON_TICKERS and word not in _EXCLUDED_WORDS:
                tickers.add(word)

        return sorted(tickers)

    def classify_topic(self, text: str) -> str:
        """Classify news topic.

        Args:
            text: Article text.

        Returns:
            Topic category string.
        """
        text_lower = text.lower()

        topic_keywords = {
            "earnings": ["earnings", "revenue", "eps", "quarter", "fiscal", "profit", "income"],
            "merger_acquisition": ["merger", "acquisition", "acquire", "buyout", "takeover", "deal"],
            "regulatory": ["sec", "fda", "regulation", "compliance", "investigation", "lawsuit"],
            "macro": ["fed", "interest rate", "inflation", "gdp", "employment", "recession"],
            "product": ["launch", "product", "release", "innovation", "patent", "technology"],
            "management": ["ceo", "cfo", "executive", "resign", "appoint", "leadership"],
            "dividend": ["dividend", "buyback", "share repurchase", "payout"],
            "guidance": ["guidance", "outlook", "forecast", "raised", "lowered", "maintained"],
        }

        scores = {}
        for topic, keywords in topic_keywords.items():
            count = sum(1 for kw in keywords if kw in text_lower)
            if count > 0:
                scores[topic] = count

        if scores:
            return max(scores, key=scores.get)
        return "general"

    def _score_with_model(self, text: str) -> dict:
        """Score using FinBERT model."""
        truncated = text[:self.config.max_text_length]
        try:
            result = self._model(truncated)
            label = result[0]["label"].lower()
            confidence = result[0]["score"]

            # Convert to numeric score
            if label == "positive":
                score = confidence
            elif label == "negative":
                score = -confidence
            else:
                score = 0.0

            return {"label": label, "score": score, "confidence": confidence}
        except Exception as e:
            logger.warning(f"Model inference failed: {e}")
            return self._score_with_keywords(text)

    def _score_with_keywords(self, text: str) -> dict:
        """Fallback keyword-based sentiment scoring."""
        text_lower = text.lower()

        # Use substring matching so "declines" matches "decline", etc.
        pos_count = sum(1 for kw in _POSITIVE_KEYWORDS if kw in text_lower)
        neg_count = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in text_lower)
        total = pos_count + neg_count

        if total == 0:
            return {"label": "neutral", "score": 0.0, "confidence": 0.3}

        score = (pos_count - neg_count) / total
        confidence = min(total / 10.0, 1.0)  # More keywords = higher confidence

        if score > 0.2:
            label = "positive"
        elif score < -0.2:
            label = "negative"
        else:
            label = "neutral"

        return {"label": label, "score": score, "confidence": confidence}
