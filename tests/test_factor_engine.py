"""Tests for Factor Engine v2."""

import numpy as np
import pandas as pd
import pytest

import config


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_prices():
    """Generate sample price data for 5 tickers over 300 days."""
    np.random.seed(42)
    dates = pd.bdate_range("2024-01-01", periods=300)
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

    # Generate random walk prices
    prices = pd.DataFrame(index=dates, columns=tickers)
    for ticker in tickers:
        returns = np.random.normal(0.0005, 0.02, 300)
        prices[ticker] = 100 * np.exp(np.cumsum(returns))

    return prices


@pytest.fixture
def sample_fundamentals():
    """Generate sample fundamental data for 5 tickers."""
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    return pd.DataFrame({
        "trailingPE": [25.0, 30.0, 22.0, 50.0, 18.0],
        "priceToBook": [12.0, 10.0, 5.0, 8.0, 4.0],
        "dividendYield": [0.006, 0.008, 0.0, 0.0, 0.0],
        "enterpriseToEbitda": [18.0, 22.0, 15.0, 35.0, 12.0],
        "returnOnEquity": [0.45, 0.40, 0.25, 0.15, 0.20],
        "debtToEquity": [1.5, 0.5, 0.1, 0.8, 0.2],
        "revenueGrowth": [0.08, 0.12, 0.15, 0.10, 0.20],
        "earningsGrowth": [0.10, 0.15, 0.12, 0.05, 0.25],
        "marketCap": [3e12, 2.5e12, 1.8e12, 1.5e12, 1e12],
        "currentPrice": [180.0, 380.0, 140.0, 175.0, 350.0],
        "sector": ["Technology", "Technology", "Technology", "Consumer", "Technology"],
    }, index=tickers)


@pytest.fixture
def sample_returns():
    """Generate sample momentum returns for 5 tickers."""
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    return pd.DataFrame({
        "ret_3m": [0.15, 0.10, 0.08, -0.05, 0.20],
        "ret_6m": [0.25, 0.18, 0.12, 0.05, 0.30],
        "ret_12m": [0.40, 0.30, 0.20, 0.10, 0.50],
    }, index=tickers)


# ============================================================================
# Factor Category Tests
# ============================================================================


