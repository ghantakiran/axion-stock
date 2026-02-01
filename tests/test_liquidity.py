"""Tests for PRD-39: Liquidity Analysis."""

import pytest
import numpy as np
import pandas as pd
from datetime import date

from src.liquidity.config import (
    LiquidityLevel,
    ImpactModel,
    SpreadType,
    VolumeProfile,
    SpreadConfig,
    VolumeConfig,
    ImpactConfig,
    ScoringConfig,
    LiquidityConfig,
    DEFAULT_SPREAD_CONFIG,
    DEFAULT_VOLUME_CONFIG,
    DEFAULT_IMPACT_CONFIG,
    DEFAULT_SCORING_CONFIG,
    DEFAULT_CONFIG,
)
from src.liquidity.models import (
    SpreadAnalysis,
    VolumeAnalysis,
    MarketImpact,
    LiquidityScore,
    LiquiditySnapshot,
)
from src.liquidity.engine import LiquidityEngine
from src.liquidity.impact import MarketImpactEstimator
from src.liquidity.scoring import LiquidityScorer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bid_ask(n: int = 50, mid: float = 150.0, spread: float = 0.02, seed: int = 42):
    """Generate synthetic bid/ask series."""
    rng = np.random.RandomState(seed)
    noise = rng.normal(0, 0.005, n)
    half = spread / 2
    mids = mid + np.cumsum(rng.normal(0, 0.5, n))
    bid = pd.Series(mids - half + noise)
    ask = pd.Series(mids + half - noise)
    return bid, ask


def _make_volume_close(n: int = 50, avg_vol: float = 5_000_000, price: float = 150.0, seed: int = 42):
    """Generate synthetic volume and close series."""
    rng = np.random.RandomState(seed)
    volume = pd.Series(np.abs(rng.normal(avg_vol, avg_vol * 0.3, n)).astype(int))
    close = pd.Series(price + np.cumsum(rng.normal(0, 1.0, n)))
    return volume, close


# ===========================================================================
# Config Tests
# ===========================================================================

class TestConfig:
    """Test configuration enums and dataclasses."""

    def test_liquidity_level_values(self):
        assert LiquidityLevel.VERY_HIGH.value == "very_high"
        assert LiquidityLevel.HIGH.value == "high"
        assert LiquidityLevel.MEDIUM.value == "medium"
        assert LiquidityLevel.LOW.value == "low"
        assert LiquidityLevel.VERY_LOW.value == "very_low"

    def test_impact_model_values(self):
        assert ImpactModel.LINEAR.value == "linear"
        assert ImpactModel.SQUARE_ROOT.value == "square_root"

    def test_spread_type_values(self):
        assert SpreadType.ABSOLUTE.value == "absolute"
        assert SpreadType.RELATIVE.value == "relative"
        assert SpreadType.EFFECTIVE.value == "effective"

    def test_volume_profile_values(self):
        assert VolumeProfile.U_SHAPE.value == "u_shape"
        assert VolumeProfile.FLAT.value == "flat"

    def test_spread_config_defaults(self):
        cfg = SpreadConfig()
        assert cfg.outlier_percentile == 99.0
        assert cfg.min_observations == 10

    def test_volume_config_defaults(self):
        cfg = VolumeConfig()
        assert cfg.window == 21
        assert cfg.vwap_window == 1
        assert cfg.min_observations == 10

    def test_impact_config_defaults(self):
        cfg = ImpactConfig()
        assert cfg.model == ImpactModel.SQUARE_ROOT
        assert cfg.max_participation_rate == 0.10
        assert cfg.impact_coefficient == 0.1

    def test_scoring_config_defaults(self):
        cfg = ScoringConfig()
        assert cfg.spread_weight + cfg.volume_weight + cfg.impact_weight == pytest.approx(1.0)
        assert cfg.very_high_threshold == 80.0

    def test_liquidity_config_bundles(self):
        cfg = LiquidityConfig()
        assert isinstance(cfg.spread, SpreadConfig)
        assert isinstance(cfg.volume, VolumeConfig)
        assert isinstance(cfg.impact, ImpactConfig)
        assert isinstance(cfg.scoring, ScoringConfig)

    def test_default_config_exists(self):
        assert DEFAULT_CONFIG.spread.min_observations == 10


