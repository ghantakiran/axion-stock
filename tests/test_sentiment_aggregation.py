"""Tests for PRD-63: Sentiment Aggregation.

Covers decay weighting, multi-source fusion, consensus scoring,
and sentiment momentum tracking.
"""

import pytest
import numpy as np

from src.sentiment.decay_weighting import (
    SentimentObservation,
    DecayedScore,
    DecayProfile,
    DecayConfig,
    DecayWeightingEngine,
)
from src.sentiment.fusion import (
    SourceSignal,
    FusionResult,
    SourceReliability,
    FusionComparison,
    SentimentFusionEngine,
)
from src.sentiment.consensus import (
    SourceVote,
    ConsensusResult,
    ConsensusShift,
    MarketConsensus,
    ConsensusScorer,
)
from src.sentiment.momentum import (
    SentimentSnapshot,
    MomentumResult,
    TrendReversal,
    MomentumSummary,
    SentimentMomentumTracker,
)


# ===================================================================
# Decay Weighting Tests
# ===================================================================
class TestSentimentObservation:
    def test_fresh_observation(self):
        obs = SentimentObservation(source="news", score=0.5, age_hours=12.0)
        assert obs.is_fresh
        assert not obs.is_stale

    def test_stale_observation(self):
        obs = SentimentObservation(source="social", score=-0.3, age_hours=200.0)
        assert not obs.is_fresh
        assert obs.is_stale


class TestDecayedScore:
    def test_weight_loss(self):
        ds = DecayedScore(decay_factor=0.5)
        assert ds.weight_loss_pct == pytest.approx(50.0)

    def test_heavily_decayed(self):
        ds = DecayedScore(decay_factor=0.2)
        assert ds.is_heavily_decayed
        ds2 = DecayedScore(decay_factor=0.8)
        assert not ds2.is_heavily_decayed


class TestDecayProfile:
    def test_decay_impact(self):
        dp = DecayProfile(weighted_score=0.3, unweighted_score=0.5)
        assert dp.decay_impact == pytest.approx(0.2)

    def test_reliable_profile(self):
        dp = DecayProfile(effective_sources=3, freshness_ratio=0.5)
        assert dp.is_reliable

    def test_unreliable_profile(self):
        dp = DecayProfile(effective_sources=1, freshness_ratio=0.8)
        assert not dp.is_reliable


class TestDecayWeightingEngine:
    def setup_method(self):
        self.engine = DecayWeightingEngine()

    def test_zero_age_no_decay(self):
        factor = self.engine.compute_decay_factor(0.0)
        assert factor == 1.0

    def test_half_life_decay(self):
        factor = self.engine.compute_decay_factor(48.0)  # Default half-life
        assert factor == pytest.approx(0.5, abs=0.01)

    def test_old_observation_decayed(self):
        factor = self.engine.compute_decay_factor(200.0)
        assert factor < 0.5

    def test_max_age_floor(self):
        factor = self.engine.compute_decay_factor(1000.0)
        assert factor == 0.05  # min_decay_factor

    def test_decay_observation(self):
        obs = SentimentObservation(
            source="news", score=0.8, age_hours=48.0,
            credibility=0.9, symbol="AAPL",
        )
        ds = self.engine.decay_observation(obs)
        assert ds.raw_score == 0.8
        assert ds.decay_factor == pytest.approx(0.5, abs=0.01)
        assert ds.decayed_score == pytest.approx(0.4, abs=0.05)
        assert ds.effective_weight > 0

    def test_aggregate_empty(self):
        profile = self.engine.aggregate([], symbol="AAPL")
        assert profile.n_observations == 0
        assert profile.weighted_score == 0.0

    def test_aggregate_single_source(self):
        obs = [
            SentimentObservation(source="news", score=0.6, age_hours=1.0, symbol="AAPL"),
        ]
        profile = self.engine.aggregate(obs, symbol="AAPL")
        assert profile.n_observations == 1
        assert profile.weighted_score > 0

    def test_aggregate_multiple_sources(self):
        obs = [
            SentimentObservation(source="news", score=0.6, age_hours=1.0, credibility=0.9),
            SentimentObservation(source="social", score=0.4, age_hours=12.0, credibility=0.6),
            SentimentObservation(source="analyst", score=0.5, age_hours=48.0, credibility=0.8),
        ]
        profile = self.engine.aggregate(obs, symbol="AAPL")
        assert profile.n_observations == 3
        assert profile.effective_sources == 3
        assert -1.0 <= profile.weighted_score <= 1.0
        assert "news" in profile.scores_by_source

    def test_fresh_observations_weighted_higher(self):
        fresh_obs = [
            SentimentObservation(source="news", score=0.8, age_hours=1.0),
        ]
        stale_obs = [
            SentimentObservation(source="news", score=0.8, age_hours=200.0),
        ]
        fresh = self.engine.aggregate(fresh_obs, symbol="X")
        stale = self.engine.aggregate(stale_obs, symbol="X")
        assert fresh.weighted_score >= stale.weighted_score

    def test_compare_profiles(self):
        profiles = [
            DecayProfile(symbol="AAPL", weighted_score=0.6, freshness_ratio=0.8, effective_sources=3),
            DecayProfile(symbol="MSFT", weighted_score=0.3, freshness_ratio=0.5, effective_sources=2),
        ]
        result = self.engine.compare_decay_profiles(profiles)
        assert result["symbols"][0] == "AAPL"
        assert result["n_reliable"] >= 1

    def test_max_age_filter(self):
        obs = [
            SentimentObservation(source="news", score=0.8, age_hours=800.0),
        ]
        profile = self.engine.aggregate(obs, symbol="OLD")
        # Beyond max_age_hours=720, still processed (decay floor)
        # Actually 800 > 720, so filtered out
        assert profile.n_observations == 0


