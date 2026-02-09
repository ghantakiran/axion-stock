"""Core LLM Sentiment Analyzer.

Sends financial text to an LLM provider for nuanced sentiment extraction.
Returns structured results with sentiment label, score, confidence,
reasoning, and key themes.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from src.model_providers.config import (
    ProviderConfig,
    ProviderResponse,
    ProviderType,
)
from src.model_providers.registry import ProviderRegistry, create_provider
from src.model_providers.router import (
    FAST_CHAIN,
    FLAGSHIP_CHAIN,
    FallbackChain,
    ModelRouter,
)

logger = logging.getLogger(__name__)


# ── Prompt templates ──────────────────────────────────────────────────

SENTIMENT_SYSTEM_PROMPT = """You are a financial sentiment analysis expert.
Analyze the provided text and return a JSON object with exactly these fields:
{
  "sentiment": "bullish" | "bearish" | "neutral" | "mixed",
  "score": <float from -1.0 (very bearish) to +1.0 (very bullish)>,
  "confidence": <float from 0.0 to 1.0>,
  "reasoning": "<1-2 sentence explanation>",
  "themes": ["<key theme 1>", "<key theme 2>"],
  "tickers": ["<TICKER1>", "<TICKER2>"],
  "urgency": "low" | "medium" | "high",
  "time_horizon": "short" | "medium" | "long"
}
Rules:
- "mixed" means conflicting bullish AND bearish signals in the same text.
- confidence reflects how certain the sentiment reading is, NOT how extreme it is.
- urgency = "high" for breaking news, earnings surprises, regulatory actions.
- Extract only actual stock ticker symbols (e.g. AAPL, TSLA), not abbreviations.
- Return ONLY the JSON object, no markdown fences or extra text."""

BATCH_SYSTEM_PROMPT = """You are a financial sentiment analysis expert.
Analyze each text and return a JSON array of objects. Each object has:
{
  "index": <0-based index>,
  "sentiment": "bullish" | "bearish" | "neutral" | "mixed",
  "score": <float -1.0 to +1.0>,
  "confidence": <float 0.0 to 1.0>,
  "themes": ["<theme>"],
  "tickers": ["<TICKER>"]
}
Return ONLY the JSON array, no markdown fences or extra text."""


@dataclass
class SentimentAspect:
    """A single thematic aspect of sentiment."""

    theme: str = ""
    sentiment: str = "neutral"
    score: float = 0.0

    def to_dict(self) -> dict:
        return {"theme": self.theme, "sentiment": self.sentiment, "score": self.score}


@dataclass
class LLMSentimentResult:
    """Result from LLM sentiment analysis."""

    sentiment: str = "neutral"  # bullish, bearish, neutral, mixed
    score: float = 0.0  # -1 to +1
    confidence: float = 0.0  # 0 to 1
    reasoning: str = ""
    themes: list[str] = field(default_factory=list)
    tickers: list[str] = field(default_factory=list)
    urgency: str = "low"  # low, medium, high
    time_horizon: str = "medium"  # short, medium, long
    model_used: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "sentiment": self.sentiment,
            "score": self.score,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "themes": self.themes,
            "tickers": self.tickers,
            "urgency": self.urgency,
            "time_horizon": self.time_horizon,
            "model_used": self.model_used,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }

    @property
    def is_actionable(self) -> bool:
        """True if sentiment is strong enough to act on."""
        return self.confidence >= 0.6 and abs(self.score) >= 0.3

    @property
    def sentiment_label(self) -> str:
        """Normalized label for compatibility with existing SentimentScore."""
        mapping = {"bullish": "positive", "bearish": "negative"}
        return mapping.get(self.sentiment, self.sentiment)


@dataclass
class AnalyzerConfig:
    """Configuration for LLM sentiment analyzer."""

    use_flagship: bool = False  # True = higher quality, higher cost
    max_text_length: int = 4000
    max_tokens: int = 512
    batch_size: int = 10
    fallback_to_keywords: bool = True
    cache_results: bool = True
    preferred_model: Optional[str] = None

    @property
    def chain(self) -> FallbackChain:
        return FLAGSHIP_CHAIN if self.use_flagship else FAST_CHAIN


class LLMSentimentAnalyzer:
    """Analyze financial text sentiment using LLM providers.

    Uses the model_providers router for automatic fallback across
    Claude, GPT, Gemini, DeepSeek, and local Ollama models.

    Example::

        analyzer = LLMSentimentAnalyzer()
        result = analyzer.analyze("NVDA beats earnings expectations")
        print(result.sentiment, result.score)  # bullish, 0.75

        # Batch mode
        results = analyzer.analyze_batch([
            "AAPL revenue up 15%",
            "TSLA recalls 500K vehicles",
        ])
    """

    def __init__(
        self,
        config: Optional[AnalyzerConfig] = None,
        registry: Optional[ProviderRegistry] = None,
        router: Optional[ModelRouter] = None,
    ):
        self.config = config or AnalyzerConfig()
        self._registry = registry
        self._router = router
        self._cache: dict[str, LLMSentimentResult] = {}

    @property
    def router(self) -> Optional[ModelRouter]:
        """Lazy router access."""
        if self._router:
            return self._router
        if self._registry:
            self._router = ModelRouter(self._registry)
        return self._router

    def analyze(self, text: str, context: str = "") -> LLMSentimentResult:
        """Analyze a single text for financial sentiment.

        Args:
            text: The text to analyze (news headline, social post, etc.)
            context: Optional context (e.g. "earnings call transcript")

        Returns:
            LLMSentimentResult with structured sentiment data.
        """
        if not text or not text.strip():
            return LLMSentimentResult()

        text = text[:self.config.max_text_length]

        # Check cache
        cache_key = text[:200]
        if self.config.cache_results and cache_key in self._cache:
            return self._cache[cache_key]

        # Build message
        user_content = text
        if context:
            user_content = f"Context: {context}\n\nText: {text}"

        messages = [{"role": "user", "content": user_content}]

        # Try LLM
        result = self._call_llm(messages, SENTIMENT_SYSTEM_PROMPT)

        if result is None and self.config.fallback_to_keywords:
            result = self._keyword_fallback(text)

        if result is None:
            result = LLMSentimentResult()

        # Cache
        if self.config.cache_results:
            self._cache[cache_key] = result

        return result

    def analyze_batch(self, texts: list[str]) -> list[LLMSentimentResult]:
        """Analyze multiple texts in a single LLM call for efficiency.

        Args:
            texts: List of texts to analyze.

        Returns:
            List of LLMSentimentResult, one per input text.
        """
        if not texts:
            return []

        results: list[LLMSentimentResult] = []

        for i in range(0, len(texts), self.config.batch_size):
            batch = texts[i:i + self.config.batch_size]
            batch_results = self._analyze_batch_chunk(batch)
            results.extend(batch_results)

        return results

    def estimate_cost(self, text: str) -> float:
        """Estimate cost in USD for analyzing a single text."""
        if not self.router:
            return 0.0
        # Rough estimate: 200 input tokens + 150 output tokens
        input_tokens = len(text.split()) * 1.3  # ~1.3 tokens per word
        return self.router.estimate_cost(
            self.config.preferred_model or "claude-haiku-4-5-20251001",
            int(input_tokens + 100),  # +100 for system prompt portion
            150,
        )

    def clear_cache(self):
        """Clear the result cache."""
        self._cache.clear()

    # ── Private ───────────────────────────────────────────────────────

    def _call_llm(
        self, messages: list[dict], system_prompt: str
    ) -> Optional[LLMSentimentResult]:
        """Call the LLM and parse the response."""
        if not self.router:
            return None

        try:
            response, model_id = self.router.chat_with_fallback(
                messages=messages,
                system_prompt=system_prompt,
                tools=[],
                chain=self.config.chain,
                preferred_model=self.config.preferred_model,
                max_tokens=self.config.max_tokens,
            )
            return self._parse_response(response, model_id)
        except Exception as e:
            logger.warning(f"LLM sentiment call failed: {e}")
            return None

    def _parse_response(
        self, response: ProviderResponse, model_id: str
    ) -> LLMSentimentResult:
        """Parse LLM JSON response into structured result."""
        text = response.text.strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse LLM response as JSON: {text[:200]}")
            return LLMSentimentResult(
                reasoning=text[:500],
                model_used=model_id,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )

        sentiment = str(data.get("sentiment", "neutral")).lower()
        if sentiment not in ("bullish", "bearish", "neutral", "mixed"):
            sentiment = "neutral"

        score = float(data.get("score", 0.0))
        score = max(-1.0, min(1.0, score))

        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

        urgency = str(data.get("urgency", "low")).lower()
        if urgency not in ("low", "medium", "high"):
            urgency = "low"

        time_horizon = str(data.get("time_horizon", "medium")).lower()
        if time_horizon not in ("short", "medium", "long"):
            time_horizon = "medium"

        return LLMSentimentResult(
            sentiment=sentiment,
            score=score,
            confidence=confidence,
            reasoning=str(data.get("reasoning", "")),
            themes=list(data.get("themes", [])),
            tickers=[str(t).upper() for t in data.get("tickers", [])],
            urgency=urgency,
            time_horizon=time_horizon,
            model_used=model_id,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

    def _analyze_batch_chunk(
        self, texts: list[str]
    ) -> list[LLMSentimentResult]:
        """Analyze a chunk of texts in a single LLM call."""
        numbered = "\n".join(
            f"[{i}] {t[:self.config.max_text_length]}" for i, t in enumerate(texts)
        )
        messages = [{"role": "user", "content": numbered}]

        if not self.router:
            return [
                self._keyword_fallback(t) if self.config.fallback_to_keywords
                else LLMSentimentResult()
                for t in texts
            ]

        try:
            response, model_id = self.router.chat_with_fallback(
                messages=messages,
                system_prompt=BATCH_SYSTEM_PROMPT,
                tools=[],
                chain=self.config.chain,
                preferred_model=self.config.preferred_model,
                max_tokens=self.config.max_tokens * len(texts),
            )
            return self._parse_batch_response(response, model_id, len(texts))
        except Exception:
            return [
                self._keyword_fallback(t) if self.config.fallback_to_keywords
                else LLMSentimentResult()
                for t in texts
            ]

    def _parse_batch_response(
        self, response: ProviderResponse, model_id: str, expected: int
    ) -> list[LLMSentimentResult]:
        """Parse batch JSON array response."""
        text = response.text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            return [LLMSentimentResult(model_used=model_id)] * expected

        if not isinstance(items, list):
            return [LLMSentimentResult(model_used=model_id)] * expected

        results = []
        for i in range(expected):
            data = items[i] if i < len(items) else {}
            sentiment = str(data.get("sentiment", "neutral")).lower()
            if sentiment not in ("bullish", "bearish", "neutral", "mixed"):
                sentiment = "neutral"
            score = max(-1.0, min(1.0, float(data.get("score", 0.0))))
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))

            results.append(LLMSentimentResult(
                sentiment=sentiment,
                score=score,
                confidence=confidence,
                themes=list(data.get("themes", [])),
                tickers=[str(t).upper() for t in data.get("tickers", [])],
                model_used=model_id,
                input_tokens=response.input_tokens // max(expected, 1),
                output_tokens=response.output_tokens // max(expected, 1),
            ))

        return results

    @staticmethod
    def _keyword_fallback(text: str) -> LLMSentimentResult:
        """Simple keyword-based fallback when no LLM is available."""
        text_lower = text.lower()

        positive = {
            "beat", "beats", "exceeded", "record", "surge", "rally",
            "growth", "strong", "upgrade", "outperform", "buy", "bullish",
            "gain", "profit", "revenue", "breakthrough", "expansion",
            "optimistic", "momentum", "recovery", "rebound", "raised",
        }
        negative = {
            "miss", "decline", "loss", "sell", "crash", "plunge",
            "downgrade", "underperform", "bearish", "weak", "concern",
            "risk", "warning", "layoff", "recession", "default", "fraud",
            "investigation", "lawsuit", "penalty", "bankruptcy",
        }

        pos = sum(1 for kw in positive if kw in text_lower)
        neg = sum(1 for kw in negative if kw in text_lower)
        total = pos + neg

        if total == 0:
            return LLMSentimentResult(sentiment="neutral", score=0.0, confidence=0.3)

        score = (pos - neg) / total
        confidence = min(total / 8.0, 0.7)  # Cap at 0.7 for keyword-based

        if score > 0.2:
            sentiment = "bullish"
        elif score < -0.2:
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        return LLMSentimentResult(
            sentiment=sentiment,
            score=round(score, 3),
            confidence=round(confidence, 3),
            model_used="keyword_fallback",
        )