class TestValueFactors:
    def test_compute_returns_series(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine.factors.value import ValueFactors

        factor = ValueFactors()
        scores = factor.compute(sample_prices, sample_fundamentals, sample_returns)

        assert isinstance(scores, pd.Series)
        assert len(scores) == len(sample_fundamentals)
        assert scores.between(0, 1).all()

    def test_low_pe_high_score(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine.factors.value import ValueFactors

        factor = ValueFactors()
        scores = factor.compute(sample_prices, sample_fundamentals, sample_returns)

        # META has lowest PE (18.0), should have high value score
        # AMZN has highest PE (50.0), should have low value score
        assert scores["META"] > scores["AMZN"]


class TestMomentumFactors:
    def test_compute_returns_series(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine.factors.momentum import MomentumFactors

        factor = MomentumFactors()
        scores = factor.compute(sample_prices, sample_fundamentals, sample_returns)

        assert isinstance(scores, pd.Series)
        assert len(scores) == len(sample_returns)
        assert scores.between(0, 1).all()

    def test_high_returns_high_score(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine.factors.momentum import MomentumFactors

        factor = MomentumFactors()
        scores = factor.compute(sample_prices, sample_fundamentals, sample_returns)

        # META has highest returns (0.50 12m), should score highest
        # AMZN has lowest 12m return (0.10), should score lower
        assert scores["META"] > scores["AMZN"]


class TestQualityFactors:
    def test_compute_returns_series(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine.factors.quality import QualityFactors

        factor = QualityFactors()
        scores = factor.compute(sample_prices, sample_fundamentals, sample_returns)

        assert isinstance(scores, pd.Series)
        assert len(scores) == len(sample_fundamentals)
        assert scores.between(0, 1).all()

    def test_high_roe_low_debt_high_score(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine.factors.quality import QualityFactors

        factor = QualityFactors()
        scores = factor.compute(sample_prices, sample_fundamentals, sample_returns)

        # AAPL has highest ROE (0.45), should score well
        # AMZN has lowest ROE (0.15) and moderate debt, should score lower
        assert scores["AAPL"] > scores["AMZN"]


class TestGrowthFactors:
    def test_compute_returns_series(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine.factors.growth import GrowthFactors

        factor = GrowthFactors()
        scores = factor.compute(sample_prices, sample_fundamentals, sample_returns)

        assert isinstance(scores, pd.Series)
        assert len(scores) == len(sample_fundamentals)
        assert scores.between(0, 1).all()

    def test_high_growth_high_score(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine.factors.growth import GrowthFactors

        factor = GrowthFactors()
        scores = factor.compute(sample_prices, sample_fundamentals, sample_returns)

        # META has highest earnings growth (0.25), should score highest
        assert scores["META"] == scores.max()


class TestVolatilityFactors:
    def test_compute_returns_series(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine.factors.volatility import VolatilityFactors

        factor = VolatilityFactors()
        scores = factor.compute(sample_prices, sample_fundamentals, sample_returns)

        assert isinstance(scores, pd.Series)
        assert len(scores) == len(sample_prices.columns)
        assert scores.between(0, 1).all()

    def test_sub_factors_computed(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine.factors.volatility import VolatilityFactors

        factor = VolatilityFactors()
        sub_scores = factor.compute_sub_factors(sample_prices, sample_fundamentals, sample_returns)

        assert isinstance(sub_scores, pd.DataFrame)
        # Should have at least some sub-factors
        assert len(sub_scores.columns) > 0


class TestTechnicalFactors:
    def test_compute_returns_series(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine.factors.technical import TechnicalFactors

        factor = TechnicalFactors()
        scores = factor.compute(sample_prices, sample_fundamentals, sample_returns)

        assert isinstance(scores, pd.Series)
        assert len(scores) == len(sample_prices.columns)
        assert scores.between(0, 1).all()

    def test_sub_factors_computed(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine.factors.technical import TechnicalFactors

        factor = TechnicalFactors()
        sub_scores = factor.compute_sub_factors(sample_prices, sample_fundamentals, sample_returns)

        assert isinstance(sub_scores, pd.DataFrame)
        assert len(sub_scores.columns) > 0


# ============================================================================
# Regime Detection Tests
# ============================================================================


class TestRegimeDetector:
    def test_classify_returns_regime(self):
        from src.factor_engine.regime import RegimeDetector, MarketRegime

        detector = RegimeDetector()
        regime = detector.classify(vix_level=20.0, yield_spread=0.5)

        assert isinstance(regime, MarketRegime)

    def test_crisis_on_high_vix(self):
        from src.factor_engine.regime import RegimeDetector, MarketRegime

        detector = RegimeDetector()
        regime = detector.classify(vix_level=40.0, yield_spread=0.5)

        assert regime == MarketRegime.CRISIS

    def test_bull_on_low_vix_uptrend(self):
        from src.factor_engine.regime import RegimeDetector, MarketRegime

        detector = RegimeDetector()
        # Create uptrending prices
        prices = pd.Series([100 + i for i in range(250)])
        regime = detector.classify(vix_level=12.0, sp500_prices=prices, yield_spread=1.0)

        assert regime == MarketRegime.BULL

    def test_bear_on_high_vix_downtrend(self):
        from src.factor_engine.regime import RegimeDetector, MarketRegime

        detector = RegimeDetector()
        # Create downtrending prices
        prices = pd.Series([200 - i for i in range(250)])
        regime = detector.classify(vix_level=28.0, sp500_prices=prices, yield_spread=-0.5)

        assert regime == MarketRegime.BEAR


# ============================================================================
# Adaptive Weights Tests
# ============================================================================


class TestAdaptiveWeightManager:
    def test_get_static_weights_v1(self):
        from src.factor_engine.weights import AdaptiveWeightManager

        manager = AdaptiveWeightManager()
        weights = manager.get_static_weights_v1()

        assert len(weights) == 4
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_get_static_weights_v2(self):
        from src.factor_engine.weights import AdaptiveWeightManager

        manager = AdaptiveWeightManager()
        weights = manager.get_static_weights_v2()

        assert len(weights) == 6
        assert abs(sum(weights.values()) - 1.0) < 0.01
        assert "volatility" in weights
        assert "technical" in weights

    def test_regime_weights_differ(self):
        from src.factor_engine.weights import AdaptiveWeightManager
        from src.factor_engine.regime import MarketRegime

        manager = AdaptiveWeightManager()
        bull_weights = manager.get_weights(regime=MarketRegime.BULL)
        bear_weights = manager.get_weights(regime=MarketRegime.BEAR)

        # Bull should favor momentum, bear should favor quality
        assert bull_weights["momentum"] > bear_weights["momentum"]
        assert bull_weights["quality"] < bear_weights["quality"]

    def test_weights_sum_to_one(self):
        from src.factor_engine.weights import AdaptiveWeightManager
        from src.factor_engine.regime import MarketRegime

        manager = AdaptiveWeightManager()

        for regime in MarketRegime:
            weights = manager.get_weights(regime=regime)
            assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_weight_constraints(self):
        from src.factor_engine.weights import AdaptiveWeightManager, MAX_WEIGHT, MIN_WEIGHT
        from src.factor_engine.regime import MarketRegime

        manager = AdaptiveWeightManager()

        for regime in MarketRegime:
            weights = manager.get_weights(regime=regime)
            for weight in weights.values():
                assert weight >= MIN_WEIGHT
                assert weight <= MAX_WEIGHT


# ============================================================================
# Sector Relative Scoring Tests
# ============================================================================


class TestSectorRelativeScorer:
    def test_compute_blended_scores(self, sample_fundamentals):
        from src.factor_engine.sector import SectorRelativeScorer

        scorer = SectorRelativeScorer()

        # Create universe scores
        universe_scores = pd.DataFrame({
            "value": [0.8, 0.7, 0.6, 0.5, 0.4],
            "momentum": [0.6, 0.7, 0.8, 0.5, 0.9],
        }, index=sample_fundamentals.index)

        sector_mapping = sample_fundamentals["sector"]
        blended = scorer.compute_blended_scores(universe_scores, sector_mapping)

        assert isinstance(blended, pd.DataFrame)
        assert blended.shape == universe_scores.shape

    def test_empty_sector_returns_universe(self, sample_fundamentals):
        from src.factor_engine.sector import SectorRelativeScorer

        scorer = SectorRelativeScorer()
        universe_scores = pd.DataFrame({
            "value": [0.8, 0.7, 0.6, 0.5, 0.4],
        }, index=sample_fundamentals.index)

        empty_sectors = pd.Series(dtype=str)
        blended = scorer.compute_blended_scores(universe_scores, empty_sectors)

        pd.testing.assert_frame_equal(blended, universe_scores)


# ============================================================================
# Factor Engine v2 Integration Tests
# ============================================================================


class TestFactorEngineV2:
    def test_compute_all_scores(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine import FactorEngineV2

        engine = FactorEngineV2()
        scores = engine.compute_all_scores(
            sample_prices, sample_fundamentals, sample_returns
        )

        assert isinstance(scores, pd.DataFrame)
        assert "value" in scores.columns
        assert "momentum" in scores.columns
        assert "quality" in scores.columns
        assert "growth" in scores.columns
        assert "volatility" in scores.columns
        assert "technical" in scores.columns
        assert "composite" in scores.columns
        assert "regime" in scores.columns

    def test_v1_compatible_scores(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine import FactorEngineV2

        engine = FactorEngineV2()
        scores = engine.compute_v1_compatible_scores(
            sample_prices, sample_fundamentals, sample_returns
        )

        # Should only have v1 columns
        assert set(scores.columns) == {"value", "momentum", "quality", "growth", "composite"}

    def test_scores_in_range(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine import FactorEngineV2

        engine = FactorEngineV2()
        scores = engine.compute_all_scores(
            sample_prices, sample_fundamentals, sample_returns
        )

        for col in ["value", "momentum", "quality", "growth", "volatility", "technical", "composite"]:
            assert scores[col].between(0, 1).all(), f"{col} scores out of range"

    def test_regime_tracked(self, sample_prices, sample_fundamentals, sample_returns):
        from src.factor_engine import FactorEngineV2

        engine = FactorEngineV2()
        engine.compute_all_scores(sample_prices, sample_fundamentals, sample_returns)

        assert engine.last_regime is not None
        assert engine.last_weights is not None


# ============================================================================
# Backward Compatibility Tests
# ============================================================================


class TestBackwardCompatibility:
    def test_v1_mode_unchanged(self, sample_fundamentals, sample_returns):
        """Test that v1 mode produces same results as before."""
        from src.factor_model import compute_composite_scores

        # Ensure v2 is disabled
        config.FACTOR_ENGINE_V2 = False

        scores = compute_composite_scores(sample_fundamentals, sample_returns)

        # Should have exactly v1 columns
        assert set(scores.columns) == {"value", "momentum", "quality", "growth", "composite"}

        # Check composite is correct weighted sum
        for ticker in scores.index:
            expected = (
                config.FACTOR_WEIGHTS["value"] * scores.loc[ticker, "value"]
                + config.FACTOR_WEIGHTS["momentum"] * scores.loc[ticker, "momentum"]
                + config.FACTOR_WEIGHTS["quality"] * scores.loc[ticker, "quality"]
                + config.FACTOR_WEIGHTS["growth"] * scores.loc[ticker, "growth"]
            )
            assert abs(scores.loc[ticker, "composite"] - expected) < 0.001

    def test_v2_mode_has_extra_columns(self, sample_prices, sample_fundamentals, sample_returns):
        """Test that v2 mode adds new columns."""
        from src.factor_model import compute_composite_scores

        # Enable v2
        config.FACTOR_ENGINE_V2 = True

        scores = compute_composite_scores(
            sample_fundamentals, sample_returns, prices=sample_prices
        )

        # Should have v2 columns
        assert "volatility" in scores.columns
        assert "technical" in scores.columns
        assert "regime" in scores.columns


# ============================================================================
# Factor Registry Tests
# ============================================================================


class TestFactorRegistry:
    def test_all_categories_registered(self):
        from src.factor_engine.factors import FactorRegistry

        registry = FactorRegistry()
        categories = registry.all()

        assert "value" in categories
        assert "momentum" in categories
        assert "quality" in categories
        assert "growth" in categories
        assert "volatility" in categories
        assert "technical" in categories

    def test_get_category(self):
        from src.factor_engine.factors import FactorRegistry, ValueFactors

        registry = FactorRegistry()
        value = registry.get("value")

        assert isinstance(value, ValueFactors)