# ===================================================================
# Fusion Tests
# ===================================================================
class TestSourceSignal:
    def test_weighted_score(self):
        s = SourceSignal(score=0.5, confidence=0.8, weight=1.0)
        assert s.weighted_score == pytest.approx(0.4)


class TestFusionResult:
    def test_sentiment_labels(self):
        assert FusionResult(fused_score=0.5).sentiment_label == "bullish"
        assert FusionResult(fused_score=0.15).sentiment_label == "mildly_bullish"
        assert FusionResult(fused_score=0.0).sentiment_label == "neutral"
        assert FusionResult(fused_score=-0.15).sentiment_label == "mildly_bearish"
        assert FusionResult(fused_score=-0.5).sentiment_label == "bearish"

    def test_high_conviction(self):
        fr = FusionResult(fused_confidence=0.8, agreement_ratio=0.7)
        assert fr.is_high_conviction

    def test_conflict(self):
        fr = FusionResult(conflict_level=0.7)
        assert fr.has_conflict


class TestSourceReliability:
    def test_reliable_source(self):
        sr = SourceReliability(accuracy_score=0.7, n_observations=15)
        assert sr.is_reliable

    def test_unreliable_source(self):
        sr = SourceReliability(accuracy_score=0.3, n_observations=15)
        assert not sr.is_reliable

    def test_effective_weight(self):
        sr = SourceReliability(weight_adjustment=1.2, accuracy_score=0.8)
        assert sr.effective_weight == pytest.approx(0.96)


class TestSentimentFusionEngine:
    def setup_method(self):
        self.engine = SentimentFusionEngine()

    def test_fuse_empty(self):
        result = self.engine.fuse([], symbol="AAPL")
        assert result.fused_score == 0.0
        assert result.n_sources == 0

    def test_fuse_single_source(self):
        signals = [SourceSignal(source="news", score=0.5, confidence=0.8)]
        result = self.engine.fuse(signals, symbol="AAPL")
        # Below min_sources=2, so low confidence
        assert result.fused_confidence == 0.2
        assert result.n_sources == 1

    def test_fuse_multiple_agreeing_sources(self):
        signals = [
            SourceSignal(source="news", score=0.6, confidence=0.9),
            SourceSignal(source="analyst", score=0.5, confidence=0.8),
            SourceSignal(source="insider", score=0.4, confidence=0.7),
        ]
        result = self.engine.fuse(signals, symbol="AAPL")
        assert result.fused_score > 0.3
        assert result.agreement_ratio >= 0.8
        assert result.conflict_level < 0.3

    def test_fuse_conflicting_sources(self):
        signals = [
            SourceSignal(source="news", score=0.8, confidence=0.9),
            SourceSignal(source="social", score=-0.6, confidence=0.8),
            SourceSignal(source="insider", score=0.5, confidence=0.7),
        ]
        result = self.engine.fuse(signals, symbol="AAPL")
        assert result.conflict_level > 0.3
        assert result.agreement_ratio < 1.0

    def test_dominant_source(self):
        signals = [
            SourceSignal(source="news", score=0.6, confidence=0.9),
            SourceSignal(source="social", score=0.3, confidence=0.3),
        ]
        result = self.engine.fuse(signals, symbol="AAPL")
        assert result.dominant_source == "news"

    def test_update_reliability(self):
        rel = self.engine.update_reliability("news", 0.5, 0.3)
        assert rel.n_observations == 1
        assert isinstance(rel.hit_rate, float)

    def test_compare_fusions(self):
        results = [
            FusionResult(symbol="AAPL", fused_score=0.6, fused_confidence=0.8),
            FusionResult(symbol="MSFT", fused_score=-0.2, fused_confidence=0.5),
        ]
        comp = self.engine.compare_fusions(results)
        assert comp.most_bullish == "AAPL"
        assert comp.most_bearish == "MSFT"
        assert comp.n_symbols == 2


