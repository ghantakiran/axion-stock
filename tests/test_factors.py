"""Tests for src/factors/ module — Factor, FactorCategory, FactorRegistry,
ValueFactors, MomentumFactors, QualityFactors, GrowthFactors,
VolatilityFactors, TechnicalFactors.
"""

import numpy as np
import pandas as pd
import pytest
from datetime import date

from src.factors.base import (
    Factor,
    FactorCategory,
    FactorCalculator,
    FactorDirection,
)
from src.factors.registry import FactorRegistry, create_default_registry
from src.factors.value import ValueFactors
from src.factors.momentum import MomentumFactors
from src.factors.quality import QualityFactors
from src.factors.growth import GrowthFactors
from src.factors.volatility import VolatilityFactors
from src.factors.technical import TechnicalFactors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
TICKERS = ["AAPL", "MSFT", "GOOG", "AMZN", "META"]


def _build_prices(n_days: int = 300, seed: int = 42) -> pd.DataFrame:
    """Build a synthetic price DataFrame (dates x tickers)."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(end=date.today(), periods=n_days)
    data = {}
    for ticker in TICKERS:
        returns = rng.normal(0.0005, 0.015, n_days)
        data[ticker] = 100 * np.cumprod(1 + returns)
    return pd.DataFrame(data, index=dates)


def _build_fundamentals() -> pd.DataFrame:
    """Build a synthetic fundamentals DataFrame (tickers x fields)."""
    data = {
        "trailingPE": [25.0, 30.0, 22.0, 40.0, 18.0],
        "priceToBook": [8.0, 12.0, 5.0, 15.0, 4.0],
        "dividendYield": [0.006, 0.008, 0.0, 0.0, 0.012],
        "enterpriseToEbitda": [18.0, 22.0, 15.0, 30.0, 12.0],
        "marketCap": [3e12, 2.5e12, 1.8e12, 1.5e12, 0.9e12],
        "returnOnEquity": [0.25, 0.30, 0.20, 0.15, 0.35],
        "debtToEquity": [1.5, 0.5, 0.3, 1.8, 0.2],
        "earningsGrowth": [0.10, 0.15, 0.08, 0.25, 0.05],
        "revenueGrowth": [0.08, 0.12, 0.06, 0.20, 0.03],
    }
    return pd.DataFrame(data, index=TICKERS)


# ---------------------------------------------------------------------------
# TestFactorBase
# ---------------------------------------------------------------------------
class TestFactorBase:
    def test_factor_creation(self):
        f = Factor(
            name="earnings_yield",
            description="EBIT / EV",
            direction=FactorDirection.POSITIVE,
            weight=0.2,
        )
        assert f.name == "earnings_yield"
        assert f.direction == FactorDirection.POSITIVE
        assert f.weight == 0.2

    def test_factor_hash(self):
        f1 = Factor(name="a", description="", direction=FactorDirection.POSITIVE)
        f2 = Factor(name="a", description="", direction=FactorDirection.NEGATIVE)
        assert hash(f1) == hash(f2)  # hash is by name only

    def test_factor_direction_enum(self):
        assert FactorDirection.POSITIVE.value == "positive"
        assert FactorDirection.NEGATIVE.value == "negative"


# ---------------------------------------------------------------------------
# TestFactorCategory
# ---------------------------------------------------------------------------
class TestFactorCategory:
    def test_creation(self):
        cat = FactorCategory(name="value", description="Value factors")
        assert cat.name == "value"
        assert cat.factors == []

    def test_add_factor(self):
        cat = FactorCategory(name="value", description="Value factors")
        f = Factor(name="pe", description="P/E ratio", direction=FactorDirection.NEGATIVE)
        cat.add_factor(f)
        assert len(cat.factors) == 1
        assert cat.factors[0].name == "pe"

    def test_default_weight(self):
        cat = FactorCategory(name="momentum", description="", default_weight=0.25)
        assert cat.default_weight == 0.25


# ---------------------------------------------------------------------------
# TestFactorCalculator (via concrete subclass)
# ---------------------------------------------------------------------------
class TestFactorCalculatorStaticMethods:
    def test_percentile_rank_ascending(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        ranked = FactorCalculator.percentile_rank(s, ascending=True)
        assert ranked.iloc[-1] == 1.0  # Highest value gets rank 1.0
        assert ranked.iloc[0] == 0.2   # Lowest gets 0.2 (1/5)

    def test_percentile_rank_descending(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        ranked = FactorCalculator.percentile_rank(s, ascending=False)
        assert ranked.iloc[0] == 0.8  # Lowest raw value gets highest rank

    def test_percentile_rank_with_nan(self):
        s = pd.Series([1.0, np.nan, 3.0])
        ranked = FactorCalculator.percentile_rank(s)
        assert ranked.iloc[1] == 0.5  # NaN filled with 0.5

    def test_winsorize(self):
        s = pd.Series([1, 2, 3, 4, 5, 100])
        w = FactorCalculator.winsorize(s, lower=0.01, upper=0.90)
        assert w.max() < 100  # Extreme value clipped

    def test_zscore(self):
        s = pd.Series([10, 20, 30, 40, 50])
        z = FactorCalculator.zscore(s)
        assert abs(z.mean()) < 1e-10
        assert abs(z.std() - 1.0) < 0.1

    def test_zscore_zero_std(self):
        s = pd.Series([5.0, 5.0, 5.0])
        z = FactorCalculator.zscore(s)
        assert (z == 0.0).all()

    def test_compute_returns(self):
        prices = _build_prices(100)
        returns = FactorCalculator.compute_returns(prices, 20)
        assert len(returns) == len(TICKERS)
        assert not returns.isna().all()

    def test_compute_returns_insufficient_data(self):
        prices = _build_prices(5)
        returns = FactorCalculator.compute_returns(prices, 100)
        # With fewer rows than requested periods, returns an empty series
        assert len(returns) == 0

    def test_combine_subfactors_equal_weight(self):
        calc = ValueFactors()  # Use concrete subclass
        scores = pd.DataFrame({
            "a": [0.8, 0.6, 0.4],
            "b": [0.2, 0.4, 0.6],
        }, index=["X", "Y", "Z"])
        combined = calc.combine_subfactors(scores)
        assert combined["X"] == pytest.approx(0.5)

    def test_combine_subfactors_custom_weights(self):
        calc = ValueFactors()
        scores = pd.DataFrame({
            "a": [1.0, 0.0],
            "b": [0.0, 1.0],
        }, index=["X", "Y"])
        combined = calc.combine_subfactors(scores, weights={"a": 0.75, "b": 0.25})
        assert combined["X"] == pytest.approx(0.75)
        assert combined["Y"] == pytest.approx(0.25)

    def test_combine_subfactors_empty(self):
        calc = ValueFactors()
        result = calc.combine_subfactors(pd.DataFrame())
        assert result.empty


# ---------------------------------------------------------------------------
# TestValueFactors
# ---------------------------------------------------------------------------
class TestValueFactors:
    def test_init_registers_factors(self):
        vf = ValueFactors()
        assert vf.category.name == "value"
        assert len(vf.category.factors) == 6

    def test_compute_returns_dataframe(self):
        vf = ValueFactors()
        prices = _build_prices()
        fundamentals = _build_fundamentals()
        scores = vf.compute(prices, fundamentals)
        assert isinstance(scores, pd.DataFrame)
        assert len(scores) == len(TICKERS)
        assert "earnings_yield" in scores.columns
        assert "ev_ebitda" in scores.columns

    def test_compute_scores_in_range(self):
        vf = ValueFactors()
        prices = _build_prices()
        fundamentals = _build_fundamentals()
        scores = vf.compute(prices, fundamentals)
        for col in scores.columns:
            assert scores[col].min() >= 0.0, f"{col} has value below 0"
            assert scores[col].max() <= 1.0, f"{col} has value above 1"

    def test_compute_missing_columns(self):
        vf = ValueFactors()
        prices = _build_prices()
        fundamentals = pd.DataFrame(index=TICKERS)  # Empty fundamentals
        scores = vf.compute(prices, fundamentals)
        # All scores should be 0.5 (default)
        assert (scores == 0.5).all().all()

    def test_get_composite_score(self):
        vf = ValueFactors()
        prices = _build_prices()
        fundamentals = _build_fundamentals()
        scores = vf.compute(prices, fundamentals)
        composite = vf.get_composite_score(scores)
        assert len(composite) == len(TICKERS)
        assert composite.min() >= 0.0
        assert composite.max() <= 1.0

    def test_default_weight(self):
        vf = ValueFactors()
        assert vf.category.default_weight == 0.20


# ---------------------------------------------------------------------------
# TestMomentumFactors
# ---------------------------------------------------------------------------
class TestMomentumFactors:
    def test_init_registers_factors(self):
        mf = MomentumFactors()
        assert mf.category.name == "momentum"
        assert len(mf.category.factors) == 6

    def test_compute_with_sufficient_data(self):
        mf = MomentumFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = mf.compute(prices, fundamentals)
        assert isinstance(scores, pd.DataFrame)
        assert "momentum_12_1" in scores.columns
        assert "high_52w_proximity" in scores.columns

    def test_compute_with_short_data(self):
        mf = MomentumFactors()
        prices = _build_prices(30)
        fundamentals = _build_fundamentals()
        scores = mf.compute(prices, fundamentals)
        # Short data defaults to 0.5
        assert scores["momentum_12_1"].eq(0.5).all()

    def test_scores_in_range(self):
        mf = MomentumFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = mf.compute(prices, fundamentals)
        for col in scores.columns:
            assert scores[col].min() >= 0.0
            assert scores[col].max() <= 1.0

    def test_get_composite_score(self):
        mf = MomentumFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = mf.compute(prices, fundamentals)
        composite = mf.get_composite_score(scores)
        assert len(composite) >= len(TICKERS)

    def test_default_weight(self):
        mf = MomentumFactors()
        assert mf.category.default_weight == 0.25


# ---------------------------------------------------------------------------
# TestQualityFactors
# ---------------------------------------------------------------------------
class TestQualityFactors:
    def test_init_registers_factors(self):
        qf = QualityFactors()
        assert qf.category.name == "quality"
        assert len(qf.category.factors) == 7

    def test_compute_with_fundamentals(self):
        qf = QualityFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = qf.compute(prices, fundamentals)
        assert "roe" in scores.columns
        assert "debt_equity" in scores.columns
        assert "interest_coverage" in scores.columns

    def test_compute_missing_fundamentals(self):
        qf = QualityFactors()
        prices = _build_prices()
        fundamentals = pd.DataFrame(index=TICKERS)
        scores = qf.compute(prices, fundamentals)
        assert (scores == 0.5).all().all()

    def test_scores_in_range(self):
        qf = QualityFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = qf.compute(prices, fundamentals)
        for col in scores.columns:
            assert scores[col].min() >= 0.0
            assert scores[col].max() <= 1.0

    def test_get_composite_score(self):
        qf = QualityFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = qf.compute(prices, fundamentals)
        composite = qf.get_composite_score(scores)
        assert len(composite) == len(TICKERS)


# ---------------------------------------------------------------------------
# TestGrowthFactors
# ---------------------------------------------------------------------------
class TestGrowthFactors:
    def test_init_registers_factors(self):
        gf = GrowthFactors()
        assert gf.category.name == "growth"
        assert len(gf.category.factors) == 6

    def test_compute_with_data(self):
        gf = GrowthFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = gf.compute(prices, fundamentals)
        assert "revenue_growth" in scores.columns
        assert "eps_growth" in scores.columns
        assert "growth_acceleration" in scores.columns

    def test_compute_missing_fundamentals(self):
        gf = GrowthFactors()
        prices = _build_prices()
        fundamentals = pd.DataFrame(index=TICKERS)
        scores = gf.compute(prices, fundamentals)
        assert (scores == 0.5).all().all()

    def test_get_composite_score(self):
        gf = GrowthFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = gf.compute(prices, fundamentals)
        composite = gf.get_composite_score(scores)
        assert len(composite) == len(TICKERS)

    def test_default_weight(self):
        gf = GrowthFactors()
        assert gf.category.default_weight == 0.15


# ---------------------------------------------------------------------------
# TestVolatilityFactors
# ---------------------------------------------------------------------------
class TestVolatilityFactors:
    def test_init_registers_factors(self):
        vf = VolatilityFactors()
        assert vf.category.name == "volatility"
        assert len(vf.category.factors) == 5

    def test_compute_with_sufficient_data(self):
        vf = VolatilityFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = vf.compute(prices, fundamentals)
        assert "realized_vol" in scores.columns
        assert "beta" in scores.columns
        assert "max_drawdown" in scores.columns

    def test_compute_with_short_data(self):
        vf = VolatilityFactors()
        prices = _build_prices(10)
        fundamentals = _build_fundamentals()
        scores = vf.compute(prices, fundamentals)
        # Short data defaults to 0.5
        assert (scores == 0.5).all().all()

    def test_compute_with_market_data(self):
        vf = VolatilityFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        market_data = pd.DataFrame({"SPY": prices["AAPL"].values * 1.1}, index=prices.index)
        scores = vf.compute(prices, fundamentals, market_data=market_data)
        assert isinstance(scores, pd.DataFrame)

    def test_scores_in_range(self):
        vf = VolatilityFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = vf.compute(prices, fundamentals)
        for col in scores.columns:
            assert scores[col].min() >= 0.0
            assert scores[col].max() <= 1.0

    def test_get_composite_score(self):
        vf = VolatilityFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = vf.compute(prices, fundamentals)
        composite = vf.get_composite_score(scores)
        assert len(composite) == len(TICKERS)


# ---------------------------------------------------------------------------
# TestTechnicalFactors
# ---------------------------------------------------------------------------
class TestTechnicalFactors:
    def test_init_registers_factors(self):
        tf = TechnicalFactors()
        assert tf.category.name == "technical"
        assert len(tf.category.factors) == 6

    def test_compute_with_sufficient_data(self):
        tf = TechnicalFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = tf.compute(prices, fundamentals)
        assert "rsi" in scores.columns
        assert "macd_signal" in scores.columns
        assert "bollinger_pct_b" in scores.columns
        assert "price_vs_200sma" in scores.columns

    def test_compute_with_short_data(self):
        tf = TechnicalFactors()
        prices = _build_prices(10)
        fundamentals = _build_fundamentals()
        scores = tf.compute(prices, fundamentals)
        assert (scores == 0.5).all().all()

    def test_scores_in_range(self):
        tf = TechnicalFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = tf.compute(prices, fundamentals)
        for col in scores.columns:
            assert scores[col].min() >= 0.0
            assert scores[col].max() <= 1.0

    def test_rsi_computation(self):
        tf = TechnicalFactors()
        prices = _build_prices(100)
        rsi = tf._compute_rsi(prices, period=14)
        assert len(rsi) == len(TICKERS)
        for val in rsi:
            assert 0 <= val <= 100

    def test_macd_computation(self):
        tf = TechnicalFactors()
        prices = _build_prices(100)
        macd = tf._compute_macd_signal(prices)
        assert len(macd) == len(TICKERS)
        assert not macd.isna().all()

    def test_bollinger_pct_b(self):
        tf = TechnicalFactors()
        prices = _build_prices(100)
        pct_b = tf._compute_bollinger_pct_b(prices, period=20)
        assert len(pct_b) == len(TICKERS)

    def test_get_composite_score(self):
        tf = TechnicalFactors()
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        scores = tf.compute(prices, fundamentals)
        composite = tf.get_composite_score(scores)
        assert len(composite) == len(TICKERS)


# ---------------------------------------------------------------------------
# TestFactorRegistry
# ---------------------------------------------------------------------------
class TestFactorRegistry:
    def test_init_empty(self):
        reg = FactorRegistry()
        assert reg.categories == []
        assert reg.total_factor_count() == 0

    def test_register_category(self):
        reg = FactorRegistry()
        cat = FactorCategory(name="value", description="Value factors")
        calc = ValueFactors()
        reg.register("value", cat, calc)
        assert "value" in reg.categories
        assert reg.get_category("value") is cat
        assert reg.get_calculator("value") is calc

    def test_get_category_unknown(self):
        reg = FactorRegistry()
        assert reg.get_category("unknown") is None

    def test_get_calculator_unknown(self):
        reg = FactorRegistry()
        assert reg.get_calculator("unknown") is None

    def test_compute_category(self):
        reg = FactorRegistry()
        vf = ValueFactors()
        reg.register("value", vf.category, vf)
        prices = _build_prices()
        fundamentals = _build_fundamentals()
        scores = reg.compute_category("value", prices, fundamentals)
        assert isinstance(scores, pd.DataFrame)
        assert "earnings_yield" in scores.columns

    def test_compute_category_unknown_raises(self):
        reg = FactorRegistry()
        with pytest.raises(ValueError, match="Unknown category"):
            reg.compute_category("unknown", pd.DataFrame(), pd.DataFrame())

    def test_compute_all(self):
        reg = FactorRegistry()
        vf = ValueFactors()
        mf = MomentumFactors()
        reg.register("value", vf.category, vf)
        reg.register("momentum", mf.category, mf)
        prices = _build_prices(300)
        fundamentals = _build_fundamentals()
        results = reg.compute_all(prices, fundamentals)
        assert "value" in results
        assert "momentum" in results

    def test_list_factors(self):
        reg = FactorRegistry()
        vf = ValueFactors()
        reg.register("value", vf.category, vf)
        listing = reg.list_factors()
        assert "value" in listing
        assert "earnings_yield" in listing["value"]

    def test_total_factor_count(self):
        reg = FactorRegistry()
        vf = ValueFactors()
        mf = MomentumFactors()
        reg.register("value", vf.category, vf)
        reg.register("momentum", mf.category, mf)
        assert reg.total_factor_count() == 12  # 6 value + 6 momentum

    def test_get_default_weights(self):
        reg = FactorRegistry()
        vf = ValueFactors()
        reg.register("value", vf.category, vf)
        weights = reg.get_default_weights()
        assert "value" in weights
        assert weights["value"] == 0.20

    def test_create_default_registry(self):
        reg = create_default_registry()
        assert reg._initialized is True
        assert len(reg.categories) == 6
        assert reg.total_factor_count() > 30
        assert "value" in reg.categories
        assert "momentum" in reg.categories
        assert "quality" in reg.categories
        assert "growth" in reg.categories
        assert "volatility" in reg.categories
        assert "technical" in reg.categories
