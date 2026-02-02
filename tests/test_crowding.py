"""Tests for Crowding Analysis module."""

import numpy as np
import pytest

from src.crowding.config import (
    CrowdingLevel, SqueezeRisk, ConsensusRating, OverlapMethod,
    DetectorConfig, OverlapConfig, ShortInterestConfig, ConsensusConfig,
    CrowdingConfig, DEFAULT_CONFIG,
)
from src.crowding.models import (
    CrowdingScore, FundOverlap, CrowdedName,
    ShortInterestData, ShortSqueezeScore, ConsensusSnapshot,
)
from src.crowding.detector import CrowdingDetector
from src.crowding.overlap import OverlapAnalyzer
from src.crowding.short_interest import ShortInterestAnalyzer
from src.crowding.consensus import ConsensusAnalyzer


# ── Config Tests ─────────────────────────────────────────────


class TestConfig:
    def test_crowding_level_values(self):
        assert CrowdingLevel.LOW.value == "low"
        assert CrowdingLevel.EXTREME.value == "extreme"

    def test_squeeze_risk_values(self):
        assert SqueezeRisk.LOW.value == "low"
        assert SqueezeRisk.HIGH.value == "high"

    def test_consensus_rating_values(self):
        assert ConsensusRating.STRONG_BUY.value == "strong_buy"
        assert ConsensusRating.SELL.value == "sell"

    def test_overlap_method_values(self):
        assert OverlapMethod.JACCARD.value == "jaccard"
        assert OverlapMethod.COSINE.value == "cosine"

    def test_detector_config_defaults(self):
        cfg = DetectorConfig()
        assert cfg.high_threshold == 0.70
        assert cfg.extreme_threshold == 0.85

    def test_overlap_config_defaults(self):
        cfg = OverlapConfig()
        assert cfg.method == OverlapMethod.JACCARD
        assert cfg.top_crowded_count == 20

    def test_short_interest_config_defaults(self):
        cfg = ShortInterestConfig()
        assert cfg.high_si_threshold == 0.20
        assert cfg.squeeze_dtc_threshold == 5.0

    def test_consensus_config_defaults(self):
        cfg = ConsensusConfig()
        assert cfg.min_analysts == 5
        assert cfg.contrarian_threshold == 0.80

    def test_crowding_config_bundles(self):
        cfg = CrowdingConfig()
        assert isinstance(cfg.detector, DetectorConfig)
        assert isinstance(cfg.overlap, OverlapConfig)


# ── Model Tests ──────────────────────────────────────────────