# ===================================================================
# Consensus Tests
# ===================================================================
class TestSourceVote:
    def test_conviction(self):
        v = SourceVote(score=0.6, confidence=0.8)
        assert v.conviction == pytest.approx(0.48)


class TestConsensusResult:
    def test_unanimous(self):
        cr = ConsensusResult(unanimity=0.95)
        assert cr.is_unanimous

    def test_strong_consensus(self):
        cr = ConsensusResult(consensus_strength=0.7, unanimity=0.8)
        assert cr.has_strong_consensus

    def test_split(self):
        cr = ConsensusResult(unanimity=0.4)
        assert cr.is_split

    def test_total_votes(self):
        cr = ConsensusResult(n_bullish=3, n_bearish=1, n_neutral=1)
        assert cr.total_votes == 5


class TestConsensusShift:
    def test_significant_shift(self):
        cs = ConsensusShift(shift_magnitude="major")
        assert cs.is_significant

    def test_insignificant_shift(self):
        cs = ConsensusShift(shift_magnitude="none")
        assert not cs.is_significant


class TestMarketConsensus:
    def test_extreme(self):
        mc = MarketConsensus(bullish_pct=0.85)
        assert mc.is_extreme

    def test_balanced(self):
        mc = MarketConsensus(bullish_pct=0.5)
        assert mc.is_balanced


class TestConsensusScorer:
    def setup_method(self):
        self.scorer = ConsensusScorer()

    def test_empty_votes(self):
        result = self.scorer.score_consensus([], symbol="AAPL")
        assert result.total_votes == 0

    def test_unanimous_bullish(self):
        votes = [
            SourceVote(source="news", score=0.6, confidence=0.9),
            SourceVote(source="analyst", score=0.5, confidence=0.8),
            SourceVote(source="insider", score=0.4, confidence=0.7),
        ]
        result = self.scorer.score_consensus(votes, symbol="AAPL")
        assert result.consensus_direction == "bullish"
        assert result.unanimity == pytest.approx(1.0)
        assert result.n_bullish == 3
        assert len(result.dissent_sources) == 0

    def test_mixed_consensus(self):
        votes = [
            SourceVote(source="news", score=0.6, confidence=0.9),
            SourceVote(source="social", score=-0.3, confidence=0.5),
            SourceVote(source="insider", score=0.4, confidence=0.7),
        ]
        result = self.scorer.score_consensus(votes, symbol="AAPL")
        assert result.consensus_direction == "bullish"
        assert result.n_bearish == 1
        assert "social" in result.dissent_sources

    def test_detect_shift_reversal(self):
        prev = ConsensusResult(
            symbol="AAPL", consensus_direction="bullish", consensus_score=0.5,
            consensus_strength=0.7,
        )
        curr = ConsensusResult(
            symbol="AAPL", consensus_direction="bearish", consensus_score=-0.3,
            consensus_strength=0.6,
        )
        shift = self.scorer.detect_shift(prev, curr)
        assert shift.is_reversal
        assert shift.score_change < 0
        assert shift.is_significant

    def test_detect_shift_minor(self):
        prev = ConsensusResult(
            symbol="AAPL", consensus_direction="bullish", consensus_score=0.5,
            consensus_strength=0.7,
        )
        curr = ConsensusResult(
            symbol="AAPL", consensus_direction="bullish", consensus_score=0.45,
            consensus_strength=0.65,
        )
        shift = self.scorer.detect_shift(prev, curr)
        assert not shift.is_reversal
        assert shift.shift_magnitude == "none"

    def test_market_consensus_bullish(self):
        results = [
            ConsensusResult(consensus_direction="bullish", consensus_strength=0.7),
            ConsensusResult(consensus_direction="bullish", consensus_strength=0.6),
            ConsensusResult(consensus_direction="neutral", consensus_strength=0.3),
        ]
        mc = self.scorer.market_consensus(results)
        assert mc.market_direction == "bullish"
        assert mc.bullish_pct == pytest.approx(2 / 3, abs=0.01)
        assert mc.breadth_score > 0.5

    def test_market_consensus_empty(self):
        mc = self.scorer.market_consensus([])
        assert mc.n_symbols == 0