# ===========================================================================
# Model Tests
# ===========================================================================

class TestModels:
    """Test data models."""

    def test_spread_analysis_defaults(self):
        sa = SpreadAnalysis()
        assert sa.avg_spread == 0.0
        assert sa.spread_bps == 0.0

    def test_spread_analysis_bps(self):
        sa = SpreadAnalysis(relative_spread=0.0005)
        assert sa.spread_bps == 5.0

    def test_spread_analysis_to_dict(self):
        sa = SpreadAnalysis(symbol="AAPL", avg_spread=0.02, relative_spread=0.0001)
        d = sa.to_dict()
        assert d["symbol"] == "AAPL"
        assert "spread_bps" in d

    def test_volume_analysis_defaults(self):
        va = VolumeAnalysis()
        assert va.avg_volume == 0.0
        assert va.is_low_volume is False
        assert va.is_high_volume is False

    def test_volume_analysis_low_volume(self):
        va = VolumeAnalysis(volume_ratio=0.3)
        assert va.is_low_volume is True

    def test_volume_analysis_high_volume(self):
        va = VolumeAnalysis(volume_ratio=2.5)
        assert va.is_high_volume is True

    def test_volume_analysis_to_dict(self):
        va = VolumeAnalysis(symbol="MSFT", avg_volume=5000000)
        d = va.to_dict()
        assert d["symbol"] == "MSFT"

    def test_market_impact_defaults(self):
        mi = MarketImpact()
        assert mi.trade_size == 0
        assert mi.is_within_safe_limit is True  # 0 <= 0

    def test_market_impact_safe_limit(self):
        mi = MarketImpact(trade_size=10000, max_safe_size=50000)
        assert mi.is_within_safe_limit is True
        mi2 = MarketImpact(trade_size=100000, max_safe_size=50000)
        assert mi2.is_within_safe_limit is False

    def test_market_impact_to_dict(self):
        mi = MarketImpact(symbol="TSLA", trade_size=5000, max_safe_size=50000)
        d = mi.to_dict()
        assert d["is_safe"] is True

    def test_liquidity_score_defaults(self):
        ls = LiquidityScore()
        assert ls.score == 50.0
        assert ls.level == LiquidityLevel.MEDIUM

    def test_liquidity_score_to_dict(self):
        ls = LiquidityScore(symbol="SPY", score=92.5, level=LiquidityLevel.VERY_HIGH)
        d = ls.to_dict()
        assert d["level"] == "very_high"

    def test_liquidity_snapshot_to_dict(self):
        snap = LiquiditySnapshot(
            symbol="AAPL",
            spread=SpreadAnalysis(symbol="AAPL", avg_spread=0.02),
            date=date(2026, 1, 31),
        )
        d = snap.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["spread"] is not None
        assert d["volume"] is None


# ===========================================================================
# Engine Tests
# ===========================================================================

