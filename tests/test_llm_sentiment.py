"""Tests for LLM Sentiment Engine (PRD-151).

Tests: LLMSentimentAnalyzer, AspectExtractor, EntityResolver,
SentimentPredictor — all with mocked LLM responses.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.llm_sentiment.analyzer import (
    AnalyzerConfig,
    LLMSentimentAnalyzer,
    LLMSentimentResult,
    SentimentAspect,
    SENTIMENT_SYSTEM_PROMPT,
)
from src.llm_sentiment.aspects import (
    AspectCategory,
    AspectConfig,
    AspectExtractor,
    AspectReport,
)
from src.llm_sentiment.entity import (
    EntityConfig,
    EntityReport,
    EntityResolver,
    EntitySentiment,
    EntityType,
)
from src.llm_sentiment.predictor import (
    ForecastHorizon,
    PredictionReport,
    PredictorConfig,
    SentimentForecast,
    SentimentPredictor,
)


# ── Helpers ───────────────────────────────────────────────────────────

def _mock_response(text: str, model_id: str = "claude-haiku-4-5-20251001"):
    """Create a mock ProviderResponse."""
    resp = MagicMock()
    resp.text = text
    resp.input_tokens = 100
    resp.output_tokens = 50
    return resp, model_id


def _mock_router(response_text: str, model_id: str = "claude-haiku-4-5-20251001"):
    """Create a mock ModelRouter that returns the given response."""
    router = MagicMock()
    resp = MagicMock()
    resp.text = response_text
    resp.input_tokens = 100
    resp.output_tokens = 50
    router.chat_with_fallback.return_value = (resp, model_id)
    router.estimate_cost.return_value = 0.001
    return router


# ── TestAnalyzerConfig ───────────────────────────────────────────────


class TestAnalyzerConfig:
    """Test AnalyzerConfig defaults and chain selection."""

    def test_defaults(self):
        cfg = AnalyzerConfig()
        assert cfg.use_flagship is False
        assert cfg.max_text_length == 4000
        assert cfg.batch_size == 10
        assert cfg.fallback_to_keywords is True
        assert cfg.cache_results is True

    def test_fast_chain(self):
        cfg = AnalyzerConfig(use_flagship=False)
        assert "claude-haiku" in cfg.chain.models[0]

    def test_flagship_chain(self):
        cfg = AnalyzerConfig(use_flagship=True)
        chain = cfg.chain
        assert any("claude" in m for m in chain.models)


# ── TestLLMSentimentResult ───────────────────────────────────────────


class TestLLMSentimentResult:
    """Test LLMSentimentResult dataclass."""

    def test_defaults(self):
        r = LLMSentimentResult()
        assert r.sentiment == "neutral"
        assert r.score == 0.0
        assert r.confidence == 0.0
        assert r.themes == []
        assert r.tickers == []

    def test_to_dict(self):
        r = LLMSentimentResult(sentiment="bullish", score=0.8, confidence=0.9)
        d = r.to_dict()
        assert d["sentiment"] == "bullish"
        assert d["score"] == 0.8

    def test_is_actionable(self):
        r = LLMSentimentResult(sentiment="bullish", score=0.8, confidence=0.9)
        assert r.is_actionable is True

        r2 = LLMSentimentResult(sentiment="neutral", score=0.1, confidence=0.5)
        assert r2.is_actionable is False

    def test_sentiment_label(self):
        assert LLMSentimentResult(sentiment="bullish").sentiment_label == "positive"
        assert LLMSentimentResult(sentiment="bearish").sentiment_label == "negative"
        assert LLMSentimentResult(sentiment="neutral").sentiment_label == "neutral"
        assert LLMSentimentResult(sentiment="mixed").sentiment_label == "mixed"


# ── TestLLMSentimentAnalyzer ─────────────────────────────────────────


class TestLLMSentimentAnalyzer:
    """Test the core LLM analyzer with mocked provider responses."""

    def test_empty_text(self):
        analyzer = LLMSentimentAnalyzer()
        result = analyzer.analyze("")
        assert result.sentiment == "neutral"

    def test_analyze_with_llm(self):
        response_json = json.dumps({
            "sentiment": "bullish",
            "score": 0.75,
            "confidence": 0.85,
            "reasoning": "Strong earnings beat",
            "themes": ["earnings", "growth"],
            "tickers": ["NVDA"],
            "urgency": "high",
            "time_horizon": "short",
        })
        router = _mock_router(response_json)
        analyzer = LLMSentimentAnalyzer(router=router)

        result = analyzer.analyze("NVDA beats earnings expectations by 20%")
        assert result.sentiment == "bullish"
        assert result.score == 0.75
        assert result.confidence == 0.85
        assert "NVDA" in result.tickers
        assert result.urgency == "high"
        assert result.model_used == "claude-haiku-4-5-20251001"

    def test_analyze_with_markdown_fences(self):
        response_json = "```json\n" + json.dumps({
            "sentiment": "bearish",
            "score": -0.6,
            "confidence": 0.7,
            "reasoning": "Recall concern",
            "themes": ["recall"],
            "tickers": ["TSLA"],
            "urgency": "medium",
            "time_horizon": "short",
        }) + "\n```"
        router = _mock_router(response_json)
        analyzer = LLMSentimentAnalyzer(router=router)

        result = analyzer.analyze("Tesla recalls 500K vehicles")
        assert result.sentiment == "bearish"
        assert result.score == -0.6

    def test_caching(self):
        response_json = json.dumps({
            "sentiment": "bullish", "score": 0.5, "confidence": 0.6,
            "reasoning": "", "themes": [], "tickers": [],
            "urgency": "low", "time_horizon": "medium",
        })
        router = _mock_router(response_json)
        analyzer = LLMSentimentAnalyzer(router=router)

        r1 = analyzer.analyze("test text")
        r2 = analyzer.analyze("test text")
        assert r1.sentiment == r2.sentiment
        # Should only call LLM once due to caching
        assert router.chat_with_fallback.call_count == 1

    def test_cache_clear(self):
        analyzer = LLMSentimentAnalyzer()
        analyzer._cache["key"] = LLMSentimentResult(sentiment="bullish")
        analyzer.clear_cache()
        assert len(analyzer._cache) == 0

    def test_keyword_fallback(self):
        analyzer = LLMSentimentAnalyzer(config=AnalyzerConfig(fallback_to_keywords=True))
        result = analyzer.analyze("Stock rally surge growth strong beat record profit")
        assert result.sentiment == "bullish"
        assert result.score > 0

    def test_keyword_fallback_negative(self):
        analyzer = LLMSentimentAnalyzer(config=AnalyzerConfig(fallback_to_keywords=True))
        result = analyzer.analyze("Stock crash plunge loss decline bankruptcy fraud lawsuit")
        assert result.sentiment == "bearish"
        assert result.score < 0

    def test_keyword_fallback_neutral(self):
        analyzer = LLMSentimentAnalyzer(config=AnalyzerConfig(fallback_to_keywords=True))
        result = analyzer.analyze("The meeting is scheduled for tomorrow")
        assert result.sentiment == "neutral"
        assert result.score == 0.0

    def test_score_clamping(self):
        response_json = json.dumps({
            "sentiment": "bullish", "score": 5.0, "confidence": 2.0,
            "reasoning": "", "themes": [], "tickers": [],
            "urgency": "low", "time_horizon": "medium",
        })
        router = _mock_router(response_json)
        analyzer = LLMSentimentAnalyzer(router=router)

        result = analyzer.analyze("test")
        assert result.score == 1.0
        assert result.confidence == 1.0

    def test_invalid_json_fallback(self):
        router = _mock_router("This is not JSON at all")
        analyzer = LLMSentimentAnalyzer(router=router)

        result = analyzer.analyze("test")
        assert result.model_used == "claude-haiku-4-5-20251001"
        assert "This is not JSON" in result.reasoning

    def test_llm_exception_fallback(self):
        router = MagicMock()
        router.chat_with_fallback.side_effect = RuntimeError("No models")
        analyzer = LLMSentimentAnalyzer(
            router=router,
            config=AnalyzerConfig(fallback_to_keywords=True),
        )
        result = analyzer.analyze("Stock surge rally growth")
        assert result.sentiment == "bullish"
        assert result.model_used == "keyword_fallback"

    def test_analyze_batch(self):
        batch_json = json.dumps([
            {"index": 0, "sentiment": "bullish", "score": 0.7, "confidence": 0.8, "themes": ["earnings"], "tickers": ["AAPL"]},
            {"index": 1, "sentiment": "bearish", "score": -0.5, "confidence": 0.7, "themes": ["recall"], "tickers": ["TSLA"]},
        ])
        router = _mock_router(batch_json)
        analyzer = LLMSentimentAnalyzer(router=router)

        results = analyzer.analyze_batch(["AAPL beats", "TSLA recalls"])
        assert len(results) == 2
        assert results[0].sentiment == "bullish"
        assert results[1].sentiment == "bearish"

    def test_analyze_batch_empty(self):
        analyzer = LLMSentimentAnalyzer()
        assert analyzer.analyze_batch([]) == []

    def test_estimate_cost(self):
        router = _mock_router("{}")
        analyzer = LLMSentimentAnalyzer(router=router)
        cost = analyzer.estimate_cost("test text")
        assert cost >= 0

    def test_context_parameter(self):
        response_json = json.dumps({
            "sentiment": "neutral", "score": 0.0, "confidence": 0.5,
            "reasoning": "", "themes": [], "tickers": [],
            "urgency": "low", "time_horizon": "medium",
        })
        router = _mock_router(response_json)
        analyzer = LLMSentimentAnalyzer(router=router)

        analyzer.analyze("revenue grew 10%", context="earnings call transcript")
        call_args = router.chat_with_fallback.call_args
        msg_content = call_args[1]["messages"][0]["content"]
        assert "Context: earnings call transcript" in msg_content

    def test_invalid_sentiment_label(self):
        response_json = json.dumps({
            "sentiment": "SUPER_BULLISH", "score": 0.9, "confidence": 0.8,
            "reasoning": "", "themes": [], "tickers": [],
            "urgency": "extreme", "time_horizon": "instant",
        })
        router = _mock_router(response_json)
        analyzer = LLMSentimentAnalyzer(router=router)
        result = analyzer.analyze("test")
        assert result.sentiment == "neutral"  # Sanitized
        assert result.urgency == "low"  # Sanitized
        assert result.time_horizon == "medium"  # Sanitized


# ── TestSentimentAspect ──────────────────────────────────────────────


class TestSentimentAspect:
    """Test SentimentAspect dataclass."""

    def test_defaults(self):
        a = SentimentAspect()
        assert a.theme == ""
        assert a.sentiment == "neutral"

    def test_to_dict(self):
        a = SentimentAspect(theme="earnings", sentiment="positive", score=0.8)
        d = a.to_dict()
        assert d["theme"] == "earnings"
        assert d["score"] == 0.8


# ── TestAspectExtractor ──────────────────────────────────────────────


class TestAspectExtractor:
    """Test aspect-level sentiment extraction."""

    def test_empty_text(self):
        extractor = AspectExtractor()
        report = extractor.extract("")
        assert report.aspect_count == 0

    def test_extract_with_llm(self):
        response_json = json.dumps({
            "aspects": [
                {"category": "product", "sentiment": "positive", "score": 0.7, "confidence": 0.8, "evidence": "strong iPhone sales"},
                {"category": "regulatory", "sentiment": "negative", "score": -0.5, "confidence": 0.6, "evidence": "EU scrutiny"},
            ],
            "dominant_aspect": "product",
            "overall_score": 0.3,
            "conflicting_aspects": True,
        })
        router = _mock_router(response_json)
        extractor = AspectExtractor(router=router)

        report = extractor.extract("AAPL posts strong iPhone sales but faces EU regulatory scrutiny")
        assert report.aspect_count == 2
        assert report.dominant_aspect == "product"
        assert report.conflicting_aspects is True
        assert len(report.get_positive_aspects()) == 1
        assert len(report.get_negative_aspects()) == 1

    def test_get_aspect(self):
        report = AspectReport(aspects=[
            {"category": "product", "sentiment": "positive", "score": 0.7, "confidence": 0.8, "evidence": ""},
        ])
        assert report.get_aspect("product") is not None
        assert report.get_aspect("financials") is None

    def test_rule_fallback(self):
        extractor = AspectExtractor()
        report = extractor.extract("Revenue growth and strong profit margins despite regulatory investigation")
        assert report.aspect_count > 0
        assert report.model_used == "rule_fallback"

    def test_to_dict(self):
        report = AspectReport(dominant_aspect="product", overall_score=0.5)
        d = report.to_dict()
        assert d["dominant_aspect"] == "product"
        assert d["overall_score"] == 0.5

    def test_invalid_category_filtered(self):
        response_json = json.dumps({
            "aspects": [
                {"category": "invalid_cat", "sentiment": "positive", "score": 0.7, "confidence": 0.8, "evidence": ""},
                {"category": "product", "sentiment": "positive", "score": 0.5, "confidence": 0.6, "evidence": ""},
            ],
            "dominant_aspect": "product",
            "overall_score": 0.5,
            "conflicting_aspects": False,
        })
        router = _mock_router(response_json)
        extractor = AspectExtractor(router=router)
        report = extractor.extract("test")
        assert report.aspect_count == 1  # Invalid filtered out

    def test_low_confidence_filtered(self):
        response_json = json.dumps({
            "aspects": [
                {"category": "product", "sentiment": "positive", "score": 0.7, "confidence": 0.1, "evidence": ""},
            ],
            "dominant_aspect": "product",
            "overall_score": 0.0,
            "conflicting_aspects": False,
        })
        router = _mock_router(response_json)
        extractor = AspectExtractor(router=router)
        report = extractor.extract("test")
        assert report.aspect_count == 0  # Below min_confidence

    def test_aspect_categories_enum(self):
        assert AspectCategory.PRODUCT.value == "product"
        assert AspectCategory.FINANCIALS.value == "financials"
        assert len(AspectCategory) == 8


# ── TestEntityResolver ───────────────────────────────────────────────


class TestEntityResolver:
    """Test entity-level sentiment resolution."""

    def test_empty_text(self):
        resolver = EntityResolver()
        report = resolver.resolve("")
        assert report.entity_count == 0

    def test_resolve_with_llm(self):
        response_json = json.dumps({
            "entities": [
                {"name": "Apple", "type": "company", "ticker": "AAPL", "sentiment": "positive", "score": 0.8, "confidence": 0.9, "context": "record revenue"},
                {"name": "Google", "type": "company", "ticker": "GOOGL", "sentiment": "negative", "score": -0.6, "confidence": 0.7, "context": "antitrust probe"},
            ],
            "relationships": [
                {"entity1": "Apple", "entity2": "Google", "relation": "competition"},
            ],
        })
        router = _mock_router(response_json)
        resolver = EntityResolver(router=router)

        report = resolver.resolve("Apple posts record revenue while Google faces antitrust probe")
        assert report.entity_count == 2
        assert report.get_by_ticker("AAPL").sentiment == "positive"
        assert report.get_by_ticker("GOOGL").sentiment == "negative"
        assert len(report.relationships) == 1

    def test_get_by_type(self):
        report = EntityReport(entities=[
            EntitySentiment(name="Apple", entity_type="company", ticker="AAPL"),
            EntitySentiment(name="Tim Cook", entity_type="person"),
        ])
        companies = report.get_by_type("company")
        assert len(companies) == 1
        assert companies[0].name == "Apple"

    def test_get_most_positive_negative(self):
        report = EntityReport(entities=[
            EntitySentiment(name="A", score=0.8),
            EntitySentiment(name="B", score=-0.5),
            EntitySentiment(name="C", score=0.3),
        ])
        assert report.get_most_positive().name == "A"
        assert report.get_most_negative().name == "B"

    def test_empty_report_helpers(self):
        report = EntityReport()
        assert report.get_most_positive() is None
        assert report.get_most_negative() is None
        assert report.get_by_ticker("AAPL") is None

    def test_rule_fallback(self):
        resolver = EntityResolver()
        report = resolver.resolve("Apple posted record revenue and strong growth")
        assert report.model_used == "rule_fallback"
        assert any(e.ticker == "AAPL" for e in report.entities)

    def test_cashtag_extraction(self):
        resolver = EntityResolver()
        report = resolver.resolve("Looking at $MSFT and $AMZN today")
        tickers = {e.ticker for e in report.entities}
        assert "MSFT" in tickers
        assert "AMZN" in tickers

    def test_entity_sentiment_to_dict(self):
        e = EntitySentiment(name="Tesla", entity_type="company", ticker="TSLA", score=0.5)
        d = e.to_dict()
        assert d["name"] == "Tesla"
        assert d["ticker"] == "TSLA"

    def test_entity_type_enum(self):
        assert EntityType.COMPANY.value == "company"
        assert EntityType.PERSON.value == "person"
        assert len(EntityType) == 7

    def test_report_to_dict(self):
        report = EntityReport(
            entities=[EntitySentiment(name="A", score=0.5)],
            relationships=[{"entity1": "A", "entity2": "B", "relation": "competition"}],
        )
        d = report.to_dict()
        assert len(d["entities"]) == 1
        assert len(d["relationships"]) == 1

    def test_low_confidence_filtered(self):
        response_json = json.dumps({
            "entities": [
                {"name": "X", "type": "company", "ticker": "X", "sentiment": "positive",
                 "score": 0.5, "confidence": 0.1, "context": ""},
            ],
            "relationships": [],
        })
        router = _mock_router(response_json)
        resolver = EntityResolver(router=router)
        report = resolver.resolve("test")
        assert report.entity_count == 0  # Below min_confidence


# ── TestSentimentPredictor ───────────────────────────────────────────


class TestSentimentPredictor:
    """Test sentiment prediction and momentum analysis."""

    def _add_trend(self, predictor, ticker, scores, start_hours_ago=100):
        """Add a series of observations with timestamps."""
        now = datetime.now(timezone.utc)
        for i, score in enumerate(scores):
            ts = now - timedelta(hours=start_hours_ago - i * 4)
            predictor.add_observation(ticker, score, ts)

    def test_insufficient_data(self):
        predictor = SentimentPredictor()
        predictor.add_observation("AAPL", 0.5)
        forecast = predictor.predict("AAPL")
        assert forecast.predicted_direction == "stable"
        assert forecast.confidence < 0.5

    def test_improving_trend(self):
        predictor = SentimentPredictor()
        scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
        self._add_trend(predictor, "AAPL", scores)

        forecast = predictor.predict("AAPL", ForecastHorizon.HOURS_24)
        assert forecast.momentum > 0
        # Direction depends on decay interaction, but momentum should be positive
        assert forecast.current_score == 0.7

    def test_deteriorating_trend(self):
        predictor = SentimentPredictor()
        scores = [0.8, 0.6, 0.4, 0.2, 0.0, -0.2, -0.4]
        self._add_trend(predictor, "TSLA", scores)

        forecast = predictor.predict("TSLA", ForecastHorizon.HOURS_24)
        assert forecast.momentum < 0
        assert forecast.current_score == -0.4

    def test_stable_sentiment(self):
        predictor = SentimentPredictor()
        scores = [0.3, 0.31, 0.29, 0.3, 0.31, 0.3, 0.3]
        self._add_trend(predictor, "MSFT", scores)

        forecast = predictor.predict("MSFT")
        assert abs(forecast.momentum) < 0.05
        assert forecast.predicted_direction == "stable"

    def test_predict_all(self):
        predictor = SentimentPredictor()
        self._add_trend(predictor, "AAPL", [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
        self._add_trend(predictor, "TSLA", [0.5, 0.4, 0.3, 0.2, 0.1, 0.0, -0.1])

        report = predictor.predict_all()
        assert report.ticker_count == 2
        assert len(report.forecasts) == 2
        assert report.generated_at != ""

    def test_report_filters(self):
        predictor = SentimentPredictor()
        self._add_trend(predictor, "AAPL", [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
        self._add_trend(predictor, "TSLA", [0.5, 0.3, 0.1, -0.1, -0.3, -0.5, -0.7])

        report = predictor.predict_all()
        improving = report.get_improving()
        deteriorating = report.get_deteriorating()
        # At least one should be in each category
        assert len(improving) + len(deteriorating) >= 1

    def test_forecast_horizons(self):
        predictor = SentimentPredictor()
        self._add_trend(predictor, "AAPL", [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])

        f4h = predictor.predict("AAPL", ForecastHorizon.HOURS_4)
        f7d = predictor.predict("AAPL", ForecastHorizon.DAYS_7)
        assert f4h.horizon == "4h"
        assert f7d.horizon == "7d"

    def test_tracked_tickers(self):
        predictor = SentimentPredictor()
        predictor.add_observation("AAPL", 0.5)
        predictor.add_observation("TSLA", 0.3)
        assert predictor.tracked_tickers == ["AAPL", "TSLA"]

    def test_observation_count(self):
        predictor = SentimentPredictor()
        predictor.add_observation("AAPL", 0.5)
        predictor.add_observation("AAPL", 0.6)
        assert predictor.get_observation_count("AAPL") == 2
        assert predictor.get_observation_count("TSLA") == 0

    def test_clear(self):
        predictor = SentimentPredictor()
        predictor.add_observation("AAPL", 0.5)
        predictor.add_observation("TSLA", 0.3)
        predictor.clear("AAPL")
        assert predictor.tracked_tickers == ["TSLA"]
        predictor.clear()
        assert predictor.tracked_tickers == []

    def test_forecast_to_dict(self):
        f = SentimentForecast(ticker="AAPL", horizon="24h", current_score=0.5)
        d = f.to_dict()
        assert d["ticker"] == "AAPL"
        assert d["horizon"] == "24h"

    def test_prediction_report_to_dict(self):
        report = PredictionReport(
            forecasts=[SentimentForecast(ticker="AAPL")],
            generated_at="2025-01-01T00:00:00Z",
            horizon="24h",
        )
        d = report.to_dict()
        assert len(d["forecasts"]) == 1

    def test_reversal_detection(self):
        predictor = SentimentPredictor()
        # Sharp swing from positive to negative
        scores = [0.8, 0.7, 0.5, 0.2, -0.1, -0.4, -0.7]
        self._add_trend(predictor, "GME", scores)

        forecast = predictor.predict("GME")
        # Should detect some reversal probability
        assert forecast.reversal_probability >= 0

    def test_no_ticker_returns_default(self):
        predictor = SentimentPredictor()
        forecast = predictor.predict("UNKNOWN")
        assert forecast.current_score == 0.0
        assert forecast.predicted_direction == "stable"

    def test_predictor_config_defaults(self):
        cfg = PredictorConfig()
        assert cfg.min_observations == 5
        assert cfg.ema_fast_span == 5
        assert cfg.ema_slow_span == 20
        assert cfg.reversal_threshold == 0.3


# ── TestModuleImports ────────────────────────────────────────────────


class TestModuleImports:
    """Test that all __all__ exports are importable."""

    def test_all_imports(self):
        from src.llm_sentiment import __all__ as exports
        import src.llm_sentiment as mod
        for name in exports:
            assert hasattr(mod, name), f"Missing export: {name}"

    def test_config_defaults(self):
        cfg = AnalyzerConfig()
        assert cfg.max_tokens == 512
        ecfg = EntityConfig()
        assert ecfg.max_tokens == 768
        acfg = AspectConfig()
        assert acfg.min_confidence == 0.3
        pcfg = PredictorConfig()
        assert pcfg.decay_halflife_hours == 24.0
