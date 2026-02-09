"""Aspect-Based Sentiment Extraction.

Extracts sentiment for specific aspects of a financial text:
product quality, financial health, management quality, competitive
position, and market conditions.
"""

import enum
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from src.model_providers.config import ProviderResponse
from src.model_providers.router import FAST_CHAIN, FallbackChain, ModelRouter

logger = logging.getLogger(__name__)


class AspectCategory(enum.Enum):
    """Financial analysis aspects."""

    PRODUCT = "product"
    FINANCIALS = "financials"
    MANAGEMENT = "management"
    COMPETITIVE = "competitive"
    MARKET = "market"
    REGULATORY = "regulatory"
    GROWTH = "growth"
    RISK = "risk"


ASPECT_SYSTEM_PROMPT = """You are a financial aspect sentiment analyst.
For the given text, extract sentiment for each relevant aspect.
Return a JSON object:
{
  "aspects": [
    {
      "category": "<one of: product, financials, management, competitive, market, regulatory, growth, risk>",
      "sentiment": "positive" | "negative" | "neutral",
      "score": <float -1.0 to +1.0>,
      "confidence": <float 0.0 to 1.0>,
      "evidence": "<quote or paraphrase from text>"
    }
  ],
  "dominant_aspect": "<category with strongest signal>",
  "overall_score": <float -1.0 to +1.0>,
  "conflicting_aspects": <boolean, true if aspects disagree>
}
Only include aspects that are actually present in the text.
Return ONLY the JSON object, no markdown fences or extra text."""


@dataclass
class AspectConfig:
    """Configuration for aspect extraction."""

    min_confidence: float = 0.3
    max_text_length: int = 4000
    max_tokens: int = 768
    preferred_model: Optional[str] = None
    chain: FallbackChain = field(default_factory=lambda: FAST_CHAIN)


@dataclass
class AspectReport:
    """Full aspect extraction report."""

    aspects: list[dict] = field(default_factory=list)
    dominant_aspect: str = ""
    overall_score: float = 0.0
    conflicting_aspects: bool = False
    model_used: str = ""

    def to_dict(self) -> dict:
        return {
            "aspects": self.aspects,
            "dominant_aspect": self.dominant_aspect,
            "overall_score": self.overall_score,
            "conflicting_aspects": self.conflicting_aspects,
            "model_used": self.model_used,
        }

    def get_aspect(self, category: str) -> Optional[dict]:
        """Get a specific aspect by category name."""
        for a in self.aspects:
            if a.get("category") == category:
                return a
        return None

    @property
    def aspect_count(self) -> int:
        return len(self.aspects)

    def get_positive_aspects(self) -> list[dict]:
        """Return aspects with positive sentiment."""
        return [a for a in self.aspects if a.get("score", 0) > 0]

    def get_negative_aspects(self) -> list[dict]:
        """Return aspects with negative sentiment."""
        return [a for a in self.aspects if a.get("score", 0) < 0]