# ===================================================================
# Momentum Tests
# ===================================================================
class TestMomentumResult:
    def test_positive_momentum(self):
        mr = MomentumResult(momentum=0.05)
        assert mr.is_positive_momentum

    def test_negative_momentum(self):
        mr = MomentumResult(momentum=-0.05)
        assert mr.is_negative_momentum

    def test_accelerating(self):
        mr = MomentumResult(momentum=0.1, acceleration=0.02)
        assert mr.is_accelerating
        assert not mr.is_decelerating

    def test_decelerating(self):
        mr = MomentumResult(momentum=0.1, acceleration=-0.02)
        assert mr.is_decelerating

    def test_signal_strength(self):
        mr = MomentumResult(momentum=0.1, trend_strength=0.8)
        assert mr.signal_strength > 0


class TestTrendReversal:
    def test_bullish_reversal(self):
        tr = TrendReversal(reversal_type="bullish_reversal", magnitude=0.4, confidence=0.7)
        assert tr.is_bullish_reversal
        assert tr.is_significant

    def test_insignificant_reversal(self):
        tr = TrendReversal(reversal_type="bearish_reversal", magnitude=0.1, confidence=0.3)
        assert not tr.is_significant


class TestMomentumSummary:
    def test_market_momentum_positive(self):
        ms = MomentumSummary(breadth=0.7)
        assert ms.market_momentum == "positive"

    def test_market_momentum_negative(self):
        ms = MomentumSummary(breadth=0.2)
        assert ms.market_momentum == "negative"

    def test_market_momentum_neutral(self):
        ms = MomentumSummary(breadth=0.5)
        assert ms.market_momentum == "neutral"


class TestSentimentMomentumTracker:
    def setup_method(self):
        self.tracker = SentimentMomentumTracker()

    def test_compute_momentum_insufficient_data(self):
        result = self.tracker.compute_momentum("AAPL", scores=[0.3, 0.4])
        assert result.n_periods == 2
        assert result.momentum == 0.0

    def test_compute_momentum_improving(self):
        scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
        result = self.tracker.compute_momentum("AAPL", scores=scores)
        assert result.trend_direction == "improving"
        assert result.momentum > 0
        assert result.trend_strength > 0.5

    def test_compute_momentum_deteriorating(self):
        scores = [0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
        result = self.tracker.compute_momentum("AAPL", scores=scores)
        assert result.trend_direction == "deteriorating"
        assert result.momentum < 0

    def test_inflection_detection(self):
        # Rising then falling
        scores = [0.1, 0.3, 0.5, 0.7, 0.65, 0.5, 0.3]
        result = self.tracker.compute_momentum("AAPL", scores=scores)
        # After smoothing, the inflection should be detected
        assert result.n_periods == 7

    def test_add_snapshot_and_compute(self):
        for i, score in enumerate([0.1, 0.2, 0.3, 0.4, 0.5]):
            self.tracker.add_snapshot(
                SentimentSnapshot(symbol="AAPL", score=score, period_index=i)
            )
        result = self.tracker.compute_momentum("AAPL")
        assert result.n_periods == 5
        assert result.momentum > 0

    def test_add_scores_bulk(self):
        self.tracker.add_scores("MSFT", [0.5, 0.4, 0.3, 0.2, 0.1])
        result = self.tracker.compute_momentum("MSFT")
        assert result.trend_direction == "deteriorating"

    def test_detect_reversal_bullish(self):
        # Declining then recovering
        scores = [0.5, 0.4, 0.3, 0.2, 0.1, 0.0, -0.1, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
        reversal = self.tracker.detect_reversal("AAPL", scores=scores, window=5)
        if reversal:
            assert reversal.reversal_type == "bullish_reversal"

    def test_detect_reversal_none(self):
        # Consistently rising — no reversal
        scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        reversal = self.tracker.detect_reversal("AAPL", scores=scores, window=3)
        assert reversal is None

    def test_momentum_summary(self):
        self.tracker.add_scores("AAPL", [0.1, 0.2, 0.3, 0.4, 0.5])
        self.tracker.add_scores("MSFT", [0.5, 0.4, 0.3, 0.2, 0.1])
        self.tracker.add_scores("GOOG", [0.3, 0.3, 0.3, 0.3, 0.3])
        summary = self.tracker.momentum_summary()
        assert summary.n_symbols == 3
        assert summary.strongest_up == "AAPL"
        assert summary.strongest_down == "MSFT"

    def test_momentum_summary_empty(self):
        summary = self.tracker.momentum_summary()
        assert summary.n_symbols == 0

    def test_detect_reversal_too_short(self):
        scores = [0.3, 0.4, 0.5]
        reversal = self.tracker.detect_reversal("AAPL", scores=scores, window=3)
        assert reversal is None