class TestLiquidityEngine:
    """Test liquidity engine."""

    def test_analyze_spread_basic(self):
        bid, ask = _make_bid_ask(50)
        engine = LiquidityEngine()
        result = engine.analyze_spread(bid, ask, symbol="TEST")
        assert result.symbol == "TEST"
        assert result.avg_spread > 0
        assert result.median_spread > 0
        assert result.relative_spread > 0
        assert result.n_observations > 0

    def test_analyze_spread_tight(self):
        bid, ask = _make_bid_ask(50, spread=0.01)
        engine = LiquidityEngine()
        result = engine.analyze_spread(bid, ask)
        assert result.avg_spread < 0.05

    def test_analyze_spread_wide(self):
        bid, ask = _make_bid_ask(50, spread=1.0)
        engine = LiquidityEngine()
        result = engine.analyze_spread(bid, ask)
        assert result.avg_spread > 0.5

    def test_analyze_spread_insufficient_data(self):
        engine = LiquidityEngine()
        result = engine.analyze_spread(pd.Series([100.0]), pd.Series([100.02]))
        assert result.avg_spread == 0.0

    def test_analyze_volume_basic(self):
        volume, close = _make_volume_close(50)
        engine = LiquidityEngine()
        result = engine.analyze_volume(volume, close, symbol="VOL")
        assert result.symbol == "VOL"
        assert result.avg_volume > 0
        assert result.avg_dollar_volume > 0
        assert result.vwap > 0

    def test_analyze_volume_ratio(self):
        volume, close = _make_volume_close(50, avg_vol=5_000_000)
        engine = LiquidityEngine()
        result = engine.analyze_volume(volume, close)
        # Ratio should be reasonable
        assert 0.1 < result.volume_ratio < 5.0

    def test_analyze_volume_insufficient_data(self):
        engine = LiquidityEngine()
        result = engine.analyze_volume(pd.Series([1000]), pd.Series([100.0]))
        assert result.avg_volume == 0.0

    def test_compute_vwap(self):
        engine = LiquidityEngine()
        price = pd.Series([100.0, 101.0, 102.0])
        volume = pd.Series([1000, 2000, 1000])
        vwap = engine.compute_vwap(price, volume)
        expected = (100 * 1000 + 101 * 2000 + 102 * 1000) / 4000
        assert vwap == pytest.approx(expected, abs=0.01)

    def test_compute_vwap_empty(self):
        engine = LiquidityEngine()
        assert engine.compute_vwap(pd.Series(dtype=float), pd.Series(dtype=float)) == 0.0

    def test_compute_vwap_zero_volume(self):
        engine = LiquidityEngine()
        assert engine.compute_vwap(pd.Series([100.0]), pd.Series([0])) == 0.0


# ===========================================================================
# Impact Tests
# ===========================================================================

class TestMarketImpactEstimator:
    """Test market impact estimation."""

    def test_estimate_impact_basic(self):
        estimator = MarketImpactEstimator()
        impact = estimator.estimate_impact(
            trade_size=10000,
            avg_volume=5_000_000,
            avg_spread=0.02,
            volatility=0.015,
            price=150.0,
            symbol="AAPL",
        )
        assert impact.symbol == "AAPL"
        assert impact.trade_size == 10000
        assert impact.participation_rate > 0
        assert impact.spread_cost > 0
        assert impact.impact_cost > 0
        assert impact.total_cost > 0
        assert impact.total_cost_bps > 0

    def test_estimate_impact_large_trade(self):
        estimator = MarketImpactEstimator()
        small = estimator.estimate_impact(trade_size=1000, avg_volume=1_000_000, volatility=0.02)
        large = estimator.estimate_impact(trade_size=100000, avg_volume=1_000_000, volatility=0.02)
        assert large.impact_cost > small.impact_cost
        assert large.total_cost_bps > small.total_cost_bps

    def test_estimate_impact_zero_volume(self):
        estimator = MarketImpactEstimator()
        impact = estimator.estimate_impact(trade_size=1000, avg_volume=0)
        assert impact.participation_rate == 0.0

    def test_estimate_impact_zero_size(self):
        estimator = MarketImpactEstimator()
        impact = estimator.estimate_impact(trade_size=0, avg_volume=1_000_000)
        assert impact.total_cost == 0.0

    def test_linear_model(self):
        cfg = ImpactConfig(model=ImpactModel.LINEAR)
        estimator = MarketImpactEstimator(config=cfg)
        impact = estimator.estimate_impact(
            trade_size=10000, avg_volume=1_000_000, volatility=0.02
        )
        assert impact.model == ImpactModel.LINEAR
        assert impact.impact_cost > 0

    def test_sqrt_model(self):
        cfg = ImpactConfig(model=ImpactModel.SQUARE_ROOT)
        estimator = MarketImpactEstimator(config=cfg)
        impact = estimator.estimate_impact(
            trade_size=10000, avg_volume=1_000_000, volatility=0.02
        )
        assert impact.model == ImpactModel.SQUARE_ROOT
        assert impact.impact_cost > 0

    def test_max_safe_size(self):
        estimator = MarketImpactEstimator()
        safe = estimator.max_safe_size(1_000_000)
        assert safe == 100_000  # 10% of 1M

    def test_max_safe_size_custom_rate(self):
        estimator = MarketImpactEstimator()
        safe = estimator.max_safe_size(1_000_000, max_participation=0.05)
        assert safe == 50_000

    def test_execution_horizon_small_trade(self):
        estimator = MarketImpactEstimator()
        days = estimator.execution_horizon(10_000, 1_000_000)
        assert days == 1

    def test_execution_horizon_large_trade(self):
        estimator = MarketImpactEstimator()
        days = estimator.execution_horizon(500_000, 1_000_000)
        # 500k / (1M * 0.10) = 5 days
        assert days == 5

    def test_execution_horizon_zero_volume(self):
        estimator = MarketImpactEstimator()
        days = estimator.execution_horizon(10_000, 0)
        assert days == 1

    def test_impact_includes_safe_size(self):
        estimator = MarketImpactEstimator()
        impact = estimator.estimate_impact(
            trade_size=200_000, avg_volume=1_000_000, volatility=0.02
        )
        assert impact.max_safe_size == 100_000
        assert impact.is_within_safe_limit is False