class AspectExtractor:
    """Extract aspect-level sentiment from financial text.

    Example::

        extractor = AspectExtractor(router=router)
        report = extractor.extract(
            "AAPL posted strong iPhone sales but faces regulatory scrutiny in EU"
        )
        # report.aspects = [
        #   {"category": "product", "sentiment": "positive", "score": 0.7, ...},
        #   {"category": "regulatory", "sentiment": "negative", "score": -0.5, ...},
        # ]
        # report.conflicting_aspects = True
    """

    def __init__(
        self,
        config: Optional[AspectConfig] = None,
        router: Optional[ModelRouter] = None,
    ):
        self.config = config or AspectConfig()
        self._router = router

    def extract(self, text: str) -> AspectReport:
        """Extract aspect-level sentiment from text.

        Args:
            text: Financial text to analyze.

        Returns:
            AspectReport with per-aspect sentiment breakdowns.
        """
        if not text or not text.strip():
            return AspectReport()

        text = text[:self.config.max_text_length]

        # Try LLM
        report = self._call_llm(text)
        if report is not None:
            return report

        # Fallback: rule-based aspect detection
        return self._rule_fallback(text)

    def _call_llm(self, text: str) -> Optional[AspectReport]:
        """Call LLM for aspect extraction."""
        if not self._router:
            return None

        messages = [{"role": "user", "content": text}]

        try:
            response, model_id = self._router.chat_with_fallback(
                messages=messages,
                system_prompt=ASPECT_SYSTEM_PROMPT,
                tools=[],
                chain=self.config.chain,
                preferred_model=self.config.preferred_model,
                max_tokens=self.config.max_tokens,
            )
            return self._parse_response(response, model_id)
        except Exception as e:
            logger.warning(f"Aspect extraction LLM call failed: {e}")
            return None

    def _parse_response(
        self, response: ProviderResponse, model_id: str
    ) -> AspectReport:
        """Parse the LLM response into an AspectReport."""
        text = response.text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return AspectReport(model_used=model_id)

        valid_categories = {c.value for c in AspectCategory}
        aspects = []
        for a in data.get("aspects", []):
            cat = str(a.get("category", "")).lower()
            if cat not in valid_categories:
                continue
            score = max(-1.0, min(1.0, float(a.get("score", 0.0))))
            confidence = max(0.0, min(1.0, float(a.get("confidence", 0.0))))
            if confidence < self.config.min_confidence:
                continue
            aspects.append({
                "category": cat,
                "sentiment": str(a.get("sentiment", "neutral")),
                "score": score,
                "confidence": confidence,
                "evidence": str(a.get("evidence", "")),
            })

        dominant = str(data.get("dominant_aspect", ""))
        if dominant not in valid_categories:
            dominant = aspects[0]["category"] if aspects else ""

        overall = max(-1.0, min(1.0, float(data.get("overall_score", 0.0))))

        return AspectReport(
            aspects=aspects,
            dominant_aspect=dominant,
            overall_score=overall,
            conflicting_aspects=bool(data.get("conflicting_aspects", False)),
            model_used=model_id,
        )

    @staticmethod
    def _rule_fallback(text: str) -> AspectReport:
        """Simple keyword-based aspect detection."""
        text_lower = text.lower()
        aspects = []

        aspect_keywords = {
            "product": (
                ["product", "launch", "innovation", "patent", "iphone", "sales", "device"],
                ["recall", "defect", "delay", "bug"],
            ),
            "financials": (
                ["revenue", "profit", "earnings", "beat", "growth", "margin"],
                ["loss", "miss", "decline", "debt", "writedown"],
            ),
            "management": (
                ["appointed", "leadership", "vision", "strategy"],
                ["resign", "fired", "scandal", "investigation"],
            ),
            "competitive": (
                ["market share", "dominance", "lead", "moat"],
                ["competition", "losing share", "disrupted"],
            ),
            "regulatory": (
                ["approved", "cleared", "compliance"],
                ["fine", "lawsuit", "investigation", "antitrust", "penalty", "scrutiny"],
            ),
            "growth": (
                ["expansion", "growth", "opportunity", "new market"],
                ["slowdown", "stagnation", "saturated"],
            ),
        }

        for cat, (pos_kws, neg_kws) in aspect_keywords.items():
            pos = sum(1 for kw in pos_kws if kw in text_lower)
            neg = sum(1 for kw in neg_kws if kw in text_lower)
            total = pos + neg
            if total == 0:
                continue
            score = (pos - neg) / total
            aspects.append({
                "category": cat,
                "sentiment": "positive" if score > 0 else ("negative" if score < 0 else "neutral"),
                "score": round(score, 2),
                "confidence": round(min(total / 3.0, 0.6), 2),
                "evidence": "",
            })

        dominant = ""
        if aspects:
            dominant = max(aspects, key=lambda a: abs(a["score"]))["category"]

        has_pos = any(a["score"] > 0 for a in aspects)
        has_neg = any(a["score"] < 0 for a in aspects)

        overall = sum(a["score"] for a in aspects) / max(len(aspects), 1)

        return AspectReport(
            aspects=aspects,
            dominant_aspect=dominant,
            overall_score=round(overall, 3),
            conflicting_aspects=has_pos and has_neg,
            model_used="rule_fallback",
        )
