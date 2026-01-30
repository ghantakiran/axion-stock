"""Earnings Call NLP Analysis.

Analyzes earnings call transcripts for management tone,
sentiment, key topics, and forward guidance signals.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.sentiment.config import EarningsNLPConfig

logger = logging.getLogger(__name__)


@dataclass
class EarningsTranscript:
    """Earnings call transcript data."""

    symbol: str = ""
    quarter: str = ""  # e.g., "Q4_2025"
    date: str = ""
    prepared_remarks: str = ""
    qa_section: str = ""
    full_text: str = ""

    @property
    def combined_text(self) -> str:
        if self.full_text:
            return self.full_text
        return f"{self.prepared_remarks} {self.qa_section}".strip()


@dataclass
class CallAnalysis:
    """Earnings call analysis result."""

    symbol: str = ""
    quarter: str = ""
    management_tone: float = 0.0  # -1 to 1
    qa_sentiment: float = 0.0  # -1 to 1
    overall_score: float = 0.0  # -1 to 1
    positive_ratio: float = 0.0
    negative_ratio: float = 0.0
    uncertainty_count: int = 0
    forward_looking_count: int = 0
    confidence_score: float = 0.0  # 0 to 1
    key_topics: list = field(default_factory=list)
    guidance_direction: str = "maintained"  # raised, maintained, lowered
    fog_index: float = 0.0  # Readability
    word_count: int = 0
    compared_to_previous: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "quarter": self.quarter,
            "management_tone": self.management_tone,
            "qa_sentiment": self.qa_sentiment,
            "overall_score": self.overall_score,
            "positive_ratio": self.positive_ratio,
            "negative_ratio": self.negative_ratio,
            "uncertainty_count": self.uncertainty_count,
            "forward_looking_count": self.forward_looking_count,
            "confidence_score": self.confidence_score,
            "key_topics": self.key_topics,
            "guidance_direction": self.guidance_direction,
            "fog_index": self.fog_index,
        }


class EarningsCallAnalyzer:
    """Analyze earnings call transcripts for sentiment signals.

    Extracts management tone, uncertainty, forward guidance,
    and key topics from earnings call text.

    Example:
        analyzer = EarningsCallAnalyzer()
        analysis = analyzer.analyze(transcript)
        tone = analysis.management_tone
    """

    def __init__(self, config: Optional[EarningsNLPConfig] = None):
        self.config = config or EarningsNLPConfig()

    def analyze(self, transcript: EarningsTranscript) -> CallAnalysis:
        """Analyze a full earnings call transcript.

        Args:
            transcript: Earnings call transcript.

        Returns:
            CallAnalysis with all tone metrics.
        """
        analysis = CallAnalysis(
            symbol=transcript.symbol,
            quarter=transcript.quarter,
        )

        text = transcript.combined_text
        if not text:
            return analysis

        words = text.lower().split()
        analysis.word_count = len(words)

        # Management tone (prepared remarks)
        if transcript.prepared_remarks:
            analysis.management_tone = self._analyze_tone(transcript.prepared_remarks)
        else:
            analysis.management_tone = self._analyze_tone(text)

        # Q&A sentiment
        if transcript.qa_section:
            analysis.qa_sentiment = self._analyze_tone(transcript.qa_section)

        # Positive / negative ratio
        pos_count, neg_count = self._count_sentiment_words(text)
        total_sentiment = pos_count + neg_count
        if total_sentiment > 0:
            analysis.positive_ratio = pos_count / total_sentiment
            analysis.negative_ratio = neg_count / total_sentiment

        # Uncertainty
        analysis.uncertainty_count = self._count_words(text, self.config.uncertainty_words)

        # Forward-looking statements
        analysis.forward_looking_count = self._count_words(text, self.config.forward_looking_words)

        # Confidence score
        analysis.confidence_score = self._compute_confidence(analysis)

        # Key topics
        analysis.key_topics = self._extract_topics(text)

        # Guidance direction
        analysis.guidance_direction = self._detect_guidance_direction(text)

        # Fog index (readability)
        analysis.fog_index = self._compute_fog_index(text)

        # Overall score
        analysis.overall_score = self._compute_overall(analysis)

        return analysis

    def analyze_multiple(
        self,
        transcripts: list[EarningsTranscript],
    ) -> list[CallAnalysis]:
        """Analyze multiple transcripts."""
        return [self.analyze(t) for t in transcripts]

    def compare_quarters(
        self,
        current: CallAnalysis,
        previous: CallAnalysis,
    ) -> dict:
        """Compare current quarter analysis to previous.

        Args:
            current: Current quarter analysis.
            previous: Previous quarter analysis.

        Returns:
            Dict of metric changes.
        """
        return {
            "tone_change": current.management_tone - previous.management_tone,
            "qa_change": current.qa_sentiment - previous.qa_sentiment,
            "confidence_change": current.confidence_score - previous.confidence_score,
            "uncertainty_change": current.uncertainty_count - previous.uncertainty_count,
            "forward_looking_change": current.forward_looking_count - previous.forward_looking_count,
            "tone_improving": current.management_tone > previous.management_tone,
        }

    def _analyze_tone(self, text: str) -> float:
        """Compute tone score for text. Returns -1 to 1."""
        pos_count, neg_count = self._count_sentiment_words(text)
        total = pos_count + neg_count

        if total == 0:
            return 0.0

        # Net sentiment normalized
        return float((pos_count - neg_count) / total)

    def _count_sentiment_words(self, text: str) -> tuple[int, int]:
        """Count positive and negative sentiment words."""
        text_lower = text.lower()

        pos_count = sum(
            1 for word in self.config.positive_words
            if word in text_lower
        )
        neg_count = sum(
            1 for word in self.config.negative_words
            if word in text_lower
        )

        return pos_count, neg_count

    def _count_words(self, text: str, word_list: list) -> int:
        """Count occurrences of words from a list."""
        text_lower = text.lower()
        return sum(text_lower.count(word) for word in word_list)

    def _compute_confidence(self, analysis: CallAnalysis) -> float:
        """Compute management confidence score (0 to 1)."""
        if analysis.word_count == 0:
            return 0.5

        # High forward-looking + low uncertainty = high confidence
        fl_density = analysis.forward_looking_count / max(analysis.word_count / 100, 1)
        unc_density = analysis.uncertainty_count / max(analysis.word_count / 100, 1)

        confidence = 0.5 + 0.25 * min(fl_density, 2) - 0.25 * min(unc_density, 2)
        return float(np.clip(confidence, 0.0, 1.0))

    def _extract_topics(self, text: str) -> list[str]:
        """Extract key topics discussed in transcript."""
        text_lower = text.lower()
        topics = []

        topic_patterns = {
            "revenue_growth": ["revenue growth", "top line", "sales growth"],
            "margins": ["gross margin", "operating margin", "profit margin", "margin expansion"],
            "guidance": ["guidance", "outlook", "forecast", "expect"],
            "ai_technology": ["artificial intelligence", " ai ", "machine learning", "generative ai"],
            "cost_reduction": ["cost reduction", "expense management", "efficiency", "restructuring"],
            "market_expansion": ["new market", "international", "expansion", "geographic"],
            "product_launch": ["new product", "launch", "release", "innovation"],
            "competition": ["competitive", "competitor", "market share"],
            "macro": ["macroeconomic", "interest rate", "inflation", "economic"],
            "capital_allocation": ["buyback", "share repurchase", "dividend", "capital allocation"],
        }

        for topic, keywords in topic_patterns.items():
            for keyword in keywords:
                if keyword in text_lower:
                    topics.append(topic)
                    break

        return topics

    def _detect_guidance_direction(self, text: str) -> str:
        """Detect if guidance was raised, maintained, or lowered."""
        text_lower = text.lower()

        raise_patterns = [
            "raise guidance", "raised guidance", "raising guidance",
            "increase guidance", "raised our outlook", "raising outlook",
            "above prior guidance", "upward revision",
        ]
        lower_patterns = [
            "lower guidance", "lowered guidance", "lowering guidance",
            "reduce guidance", "reduced outlook", "below prior guidance",
            "downward revision", "revise lower",
        ]

        raise_count = sum(1 for p in raise_patterns if p in text_lower)
        lower_count = sum(1 for p in lower_patterns if p in text_lower)

        if raise_count > lower_count:
            return "raised"
        elif lower_count > raise_count:
            return "lowered"
        return "maintained"

    def _compute_fog_index(self, text: str) -> float:
        """Compute Gunning Fog Index for readability.

        Higher values indicate more complex text. Scores above 12
        suggest the text may be obscuring information.
        """
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return 0.0

        words = text.split()
        total_words = len(words)
        total_sentences = len(sentences)

        if total_sentences == 0 or total_words == 0:
            return 0.0

        # Complex words: 3+ syllables (simplified)
        complex_words = sum(1 for w in words if self._syllable_count(w) >= 3)

        avg_sentence_length = total_words / total_sentences
        pct_complex = complex_words / total_words * 100

        fog = 0.4 * (avg_sentence_length + pct_complex)
        return round(fog, 1)

    def _syllable_count(self, word: str) -> int:
        """Approximate syllable count for a word."""
        word = word.lower().strip(".,;:!?\"'")
        if not word:
            return 0
        count = 0
        vowels = "aeiouy"
        prev_vowel = False
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel
        if word.endswith("e") and count > 1:
            count -= 1
        return max(count, 1)

    def _compute_overall(self, analysis: CallAnalysis) -> float:
        """Compute overall earnings call score."""
        # Weighted combination
        tone = analysis.management_tone * 0.4
        qa = analysis.qa_sentiment * 0.3
        confidence = (analysis.confidence_score - 0.5) * 2 * 0.2  # Center at 0
        guidance_map = {"raised": 0.3, "maintained": 0.0, "lowered": -0.3}
        guidance = guidance_map.get(analysis.guidance_direction, 0.0) * 0.1

        return float(np.clip(tone + qa + confidence + guidance, -1.0, 1.0))