class TestModels:
    def test_crowding_score_is_crowded(self):
        s = CrowdingScore(symbol="AAPL", score=0.75, level=CrowdingLevel.HIGH)
        assert s.is_crowded

    def test_crowding_score_not_crowded(self):
        s = CrowdingScore(symbol="AAPL", score=0.30, level=CrowdingLevel.LOW)
        assert not s.is_crowded

    def test_crowding_score_to_dict(self):
        s = CrowdingScore(symbol="AAPL", score=0.75, level=CrowdingLevel.HIGH,
                          n_holders=50, is_decrowding=True)
        d = s.to_dict()
        assert d["level"] == "high"
        assert d["is_crowded"] is True
        assert d["is_decrowding"] is True

    def test_fund_overlap_pct(self):
        o = FundOverlap(fund_a="A", fund_b="B", overlap_score=0.45,
                        shared_positions=10, total_positions_a=20, total_positions_b=25)
        assert abs(o.overlap_pct - 45.0) < 0.01

    def test_fund_overlap_to_dict(self):
        o = FundOverlap(fund_a="A", fund_b="B", overlap_score=0.45,
                        shared_positions=10, total_positions_a=20, total_positions_b=25,
                        top_shared=["AAPL", "MSFT"])
        d = o.to_dict()
        assert d["top_shared"] == ["AAPL", "MSFT"]

    def test_crowded_name_intensity(self):
        c = CrowdedName(symbol="AAPL", n_funds=10, total_ownership_pct=25.0,
                        avg_position_size=2.5, breadth=0.8, depth=0.6)
        assert abs(c.crowding_intensity - 0.7) < 0.01

    def test_short_interest_data_properties(self):
        d = ShortInterestData(symbol="GME", shares_short=10e6,
                              float_shares=50e6, avg_daily_volume=5e6,
                              cost_to_borrow=0.30)
        assert abs(d.si_ratio - 0.2) < 0.001
        assert abs(d.days_to_cover - 2.0) < 0.001

    def test_short_interest_zero_float(self):
        d = ShortInterestData(symbol="X", shares_short=100,
                              float_shares=0, avg_daily_volume=0)
        assert d.si_ratio == 0.0
        assert d.days_to_cover == 0.0

    def test_short_interest_to_dict(self):
        d = ShortInterestData(symbol="GME", shares_short=10e6,
                              float_shares=50e6, avg_daily_volume=5e6)
        result = d.to_dict()
        assert result["si_ratio"] == 0.2
        assert result["days_to_cover"] == 2.0

    def test_squeeze_score_to_dict(self):
        s = ShortSqueezeScore(symbol="GME", squeeze_score=0.8,
                              risk=SqueezeRisk.HIGH, si_ratio=0.3)
        d = s.to_dict()
        assert d["risk"] == "high"

    def test_consensus_snapshot_rating(self):
        c = ConsensusSnapshot(symbol="AAPL", mean_rating=4.2, n_analysts=20,
                              buy_count=15, hold_count=4, sell_count=1)
        assert c.rating == ConsensusRating.BUY
        assert abs(c.buy_pct - 75.0) < 0.01

    def test_consensus_rating_levels(self):
        assert ConsensusSnapshot(symbol="X", mean_rating=4.6, n_analysts=5).rating == ConsensusRating.STRONG_BUY
        assert ConsensusSnapshot(symbol="X", mean_rating=3.0, n_analysts=5).rating == ConsensusRating.HOLD
        assert ConsensusSnapshot(symbol="X", mean_rating=1.8, n_analysts=5).rating == ConsensusRating.SELL
        assert ConsensusSnapshot(symbol="X", mean_rating=1.2, n_analysts=5).rating == ConsensusRating.STRONG_SELL

    def test_consensus_to_dict(self):
        c = ConsensusSnapshot(symbol="AAPL", mean_rating=4.2, n_analysts=20,
                              buy_count=15, is_contrarian=True)
        d = c.to_dict()
        assert d["rating"] == "buy"
        assert d["is_contrarian"] is True


# ── Crowding Detector Tests ──────────────────────────────────


class TestCrowdingDetector:
    def test_basic_scoring(self):
        detector = CrowdingDetector()
        score = detector.score("AAPL", [8.0, 7.0, 5.0, 3.0, 2.0], n_holders=50)
        assert score.symbol == "AAPL"
        assert 0 <= score.score <= 1

    def test_high_crowding(self):
        # Many holders with high concentration
        detector = CrowdingDetector()
        ownership = [15.0, 12.0, 10.0, 8.0, 5.0] + [2.0] * 40
        score = detector.score("CROWDED", ownership, n_holders=100)
        assert score.level in (CrowdingLevel.HIGH, CrowdingLevel.EXTREME, CrowdingLevel.MEDIUM)

    def test_low_crowding(self):
        detector = CrowdingDetector()
        score = detector.score("UNCROWDED", [1.0, 0.5], n_holders=2)
        assert score.level == CrowdingLevel.LOW

    def test_decrowding_detection(self):
        detector = CrowdingDetector()
        score = detector.score(
            "AAPL", [5.0, 3.0], n_holders=10,
            previous_scores=[0.8, 0.7, 0.6],
        )
        assert score.is_decrowding  # declining trend

    def test_empty_ownership(self):
        detector = CrowdingDetector()
        score = detector.score("EMPTY", [])
        assert score.score == 0.0

    def test_history_tracking(self):
        detector = CrowdingDetector()
        detector.score("AAPL", [5.0, 3.0], n_holders=10)
        detector.score("AAPL", [6.0, 4.0], n_holders=12)
        assert len(detector.get_history("AAPL")) == 2

    def test_reset(self):
        detector = CrowdingDetector()
        detector.score("AAPL", [5.0])
        detector.reset()
        assert detector.get_history("AAPL") == []


# ── Overlap Analyzer Tests ───────────────────────────────────