# ===========================================================================
# Scoring Tests
# ===========================================================================

class TestLiquidityScorer:
    """Test liquidity scoring."""

    def test_score_highly_liquid(self):
        spread = SpreadAnalysis(symbol="SPY", relative_spread=0.00005)  # 0.5 bps
        volume = VolumeAnalysis(symbol="SPY", avg_dollar_volume=1_000_000_000)
        scorer = LiquidityScorer()
        result = scorer.score(spread, volume)
        assert result.score > 80
        assert result.level == LiquidityLevel.VERY_HIGH

    def test_score_illiquid(self):
        spread = SpreadAnalysis(symbol="TINY", relative_spread=0.02)  # 200 bps
        volume = VolumeAnalysis(symbol="TINY", avg_dollar_volume=50_000)
        scorer = LiquidityScorer()
        result = scorer.score(spread, volume)
        assert result.score < 20
        assert result.level in (LiquidityLevel.LOW, LiquidityLevel.VERY_LOW)

    def test_score_medium_liquidity(self):
        spread = SpreadAnalysis(symbol="MID", relative_spread=0.001)  # 10 bps
        volume = VolumeAnalysis(symbol="MID", avg_dollar_volume=20_000_000)
        scorer = LiquidityScorer()
        result = scorer.score(spread, volume)
        assert 30 < result.score < 80

    def test_score_with_impact(self):
        spread = SpreadAnalysis(symbol="TEST", relative_spread=0.0005)
        volume = VolumeAnalysis(symbol="TEST", avg_dollar_volume=100_000_000)
        impact = MarketImpact(total_cost_bps=5.0, max_safe_size=50000)
        scorer = LiquidityScorer()
        result = scorer.score(spread, volume, impact, price=100.0)
        assert result.max_safe_shares == 50000
        assert result.max_safe_dollars == 5_000_000

    def test_score_sub_components(self):
        spread = SpreadAnalysis(symbol="X", relative_spread=0.0002)
        volume = VolumeAnalysis(symbol="X", avg_dollar_volume=50_000_000)
        scorer = LiquidityScorer()
        result = scorer.score(spread, volume)
        assert result.spread_score > 0
        assert result.volume_score > 0
        assert result.impact_score > 0

    def test_rank_universe(self):
        scorer = LiquidityScorer()
        scores = [
            LiquidityScore(symbol="A", score=90.0),
            LiquidityScore(symbol="B", score=50.0),
            LiquidityScore(symbol="C", score=75.0),
        ]
        ranked = scorer.rank_universe(scores)
        assert ranked[0].symbol == "A"
        assert ranked[1].symbol == "C"
        assert ranked[2].symbol == "B"

    def test_classify_all_levels(self):
        scorer = LiquidityScorer()
        # Test classification at boundaries
        assert scorer._classify(85.0) == LiquidityLevel.VERY_HIGH
        assert scorer._classify(65.0) == LiquidityLevel.HIGH
        assert scorer._classify(45.0) == LiquidityLevel.MEDIUM
        assert scorer._classify(25.0) == LiquidityLevel.LOW
        assert scorer._classify(10.0) == LiquidityLevel.VERY_LOW

    def test_score_to_dict(self):
        scorer = LiquidityScorer()
        spread = SpreadAnalysis(symbol="SPY", relative_spread=0.00005)
        volume = VolumeAnalysis(symbol="SPY", avg_dollar_volume=500_000_000)
        result = scorer.score(spread, volume)
        d = result.to_dict()
        assert "score" in d
        assert "level" in d
        assert "spread_score" in d


