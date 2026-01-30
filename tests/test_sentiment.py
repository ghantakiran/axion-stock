"""Tests for the Sentiment Intelligence module (PRD-07)."""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.sentiment.config import (
    SentimentConfig, NewsSentimentConfig, SocialMediaConfig,
    InsiderConfig, AnalystConfig, EarningsNLPConfig, CompositeConfig,
)
from src.sentiment.news import (
    NewsSentimentEngine, SentimentScore, Article,
)
from src.sentiment.social import (
    SocialMediaMonitor, TickerMention, SocialPost,
    TrendingAlert, SocialSentimentSummary,
)
from src.sentiment.insider import (
    InsiderTracker, InsiderFiling, InsiderReport,
)
from src.sentiment.analyst import (
    AnalystConsensusTracker, AnalystRating, EstimateRevision, ConsensusReport,
)
from src.sentiment.earnings import (
    EarningsCallAnalyzer, EarningsTranscript, CallAnalysis,
)
from src.sentiment.composite import (
    SentimentComposite, SentimentBreakdown,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def news_engine():
    return NewsSentimentEngine()


@pytest.fixture
def social_monitor():
    return SocialMediaMonitor()


@pytest.fixture
def insider_tracker():
    return InsiderTracker()


@pytest.fixture
def analyst_tracker():
    return AnalystConsensusTracker()


@pytest.fixture
def earnings_analyzer():
    return EarningsCallAnalyzer()


@pytest.fixture
def composite():
    return SentimentComposite()


@pytest.fixture
def sample_articles():
    return [
        Article(
            title="Apple Reports Record Revenue",
            summary="Apple exceeded analyst expectations with strong iPhone and services growth.",
            source="reuters",
            published_at=datetime.now().isoformat(),
            symbols=["AAPL"],
        ),
        Article(
            title="Tesla Faces Recall Concerns",
            summary="Tesla announces recall of 500K vehicles due to safety concerns. Stock declines.",
            source="bloomberg",
            published_at=(datetime.now() - timedelta(hours=2)).isoformat(),
            symbols=["TSLA"],
        ),
        Article(
            title="Fed Holds Interest Rates Steady",
            summary="The Federal Reserve maintained rates as expected amid inflation uncertainty.",
            source="reuters",
            published_at=(datetime.now() - timedelta(hours=5)).isoformat(),
        ),
    ]


@pytest.fixture
def sample_social_posts():
    return [
        SocialPost(
            text="AAPL to the moon! Record earnings beat, bullish AF",
            source="reddit", tickers=["AAPL"], sentiment=0.8,
            upvotes=500, comments=120,
        ),
        SocialPost(
            text="AAPL looking strong, buying more calls",
            source="twitter", tickers=["AAPL"], sentiment=0.6,
            upvotes=200, comments=50,
        ),
        SocialPost(
            text="TSLA crash incoming, overvalued junk",
            source="reddit", tickers=["TSLA"], sentiment=-0.7,
            upvotes=300, comments=200,
        ),
        SocialPost(
            text="NVDA AI dominance continues, long and strong",
            source="stocktwits", tickers=["NVDA"], sentiment=0.9,
            upvotes=150, comments=30,
        ),
    ]


@pytest.fixture
def sample_filings():
    now = datetime.now()
    return [
        InsiderFiling(
            symbol="AAPL", insider_name="Tim Cook", insider_title="CEO",
            transaction_type="P", shares=50000, price=180.0,
            value=9_000_000, filing_date=(now - timedelta(days=5)).isoformat(),
        ),
        InsiderFiling(
            symbol="AAPL", insider_name="Luca Maestri", insider_title="CFO",
            transaction_type="S", shares=40000, price=182.0,
            value=7_280_000, filing_date=(now - timedelta(days=10)).isoformat(),
            is_10b5_1=True,
        ),
        InsiderFiling(
            symbol="AAPL", insider_name="Board Member A", insider_title="Director",
            transaction_type="P", shares=5000, price=178.0,
            value=890_000, filing_date=(now - timedelta(days=15)).isoformat(),
        ),
        InsiderFiling(
            symbol="AAPL", insider_name="Board Member B", insider_title="Director",
            transaction_type="P", shares=3000, price=179.0,
            value=537_000, filing_date=(now - timedelta(days=20)).isoformat(),
        ),
    ]


@pytest.fixture
def sample_ratings():
    return [
        AnalystRating(analyst_name="Analyst A", firm="Goldman Sachs",
                     rating="buy", target_price=200.0, previous_rating="hold",
                     date=datetime.now().isoformat()),
        AnalystRating(analyst_name="Analyst B", firm="Morgan Stanley",
                     rating="strong_buy", target_price=210.0, previous_rating="buy",
                     date=datetime.now().isoformat()),
        AnalystRating(analyst_name="Analyst C", firm="JPMorgan",
                     rating="buy", target_price=195.0, previous_rating="buy",
                     date=datetime.now().isoformat()),
        AnalystRating(analyst_name="Analyst D", firm="Barclays",
                     rating="hold", target_price=180.0, previous_rating="hold",
                     date=datetime.now().isoformat()),
    ]


@pytest.fixture
def sample_transcript():
    return EarningsTranscript(
        symbol="AAPL",
        quarter="Q4_2025",
        date="2026-01-25",
        prepared_remarks=(
            "We delivered record revenue this quarter driven by strong growth "
            "in our services segment. We are confident in our outlook and expect "
            "continued momentum. Our innovative products are performing exceptionally "
            "well across all geographic markets. We are raising guidance for next quarter."
        ),
        qa_section=(
            "Regarding your question about margins, we anticipate improvement "
            "driven by efficiency gains. The competitive landscape remains challenging "
            "but we are well positioned. We expect revenue growth to accelerate "
            "as our new AI features expand globally."
        ),
    )


# =============================================================================
# Config Tests
# =============================================================================

class TestSentimentConfig:

    def test_default_config(self):
        config = SentimentConfig()
        assert config.news.default_window_hours == 24
        assert config.social.mention_lookback_hours == 24
        assert config.insider.cluster_min_insiders == 3
        assert config.analyst.min_analysts == 3
        assert config.composite.min_sources_required == 2

    def test_composite_weights_sum(self):
        config = CompositeConfig()
        total = sum(config.weights.values())
        assert abs(total - 1.0) < 0.01

    def test_news_source_credibility(self):
        config = NewsSentimentConfig()
        assert config.source_credibility["reuters"] > config.source_credibility["seeking_alpha"]


# =============================================================================
# News Sentiment Tests
# =============================================================================

class TestNewsSentimentEngine:

    def test_score_positive_article(self, news_engine, sample_articles):
        score = news_engine.score_article(sample_articles[0])
        assert isinstance(score, SentimentScore)
        assert score.score > 0  # "Record Revenue" + "exceeded" = positive
        assert score.sentiment == "positive"

    def test_score_negative_article(self, news_engine, sample_articles):
        score = news_engine.score_article(sample_articles[1])
        assert score.score < 0  # "recall", "concern", "decline"
        assert score.sentiment == "negative"

    def test_score_preserves_symbols(self, news_engine, sample_articles):
        score = news_engine.score_article(sample_articles[0])
        assert "AAPL" in score.symbols

    def test_score_empty_article(self, news_engine):
        article = Article(title="", summary="")
        score = news_engine.score_article(article)
        assert score.score == 0.0
        assert score.sentiment == "neutral"

    def test_extract_tickers_cashtag(self, news_engine):
        text = "Watching $AAPL and $MSFT today, both looking strong"
        tickers = news_engine.extract_tickers(text)
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    def test_extract_tickers_known(self, news_engine):
        text = "NVDA continues to dominate the AI chip market"
        tickers = news_engine.extract_tickers(text)
        assert "NVDA" in tickers

    def test_extract_tickers_excludes_common_words(self, news_engine):
        text = "The CEO said AI is important for the US economy"
        tickers = news_engine.extract_tickers(text)
        assert "CEO" not in tickers
        assert "THE" not in tickers

    def test_classify_topic_earnings(self, news_engine):
        topic = news_engine.classify_topic("Apple reports Q4 earnings beat, EPS exceeds estimates")
        assert topic == "earnings"

    def test_classify_topic_merger(self, news_engine):
        topic = news_engine.classify_topic("Microsoft announces acquisition of gaming company")
        assert topic == "merger_acquisition"

    def test_classify_topic_macro(self, news_engine):
        topic = news_engine.classify_topic("Fed raises interest rate amid inflation concerns")
        assert topic == "macro"

    def test_aggregate_sentiment(self, news_engine, sample_articles):
        scores = [news_engine.score_article(a) for a in sample_articles]
        agg = news_engine.aggregate_sentiment(scores)
        assert -1.0 <= agg <= 1.0

    def test_aggregate_empty(self, news_engine):
        assert news_engine.aggregate_sentiment([]) == 0.0

    def test_score_text_direct(self, news_engine):
        result = news_engine.score_text("Stock surges on strong earnings beat and revenue growth")
        assert result["score"] > 0

    def test_sentiment_score_to_dict(self):
        score = SentimentScore(sentiment="positive", score=0.7, symbols=["AAPL"])
        d = score.to_dict()
        assert d["sentiment"] == "positive"
        assert d["score"] == 0.7


# =============================================================================
# Social Media Tests
# =============================================================================

class TestSocialMediaMonitor:

    def test_process_posts(self, social_monitor, sample_social_posts):
        mentions = social_monitor.process_posts(sample_social_posts)
        assert "AAPL" in mentions
        assert "TSLA" in mentions
        assert mentions["AAPL"].count == 2
        assert mentions["TSLA"].count == 1

    def test_mention_sentiment(self, social_monitor, sample_social_posts):
        mentions = social_monitor.process_posts(sample_social_posts)
        assert mentions["AAPL"].avg_sentiment > 0
        assert mentions["TSLA"].avg_sentiment < 0

    def test_mention_engagement(self, social_monitor, sample_social_posts):
        mentions = social_monitor.process_posts(sample_social_posts)
        assert mentions["AAPL"].engagement > 0
        assert mentions["AAPL"].total_upvotes == 700  # 500 + 200

    def test_detect_trending(self, social_monitor):
        current = {"AAPL": 500, "MSFT": 100, "GME": 5000}
        historical = {"AAPL": 200, "MSFT": 90, "GME": 50}
        alerts = social_monitor.detect_trending(current, historical)
        # GME: 5000/50 = 100x (trending), AAPL: 500/200 = 2.5x (not 3x)
        trending_symbols = [a.symbol for a in alerts]
        assert "GME" in trending_symbols

    def test_detect_mention_spike(self, social_monitor):
        # Create time series with spike
        ts = pd.Series([10, 12, 11, 15, 13, 100])  # Last value is spike
        assert social_monitor.detect_mention_spike(ts) is True

    def test_detect_no_spike(self, social_monitor):
        ts = pd.Series([10, 12, 11, 15, 13, 14])
        assert social_monitor.detect_mention_spike(ts) is False

    def test_get_symbol_summary(self, social_monitor, sample_social_posts):
        summary = social_monitor.get_symbol_summary("AAPL", sample_social_posts)
        assert isinstance(summary, SocialSentimentSummary)
        assert summary.total_mentions == 2
        assert summary.composite_sentiment > 0

    def test_rank_by_buzz(self, social_monitor, sample_social_posts):
        mentions = social_monitor.process_posts(sample_social_posts)
        ranked = social_monitor.rank_by_buzz(mentions, top_n=5)
        assert len(ranked) > 0
        # AAPL should rank high (2 mentions, high engagement)
        assert ranked[0].symbol == "AAPL"

    def test_ticker_mention_to_dict(self):
        m = TickerMention(symbol="AAPL", count=10, total_upvotes=500, total_comments=100)
        d = m.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["engagement"] == 600


# =============================================================================
# Insider Tracker Tests
# =============================================================================

class TestInsiderTracker:

    def test_analyze_filings(self, insider_tracker, sample_filings):
        report = insider_tracker.analyze(sample_filings)
        assert isinstance(report, InsiderReport)
        assert report.symbol == "AAPL"
        assert report.buy_count == 3
        assert report.sell_count == 1
        assert report.net_shares > 0  # More bought than sold

    def test_cluster_buy_detection(self, insider_tracker, sample_filings):
        report = insider_tracker.analyze(sample_filings)
        # 3 buyers within 30 days -> cluster buy
        assert report.cluster_buy is True

    def test_ceo_activity(self, insider_tracker, sample_filings):
        report = insider_tracker.analyze(sample_filings)
        assert len(report.ceo_activity) >= 1  # CEO and CFO
        assert any("Tim Cook" in a for a in report.ceo_activity)

    def test_insider_score_positive(self, insider_tracker, sample_filings):
        report = insider_tracker.analyze(sample_filings)
        # Net buying with cluster should be positive
        assert report.insider_score > 0

    def test_insider_score_negative(self, insider_tracker):
        sells = [
            InsiderFiling(symbol="XYZ", insider_name=f"Exec {i}",
                         insider_title="VP", transaction_type="S",
                         shares=10000, price=50.0, value=500_000,
                         filing_date=(datetime.now() - timedelta(days=i*5)).isoformat())
            for i in range(5)
        ]
        report = insider_tracker.analyze(sells)
        assert report.insider_score < 0

    def test_empty_filings(self, insider_tracker):
        report = insider_tracker.analyze([])
        assert report.buy_count == 0
        assert report.sell_count == 0

    def test_10b5_1_low_signal(self, insider_tracker):
        # 10b5-1 planned sales should have minimal negative impact
        filings = [
            InsiderFiling(symbol="ABC", insider_name="CEO",
                         insider_title="CEO", transaction_type="S",
                         shares=10000, price=100.0, value=1_000_000,
                         filing_date=datetime.now().isoformat(), is_10b5_1=True),
        ]
        report = insider_tracker.analyze(filings)
        # Score should be only slightly negative
        assert report.insider_score > -0.5

    def test_report_to_dict(self, insider_tracker, sample_filings):
        report = insider_tracker.analyze(sample_filings)
        d = report.to_dict()
        assert "insider_score" in d
        assert "cluster_buy" in d


# =============================================================================
# Analyst Consensus Tests
# =============================================================================

class TestAnalystConsensus:

    def test_compute_consensus(self, analyst_tracker, sample_ratings):
        report = analyst_tracker.compute_consensus(
            sample_ratings, current_price=180.0, symbol="AAPL"
        )
        assert isinstance(report, ConsensusReport)
        assert report.num_analysts == 4
        assert report.buy_count == 3  # 2 buy + 1 strong_buy
        assert report.hold_count == 1

    def test_consensus_rating(self, analyst_tracker, sample_ratings):
        report = analyst_tracker.compute_consensus(sample_ratings, current_price=180.0)
        # Majority buy -> consensus should be buy
        assert report.consensus_rating in ("buy", "strong_buy")
        assert report.consensus_score > 0

    def test_price_targets(self, analyst_tracker, sample_ratings):
        report = analyst_tracker.compute_consensus(sample_ratings, current_price=180.0)
        assert report.target_price_mean > 0
        assert report.target_price_high >= report.target_price_mean
        assert report.target_price_low <= report.target_price_mean
        assert report.upside_pct > 0  # Target above current

    def test_revision_momentum(self, analyst_tracker):
        revisions = [
            EstimateRevision(revision_pct=0.05, date=datetime.now().isoformat()),
            EstimateRevision(revision_pct=0.03, date=datetime.now().isoformat()),
            EstimateRevision(revision_pct=-0.01, date=datetime.now().isoformat()),
        ]
        momentum = analyst_tracker.compute_revision_momentum(revisions)
        assert momentum > 0  # Net positive revisions

    def test_revision_breadth(self, analyst_tracker):
        revisions = [
            EstimateRevision(revision_pct=0.05),
            EstimateRevision(revision_pct=0.03),
            EstimateRevision(revision_pct=-0.01),
            EstimateRevision(revision_pct=0.02),
        ]
        breadth = analyst_tracker.compute_revision_breadth(revisions)
        assert breadth == 0.75  # 3/4 up

    def test_rating_changes(self, analyst_tracker, sample_ratings):
        changes = analyst_tracker.get_rating_changes(sample_ratings)
        assert changes["upgrades"] == 2  # hold->buy and buy->strong_buy
        assert changes["net"] > 0

    def test_empty_ratings(self, analyst_tracker):
        report = analyst_tracker.compute_consensus([])
        assert report.num_analysts == 0
        assert report.consensus_score == 0.0

    def test_report_to_dict(self, analyst_tracker, sample_ratings):
        report = analyst_tracker.compute_consensus(sample_ratings, current_price=180.0)
        d = report.to_dict()
        assert "consensus_rating" in d
        assert "upside_pct" in d


# =============================================================================
# Earnings Call NLP Tests
# =============================================================================

class TestEarningsCallAnalyzer:

    def test_analyze_transcript(self, earnings_analyzer, sample_transcript):
        analysis = earnings_analyzer.analyze(sample_transcript)
        assert isinstance(analysis, CallAnalysis)
        assert analysis.symbol == "AAPL"
        assert analysis.quarter == "Q4_2025"

    def test_management_tone_positive(self, earnings_analyzer, sample_transcript):
        analysis = earnings_analyzer.analyze(sample_transcript)
        # Transcript is mostly positive
        assert analysis.management_tone > 0

    def test_guidance_raised(self, earnings_analyzer, sample_transcript):
        analysis = earnings_analyzer.analyze(sample_transcript)
        assert analysis.guidance_direction == "raised"

    def test_forward_looking_count(self, earnings_analyzer, sample_transcript):
        analysis = earnings_analyzer.analyze(sample_transcript)
        assert analysis.forward_looking_count > 0

    def test_key_topics(self, earnings_analyzer, sample_transcript):
        analysis = earnings_analyzer.analyze(sample_transcript)
        assert len(analysis.key_topics) > 0
        assert "guidance" in analysis.key_topics

    def test_confidence_score(self, earnings_analyzer, sample_transcript):
        analysis = earnings_analyzer.analyze(sample_transcript)
        assert 0 <= analysis.confidence_score <= 1

    def test_fog_index(self, earnings_analyzer, sample_transcript):
        analysis = earnings_analyzer.analyze(sample_transcript)
        assert analysis.fog_index > 0

    def test_overall_score(self, earnings_analyzer, sample_transcript):
        analysis = earnings_analyzer.analyze(sample_transcript)
        assert -1 <= analysis.overall_score <= 1
        # Positive transcript should have positive overall score
        assert analysis.overall_score > 0

    def test_compare_quarters(self, earnings_analyzer):
        current = CallAnalysis(management_tone=0.6, qa_sentiment=0.4, confidence_score=0.7,
                              uncertainty_count=3, forward_looking_count=10)
        previous = CallAnalysis(management_tone=0.3, qa_sentiment=0.2, confidence_score=0.5,
                               uncertainty_count=5, forward_looking_count=8)
        comparison = earnings_analyzer.compare_quarters(current, previous)
        assert comparison["tone_change"] > 0
        assert comparison["tone_improving"] is True
        assert comparison["uncertainty_change"] < 0  # Fewer uncertain words

    def test_empty_transcript(self, earnings_analyzer):
        transcript = EarningsTranscript(symbol="XYZ", quarter="Q1_2026")
        analysis = earnings_analyzer.analyze(transcript)
        assert analysis.management_tone == 0.0
        assert analysis.word_count == 0

    def test_negative_transcript(self, earnings_analyzer):
        transcript = EarningsTranscript(
            symbol="BAD",
            quarter="Q1_2026",
            prepared_remarks="We face challenging conditions with declining revenue. "
                            "Risk factors are concerning and the outlook is uncertain. "
                            "Weak demand and difficult competitive pressures continue.",
        )
        analysis = earnings_analyzer.analyze(transcript)
        assert analysis.management_tone < 0

    def test_analysis_to_dict(self, earnings_analyzer, sample_transcript):
        analysis = earnings_analyzer.analyze(sample_transcript)
        d = analysis.to_dict()
        assert "management_tone" in d
        assert "guidance_direction" in d


# =============================================================================
# Composite Sentiment Tests
# =============================================================================

class TestSentimentComposite:

    def test_compute_composite(self, composite):
        scores = {
            "news_sentiment": 0.6,
            "social_sentiment": 0.8,
            "insider_signal": 0.3,
            "analyst_revision": 0.5,
            "earnings_tone": 0.4,
            "options_flow": 0.7,
        }
        result = composite.compute("AAPL", scores)
        assert isinstance(result, SentimentBreakdown)
        assert result.composite_score > 0
        assert result.sources_available == 6
        assert result.confidence == "high"

    def test_partial_sources(self, composite):
        scores = {
            "news_sentiment": 0.5,
            "insider_signal": -0.3,
        }
        result = composite.compute("AAPL", scores)
        assert result.sources_available == 2
        assert result.confidence in ("low", "medium")

    def test_insufficient_sources(self, composite):
        scores = {"news_sentiment": 0.5}
        result = composite.compute("AAPL", scores)
        assert result.composite_score == 0.0  # Not enough sources

    def test_none_values_ignored(self, composite):
        scores = {
            "news_sentiment": 0.5,
            "social_sentiment": None,
            "insider_signal": 0.3,
            "analyst_revision": None,
        }
        result = composite.compute("AAPL", scores)
        assert result.sources_available == 2

    def test_normalized_range(self, composite):
        scores = {"news_sentiment": 1.0, "social_sentiment": 1.0, "insider_signal": 1.0}
        result = composite.compute("AAPL", scores)
        assert 0 <= result.composite_normalized <= 1

    def test_compute_batch(self, composite):
        batch = {
            "AAPL": {"news_sentiment": 0.6, "social_sentiment": 0.8, "insider_signal": 0.4},
            "TSLA": {"news_sentiment": -0.3, "social_sentiment": 0.5, "insider_signal": -0.2},
        }
        results = composite.compute_batch(batch)
        assert "AAPL" in results
        assert "TSLA" in results
        assert results["AAPL"].composite_score > results["TSLA"].composite_score

    def test_rank_symbols(self, composite):
        batch = {
            "AAPL": {"news_sentiment": 0.6, "social_sentiment": 0.8, "insider_signal": 0.4},
            "TSLA": {"news_sentiment": -0.3, "social_sentiment": 0.1, "insider_signal": -0.2},
            "NVDA": {"news_sentiment": 0.9, "social_sentiment": 0.9, "insider_signal": 0.7},
        }
        results = composite.compute_batch(batch)
        ranking = composite.rank_symbols(results)
        assert isinstance(ranking, pd.DataFrame)
        assert ranking.iloc[0]["symbol"] == "NVDA"

    def test_compute_factor_score(self, composite):
        batch = {
            "AAPL": {"news_sentiment": 0.6, "social_sentiment": 0.8, "insider_signal": 0.4},
            "TSLA": {"news_sentiment": -0.3, "social_sentiment": 0.1, "insider_signal": -0.2},
            "NVDA": {"news_sentiment": 0.9, "social_sentiment": 0.9, "insider_signal": 0.7},
        }
        results = composite.compute_batch(batch)
        factor = composite.compute_factor_score(results)
        assert isinstance(factor, pd.Series)
        assert len(factor) == 3
        # All values should be 0-1
        assert factor.min() >= 0
        assert factor.max() <= 1

    def test_sentiment_regime(self, composite):
        batch = {
            "AAPL": {"news_sentiment": 0.6, "social_sentiment": 0.8, "insider_signal": 0.4},
            "MSFT": {"news_sentiment": 0.5, "social_sentiment": 0.6, "insider_signal": 0.3},
            "NVDA": {"news_sentiment": 0.9, "social_sentiment": 0.9, "insider_signal": 0.7},
        }
        results = composite.compute_batch(batch)
        regime = composite.get_sentiment_regime(results)
        assert regime["regime"] in ("bullish", "extreme_bullish")
        assert regime["avg_score"] > 0

    def test_breakdown_to_dict(self, composite):
        scores = {"news_sentiment": 0.5, "insider_signal": 0.3}
        result = composite.compute("AAPL", scores)
        d = result.to_dict()
        assert "composite_score" in d
        assert "confidence" in d


# =============================================================================
# Integration Tests
# =============================================================================

class TestSentimentIntegration:

    def test_full_workflow(self, news_engine, social_monitor, insider_tracker,
                           analyst_tracker, earnings_analyzer, composite,
                           sample_articles, sample_social_posts, sample_filings,
                           sample_ratings, sample_transcript):
        """Full pipeline: individual signals -> composite score."""
        # 1. News sentiment
        news_scores = [news_engine.score_article(a) for a in sample_articles
                       if "AAPL" in a.symbols]
        news_agg = news_engine.aggregate_sentiment(news_scores) if news_scores else 0.0

        # 2. Social sentiment
        aapl_summary = social_monitor.get_symbol_summary("AAPL", sample_social_posts)

        # 3. Insider signal
        insider_report = insider_tracker.analyze(sample_filings)

        # 4. Analyst consensus
        consensus = analyst_tracker.compute_consensus(sample_ratings, current_price=180.0)

        # 5. Earnings tone
        earnings = earnings_analyzer.analyze(sample_transcript)

        # 6. Composite
        result = composite.compute("AAPL", {
            "news_sentiment": news_agg,
            "social_sentiment": aapl_summary.composite_sentiment,
            "insider_signal": insider_report.insider_score,
            "analyst_revision": consensus.consensus_score,
            "earnings_tone": earnings.overall_score,
        })

        assert result.sources_available >= 4
        assert -1 <= result.composite_score <= 1
        assert result.confidence in ("medium", "high")

    def test_module_imports(self):
        """Verify all public API imports work."""
        from src.sentiment import (
            SentimentConfig,
            NewsSentimentEngine,
            SocialMediaMonitor,
            InsiderTracker,
            AnalystConsensusTracker,
            EarningsCallAnalyzer,
            SentimentComposite,
        )
        assert SentimentConfig is not None
        assert NewsSentimentEngine is not None