class TestOverlapAnalyzer:
    def test_jaccard_overlap(self):
        a = {"AAPL": 5.0, "MSFT": 3.0, "GOOG": 2.0}
        b = {"AAPL": 4.0, "MSFT": 2.0, "AMZN": 3.0}
        analyzer = OverlapAnalyzer()
        result = analyzer.compute_overlap(a, b, "Fund A", "Fund B")

        assert result.shared_positions == 2  # AAPL, MSFT
        assert result.overlap_score > 0
        assert result.overlap_score <= 1.0

    def test_cosine_overlap(self):
        a = {"AAPL": 5.0, "MSFT": 3.0}
        b = {"AAPL": 5.0, "MSFT": 3.0}
        cfg = OverlapConfig(method=OverlapMethod.COSINE)
        analyzer = OverlapAnalyzer(cfg)
        result = analyzer.compute_overlap(a, b)
        assert abs(result.overlap_score - 1.0) < 0.01  # identical

    def test_no_overlap(self):
        a = {"AAPL": 5.0}
        b = {"GOOG": 3.0}
        analyzer = OverlapAnalyzer()
        result = analyzer.compute_overlap(a, b)
        assert result.overlap_score == 0.0
        assert result.shared_positions == 0

    def test_all_overlaps(self):
        portfolios = {
            "Fund A": {"AAPL": 5, "MSFT": 3},
            "Fund B": {"AAPL": 4, "GOOG": 2},
            "Fund C": {"MSFT": 3, "GOOG": 2},
        }
        analyzer = OverlapAnalyzer()
        results = analyzer.compute_all_overlaps(portfolios)
        assert len(results) == 3  # C(3,2) = 3 pairs

    def test_crowded_names(self):
        portfolios = {
            "Fund A": {"AAPL": 5, "MSFT": 3, "GOOG": 2},
            "Fund B": {"AAPL": 4, "MSFT": 2, "AMZN": 3},
            "Fund C": {"AAPL": 3, "GOOG": 2, "AMZN": 1},
        }
        analyzer = OverlapAnalyzer()
        crowded = analyzer.find_crowded_names(portfolios)
        assert crowded[0].symbol == "AAPL"  # held by all 3 funds
        assert crowded[0].n_funds == 3

    def test_empty_portfolios(self):
        analyzer = OverlapAnalyzer()
        result = analyzer.find_crowded_names({})
        assert result == []


# ── Short Interest Analyzer Tests ────────────────────────────


class TestShortInterestAnalyzer:
    def test_basic_analysis(self):
        analyzer = ShortInterestAnalyzer()
        for i in range(5):
            analyzer.add_data(ShortInterestData(
                symbol="GME", shares_short=10e6 + i * 1e6,
                float_shares=50e6, avg_daily_volume=5e6,
                cost_to_borrow=0.30, date=f"2026-01-{i + 1:02d}",
            ))
        result = analyzer.analyze("GME")
        assert result.symbol == "GME"
        assert result.squeeze_score > 0

    def test_high_squeeze_risk(self):
        analyzer = ShortInterestAnalyzer()
        for i in range(5):
            analyzer.add_data(ShortInterestData(
                symbol="SQUEEZE", shares_short=20e6,
                float_shares=40e6, avg_daily_volume=2e6,
                cost_to_borrow=0.50,
            ))
        result = analyzer.analyze("SQUEEZE")
        assert result.risk in (SqueezeRisk.HIGH, SqueezeRisk.ELEVATED)

    def test_low_squeeze_risk(self):
        analyzer = ShortInterestAnalyzer()
        analyzer.add_data(ShortInterestData(
            symbol="SAFE", shares_short=1e6,
            float_shares=100e6, avg_daily_volume=10e6,
            cost_to_borrow=0.01,
        ))
        result = analyzer.analyze("SAFE")
        assert result.risk == SqueezeRisk.LOW

    def test_si_momentum(self):
        analyzer = ShortInterestAnalyzer()
        for i in range(10):
            analyzer.add_data(ShortInterestData(
                symbol="RISING", shares_short=5e6 + i * 1e6,
                float_shares=50e6, avg_daily_volume=5e6,
            ))
        result = analyzer.analyze("RISING")
        assert result.si_momentum > 0  # increasing SI

    def test_empty_symbol(self):
        analyzer = ShortInterestAnalyzer()
        result = analyzer.analyze("UNKNOWN")
        assert result.squeeze_score == 0.0

    def test_reset(self):
        analyzer = ShortInterestAnalyzer()
        analyzer.add_data(ShortInterestData(
            symbol="X", shares_short=1e6, float_shares=10e6, avg_daily_volume=1e6,
        ))
        analyzer.reset()
        assert analyzer.get_history("X") == []


# ── Consensus Analyzer Tests ────────────────────────────────