# ===========================================================================
# Integration Tests
# ===========================================================================

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_liquidity_pipeline(self):
        """Spread -> Volume -> Impact -> Score."""
        bid, ask = _make_bid_ask(50, mid=150.0, spread=0.03)
        volume, close = _make_volume_close(50, avg_vol=5_000_000, price=150.0)

        engine = LiquidityEngine()
        spread = engine.analyze_spread(bid, ask, symbol="AAPL")
        vol_analysis = engine.analyze_volume(volume, close, symbol="AAPL")

        estimator = MarketImpactEstimator()
        impact = estimator.estimate_impact(
            trade_size=10000,
            avg_volume=vol_analysis.avg_volume,
            avg_spread=spread.avg_spread,
            volatility=0.015,
            price=150.0,
            symbol="AAPL",
        )

        scorer = LiquidityScorer()
        score = scorer.score(spread, vol_analysis, impact, price=150.0)

        assert score.symbol == "AAPL"
        assert score.score > 0
        assert score.level in list(LiquidityLevel)
        assert score.max_safe_shares > 0

    def test_snapshot_creation(self):
        """Create a full LiquiditySnapshot."""
        spread = SpreadAnalysis(symbol="MSFT", avg_spread=0.01)
        volume = VolumeAnalysis(symbol="MSFT", avg_volume=10_000_000)
        impact = MarketImpact(symbol="MSFT", trade_size=5000)
        liq_score = LiquidityScore(symbol="MSFT", score=85.0, level=LiquidityLevel.VERY_HIGH)

        snap = LiquiditySnapshot(
            symbol="MSFT",
            spread=spread,
            volume=volume,
            impact=impact,
            score=liq_score,
            date=date(2026, 1, 31),
        )
        d = snap.to_dict()
        assert d["symbol"] == "MSFT"
        assert d["spread"] is not None
        assert d["volume"] is not None
        assert d["impact"] is not None
        assert d["score"] is not None

    def test_universe_ranking(self):
        """Score multiple assets and rank by liquidity."""
        scorer = LiquidityScorer()

        assets = [
            ("SPY", 0.00005, 1_000_000_000),
            ("AAPL", 0.0002, 200_000_000),
            ("TINY", 0.01, 500_000),
        ]

        scores = []
        for sym, rel_spread, dollar_vol in assets:
            spread = SpreadAnalysis(symbol=sym, relative_spread=rel_spread)
            volume = VolumeAnalysis(symbol=sym, avg_dollar_volume=dollar_vol)
            s = scorer.score(spread, volume)
            scores.append(s)

        ranked = scorer.rank_universe(scores)
        assert ranked[0].symbol == "SPY"
        assert ranked[-1].symbol == "TINY"


# ===========================================================================
# Module Import Tests
# ===========================================================================

class TestModuleImports:
    """Test module imports work correctly."""

    def test_top_level_imports(self):
        from src.liquidity import (
            LiquidityEngine,
            MarketImpactEstimator,
            LiquidityScorer,
            LiquidityLevel,
            ImpactModel,
            SpreadAnalysis,
            VolumeAnalysis,
            MarketImpact,
            LiquidityScore,
            LiquiditySnapshot,
            DEFAULT_CONFIG,
        )
        assert LiquidityEngine is not None
        assert MarketImpactEstimator is not None
        assert LiquidityScorer is not None
