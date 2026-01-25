"""Unit tests for factor scoring module."""

import numpy as np
import pandas as pd
import pytest

from src.factor_model import (
    _percentile_rank,
    _invert_rank,
    compute_value_scores,
    compute_momentum_scores,
    compute_quality_scores,
    compute_growth_scores,
    compute_composite_scores,
)


class TestPercentileRank:
    def test_basic_ranking(self):
        series = pd.Series([1, 2, 3, 4, 5])
        result = _percentile_rank(series)
        assert result.iloc[0] == 0.2  # lowest
        assert result.iloc[-1] == 1.0  # highest

    def test_nan_filled_with_median(self):
        series = pd.Series([1, np.nan, 3, np.nan, 5])
        result = _percentile_rank(series)
        assert result.iloc[1] == 0.5
        assert result.iloc[3] == 0.5

    def test_output_range(self):
        series = pd.Series(np.random.randn(100))
        result = _percentile_rank(series)
        assert result.min() > 0
        assert result.max() <= 1.0


class TestInvertRank:
    def test_inversion(self):
        series = pd.Series([1, 2, 3, 4, 5])
        result = _invert_rank(series)
        # Lower values should get higher scores
        assert result.iloc[0] > result.iloc[-1]

    def test_range(self):
        series = pd.Series([10, 20, 30])
        result = _invert_rank(series)
        assert all(0 <= v <= 1 for v in result)


class TestValueScores:
    @pytest.fixture
    def sample_fundamentals(self):
        return pd.DataFrame({
            "trailingPE": [10, 20, 30, 40, 50],
            "priceToBook": [1, 2, 3, 4, 5],
            "enterpriseToEbitda": [5, 10, 15, 20, 25],
            "dividendYield": [0.05, 0.04, 0.03, 0.02, 0.01],
        }, index=["A", "B", "C", "D", "E"])

    def test_output_shape(self, sample_fundamentals):
        result = compute_value_scores(sample_fundamentals)
        assert len(result) == 5
        assert all(idx in result.index for idx in ["A", "B", "C", "D", "E"])

    def test_low_pe_high_score(self, sample_fundamentals):
        result = compute_value_scores(sample_fundamentals)
        # Stock A has lowest PE, should have highest value score
        assert result["A"] > result["E"]

    def test_output_range(self, sample_fundamentals):
        result = compute_value_scores(sample_fundamentals)
        assert all(0 <= v <= 1 for v in result)


class TestMomentumScores:
    @pytest.fixture
    def sample_returns(self):
        return pd.DataFrame({
            "ret_6m": [0.30, 0.20, 0.10, 0.00, -0.10],
            "ret_12m": [0.50, 0.40, 0.30, 0.20, 0.10],
        }, index=["A", "B", "C", "D", "E"])

    def test_output_shape(self, sample_returns):
        result = compute_momentum_scores(sample_returns)
        assert len(result) == 5

    def test_high_returns_high_score(self, sample_returns):
        result = compute_momentum_scores(sample_returns)
        # Stock A has highest returns, should have highest momentum
        assert result["A"] > result["E"]

    def test_output_range(self, sample_returns):
        result = compute_momentum_scores(sample_returns)
        assert all(0 <= v <= 1 for v in result)


class TestQualityScores:
    @pytest.fixture
    def sample_fundamentals(self):
        return pd.DataFrame({
            "returnOnEquity": [0.30, 0.25, 0.20, 0.15, 0.10],
            "debtToEquity": [0.2, 0.4, 0.6, 0.8, 1.0],
        }, index=["A", "B", "C", "D", "E"])

    def test_high_roe_low_debt_high_score(self, sample_fundamentals):
        result = compute_quality_scores(sample_fundamentals)
        # Stock A has highest ROE and lowest D/E
        assert result["A"] > result["E"]


class TestGrowthScores:
    @pytest.fixture
    def sample_fundamentals(self):
        return pd.DataFrame({
            "revenueGrowth": [0.30, 0.20, 0.10, 0.05, -0.05],
            "earningsGrowth": [0.40, 0.30, 0.20, 0.10, 0.00],
        }, index=["A", "B", "C", "D", "E"])

    def test_high_growth_high_score(self, sample_fundamentals):
        result = compute_growth_scores(sample_fundamentals)
        assert result["A"] > result["E"]


class TestCompositeScores:
    @pytest.fixture
    def sample_data(self):
        fundamentals = pd.DataFrame({
            "trailingPE": [10, 20, 30],
            "priceToBook": [1, 2, 3],
            "enterpriseToEbitda": [5, 10, 15],
            "dividendYield": [0.05, 0.03, 0.01],
            "returnOnEquity": [0.30, 0.20, 0.10],
            "debtToEquity": [0.2, 0.5, 1.0],
            "revenueGrowth": [0.25, 0.15, 0.05],
            "earningsGrowth": [0.30, 0.20, 0.10],
        }, index=["A", "B", "C"])

        returns = pd.DataFrame({
            "ret_6m": [0.25, 0.15, 0.05],
            "ret_12m": [0.40, 0.25, 0.10],
        }, index=["A", "B", "C"])

        return fundamentals, returns

    def test_output_columns(self, sample_data):
        fund, ret = sample_data
        result = compute_composite_scores(fund, ret)
        expected_cols = {"value", "momentum", "quality", "growth", "composite"}
        assert set(result.columns) == expected_cols

    def test_composite_is_weighted_sum(self, sample_data):
        fund, ret = sample_data
        result = compute_composite_scores(fund, ret)
        # Verify composite is weighted sum of factors
        for idx in result.index:
            row = result.loc[idx]
            expected = (
                0.25 * row["value"]
                + 0.30 * row["momentum"]
                + 0.25 * row["quality"]
                + 0.20 * row["growth"]
            )
            assert abs(row["composite"] - expected) < 0.001

    def test_all_scores_in_range(self, sample_data):
        fund, ret = sample_data
        result = compute_composite_scores(fund, ret)
        for col in result.columns:
            assert all(0 <= v <= 1 for v in result[col])