class TestConsensusAnalyzer:
    def test_basic_analysis(self):
        analyzer = ConsensusAnalyzer()
        ratings = [4.0, 4.5, 3.5, 4.0, 5.0, 3.0, 4.0]
        result = analyzer.analyze("AAPL", ratings, current_price=150.0)

        assert result.symbol == "AAPL"
        assert result.n_analysts == 7
        assert result.mean_rating > 0

    def test_buy_hold_sell_counts(self):
        analyzer = ConsensusAnalyzer()
        ratings = [5.0, 4.0, 4.0, 3.0, 2.0]  # 3 buy, 1 hold, 1 sell
        result = analyzer.analyze("TEST", ratings)
        assert result.buy_count == 3
        assert result.hold_count == 1
        assert result.sell_count == 1

    def test_target_upside(self):
        analyzer = ConsensusAnalyzer()
        ratings = [4.0] * 5
        targets = [180.0, 190.0, 170.0, 185.0, 175.0]
        result = analyzer.analyze("AAPL", ratings, targets, current_price=150.0)
        assert result.target_upside > 0  # mean target > current price

    def test_contrarian_detection(self):
        analyzer = ConsensusAnalyzer()
        # 90% buy -> potential contrarian signal
        ratings = [4.0, 4.5, 4.0, 5.0, 4.0, 4.5, 4.0, 5.0, 4.0, 2.0]
        result = analyzer.analyze("CROWD", ratings)
        assert result.is_contrarian

    def test_not_contrarian(self):
        analyzer = ConsensusAnalyzer()
        # Mixed ratings
        ratings = [5.0, 4.0, 3.0, 2.0, 1.0]
        result = analyzer.analyze("MIXED", ratings)
        assert not result.is_contrarian

    def test_revision_momentum(self):
        analyzer = ConsensusAnalyzer()
        # First snapshot
        analyzer.analyze("AAPL", [3.0] * 5)
        # Second snapshot with higher ratings
        result = analyzer.analyze("AAPL", [4.0] * 5)
        assert result.revision_momentum > 0

    def test_too_few_analysts(self):
        analyzer = ConsensusAnalyzer()
        result = analyzer.analyze("X", [4.0, 3.0])
        assert result.n_analysts == 0  # below min_analysts

    def test_reset(self):
        analyzer = ConsensusAnalyzer()
        analyzer.analyze("AAPL", [4.0] * 5)
        analyzer.reset()
        assert analyzer.get_history("AAPL") == []


# ── Integration Tests ────────────────────────────────────────


class TestIntegration:
    def test_full_pipeline(self):
        """End-to-end: crowding + overlap + short interest + consensus."""
        # Crowding detection
        detector = CrowdingDetector()
        score = detector.score("AAPL", [8.0, 6.0, 4.0, 3.0, 2.0], n_holders=50)
        assert score.score > 0

        # Fund overlap
        portfolios = {
            "Fund A": {"AAPL": 5, "MSFT": 3, "GOOG": 2},
            "Fund B": {"AAPL": 4, "MSFT": 2, "AMZN": 3},
        }
        overlap = OverlapAnalyzer()
        overlaps = overlap.compute_all_overlaps(portfolios)
        assert len(overlaps) == 1
        crowded = overlap.find_crowded_names(portfolios)
        assert len(crowded) > 0

        # Short interest
        si = ShortInterestAnalyzer()
        si.add_data(ShortInterestData(
            symbol="AAPL", shares_short=5e6,
            float_shares=100e6, avg_daily_volume=10e6,
        ))
        squeeze = si.analyze("AAPL")
        assert isinstance(squeeze.risk, SqueezeRisk)

        # Consensus
        consensus = ConsensusAnalyzer()
        snap = consensus.analyze("AAPL", [4.0, 4.5, 3.5, 4.0, 5.0],
                                 [180, 190, 175], current_price=150.0)
        assert snap.rating in (ConsensusRating.BUY, ConsensusRating.STRONG_BUY)


class TestModuleImports:
    def test_top_level_imports(self):
        from src.crowding import (
            CrowdingDetector, OverlapAnalyzer,
            ShortInterestAnalyzer, ConsensusAnalyzer,
            CrowdingScore, FundOverlap, CrowdedName,
            ShortInterestData, ShortSqueezeScore, ConsensusSnapshot,
            CrowdingLevel, SqueezeRisk, ConsensusRating,
            DEFAULT_CONFIG,
        )
        assert DEFAULT_CONFIG is not None
