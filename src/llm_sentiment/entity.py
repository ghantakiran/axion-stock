"""Entity-Level Sentiment Resolution.

Separates sentiment by named entity (company, CEO, sector, product)
so that "AAPL is doing well despite Tim Cook criticism" resolves to
AAPL=positive, Tim Cook=negative.
"""

import enum
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from src.model_providers.config import ProviderResponse
from src.model_providers.router import FAST_CHAIN, FallbackChain, ModelRouter

logger = logging.getLogger(__name__)


class EntityType(enum.Enum):
    """Types of financial entities."""

    COMPANY = "company"
    PERSON = "person"
    SECTOR = "sector"
    PRODUCT = "product"
    INDEX = "index"
    CURRENCY = "currency"
    COMMODITY = "commodity"


ENTITY_SYSTEM_PROMPT = """You are a financial named entity recognition and sentiment expert.
For the given text, identify each entity and its sentiment.
Return a JSON object:
{
  "entities": [
    {
      "name": "<entity name>",
      "type": "<company|person|sector|product|index|currency|commodity>",
      "ticker": "<ticker symbol if applicable, else null>",
      "sentiment": "positive" | "negative" | "neutral",
      "score": <float -1.0 to +1.0>,
      "confidence": <float 0.0 to 1.0>,
      "context": "<brief phrase from text>"
    }
  ],
  "relationships": [
    {
      "entity1": "<name>",
      "entity2": "<name>",
      "relation": "<comparison|partnership|competition|subsidiary>"
    }
  ]
}
Include only entities with clear sentiment signals.
Return ONLY the JSON object, no markdown fences or extra text."""


@dataclass
class EntitySentiment:
    """Sentiment for a single entity."""

    name: str = ""
    entity_type: str = "company"
    ticker: Optional[str] = None
    sentiment: str = "neutral"
    score: float = 0.0
    confidence: float = 0.0
    context: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "ticker": self.ticker,
            "sentiment": self.sentiment,
            "score": self.score,
            "confidence": self.confidence,
            "context": self.context,
        }


@dataclass
class EntityConfig:
    """Configuration for entity resolution."""

    min_confidence: float = 0.3
    max_text_length: int = 4000
    max_tokens: int = 768
    preferred_model: Optional[str] = None
    chain: FallbackChain = field(default_factory=lambda: FAST_CHAIN)


@dataclass
class EntityReport:
    """Full entity sentiment report."""

    entities: list[EntitySentiment] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    model_used: str = ""

    def to_dict(self) -> dict:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relationships": self.relationships,
            "model_used": self.model_used,
        }

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    def get_by_type(self, entity_type: str) -> list[EntitySentiment]:
        """Filter entities by type."""
        return [e for e in self.entities if e.entity_type == entity_type]

    def get_by_ticker(self, ticker: str) -> Optional[EntitySentiment]:
        """Get entity sentiment by ticker symbol."""
        ticker_upper = ticker.upper()
        for e in self.entities:
            if e.ticker and e.ticker.upper() == ticker_upper:
                return e
        return None

    def get_most_positive(self) -> Optional[EntitySentiment]:
        """Return the entity with the highest positive score."""
        if not self.entities:
            return None
        return max(self.entities, key=lambda e: e.score)

    def get_most_negative(self) -> Optional[EntitySentiment]:
        """Return the entity with the lowest score."""
        if not self.entities:
            return None
        return min(self.entities, key=lambda e: e.score)


class EntityResolver:
    """Resolve entity-level sentiment from financial text.

    Example::

        resolver = EntityResolver(router=router)
        report = resolver.resolve(
            "Apple posted record revenue while Google faces antitrust probe"
        )
        # report.entities = [
        #   EntitySentiment(name="Apple", ticker="AAPL", sentiment="positive", score=0.8),
        #   EntitySentiment(name="Google", ticker="GOOGL", sentiment="negative", score=-0.6),
        # ]
    """

    def __init__(
        self,
        config: Optional[EntityConfig] = None,
        router: Optional[ModelRouter] = None,
    ):
        self.config = config or EntityConfig()
        self._router = router

    def resolve(self, text: str) -> EntityReport:
        """Extract entity-level sentiment from text.

        Args:
            text: Financial text to analyze.

        Returns:
            EntityReport with per-entity sentiment breakdowns.
        """
        if not text or not text.strip():
            return EntityReport()

        text = text[:self.config.max_text_length]

        report = self._call_llm(text)
        if report is not None:
            return report

        return self._rule_fallback(text)

    def _call_llm(self, text: str) -> Optional[EntityReport]:
        """Call LLM for entity resolution."""
        if not self._router:
            return None

        messages = [{"role": "user", "content": text}]

        try:
            response, model_id = self._router.chat_with_fallback(
                messages=messages,
                system_prompt=ENTITY_SYSTEM_PROMPT,
                tools=[],
                chain=self.config.chain,
                preferred_model=self.config.preferred_model,
                max_tokens=self.config.max_tokens,
            )
            return self._parse_response(response, model_id)
        except Exception as e:
            logger.warning(f"Entity resolution LLM call failed: {e}")
            return None

    def _parse_response(
        self, response: ProviderResponse, model_id: str
    ) -> EntityReport:
        """Parse LLM response into EntityReport."""
        text = response.text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return EntityReport(model_used=model_id)

        valid_types = {t.value for t in EntityType}
        entities = []
        for e in data.get("entities", []):
            etype = str(e.get("type", "company")).lower()
            if etype not in valid_types:
                etype = "company"
            score = max(-1.0, min(1.0, float(e.get("score", 0.0))))
            confidence = max(0.0, min(1.0, float(e.get("confidence", 0.0))))
            if confidence < self.config.min_confidence:
                continue
            entities.append(EntitySentiment(
                name=str(e.get("name", "")),
                entity_type=etype,
                ticker=e.get("ticker"),
                sentiment=str(e.get("sentiment", "neutral")),
                score=score,
                confidence=confidence,
                context=str(e.get("context", "")),
            ))

        relationships = []
        for r in data.get("relationships", []):
            if "entity1" in r and "entity2" in r:
                relationships.append({
                    "entity1": str(r["entity1"]),
                    "entity2": str(r["entity2"]),
                    "relation": str(r.get("relation", "related")),
                })

        return EntityReport(
            entities=entities,
            relationships=relationships,
            model_used=model_id,
        )

    @staticmethod
    def _rule_fallback(text: str) -> EntityReport:
        """Simple ticker-based entity detection fallback."""
        import re

        # Known company names → tickers
        company_map = {
            "apple": ("Apple", "AAPL"), "microsoft": ("Microsoft", "MSFT"),
            "google": ("Google", "GOOGL"), "alphabet": ("Alphabet", "GOOGL"),
            "amazon": ("Amazon", "AMZN"), "meta": ("Meta", "META"),
            "tesla": ("Tesla", "TSLA"), "nvidia": ("NVIDIA", "NVDA"),
            "jpmorgan": ("JPMorgan", "JPM"), "goldman": ("Goldman Sachs", "GS"),
        }

        text_lower = text.lower()
        entities = []

        # Simple positive/negative keyword proximity
        pos_words = {"record", "strong", "beat", "growth", "surge", "profit", "revenue"}
        neg_words = {"decline", "loss", "probe", "lawsuit", "miss", "weak", "fraud"}

        for key, (name, ticker) in company_map.items():
            if key not in text_lower:
                continue

            # Find sentiment near the entity mention
            idx = text_lower.index(key)
            window = text_lower[max(0, idx - 50):idx + 50 + len(key)]
            pos = sum(1 for w in pos_words if w in window)
            neg = sum(1 for w in neg_words if w in window)
            total = pos + neg

            if total == 0:
                score = 0.0
                sentiment = "neutral"
            else:
                score = round((pos - neg) / total, 2)
                sentiment = "positive" if score > 0 else ("negative" if score < 0 else "neutral")

            entities.append(EntitySentiment(
                name=name,
                entity_type="company",
                ticker=ticker,
                sentiment=sentiment,
                score=score,
                confidence=round(min(total / 3.0, 0.5), 2),
            ))

        # Cashtag extraction: $AAPL
        for match in re.finditer(r'\$([A-Z]{1,5})\b', text):
            ticker = match.group(1)
            if any(e.ticker == ticker for e in entities):
                continue
            entities.append(EntitySentiment(
                name=ticker,
                entity_type="company",
                ticker=ticker,
                sentiment="neutral",
                score=0.0,
                confidence=0.2,
            ))

        return EntityReport(entities=entities, model_used="rule_fallback")
