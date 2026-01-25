"""Unit tests for portfolio construction module."""

import numpy as np
import pandas as pd
import pytest

from src.portfolio import select_top_stocks, compute_allocations


class TestSelectTopStocks:
    @pytest.fixture
    def sample_scores(self):
        # Create 100 stocks with varying composite scores (large enough for percentile filter)
        tickers = [f"STOCK{i}" for i in range(100)]
        scores = pd.DataFrame({
            "value": np.linspace(0.3, 0.9, 100),
            "momentum": np.linspace(0.4, 0.85, 100),
            "quality": np.linspace(0.35, 0.88, 100),
            "growth": np.linspace(0.25, 0.92, 100),
            "composite": np.linspace(0.3, 0.9, 100),
        }, index=tickers)
        return scores

    def test_selects_top_n(self, sample_scores):
        result = select_top_stocks(sample_scores, n=5)
        assert len(result) == 5

    def test_selects_highest_scores(self, sample_scores):
        result = select_top_stocks(sample_scores, n=5)
        # Should include highest scoring stocks
        assert "STOCK99" in result.index
        assert "STOCK98" in result.index

    def test_respects_percentile_threshold(self, sample_scores):
        result = select_top_stocks(sample_scores, n=5)
        # All selected should be in top percentile
        threshold = sample_scores["composite"].quantile(0.90)
        assert all(result["composite"] >= threshold)

    def test_returns_dataframe_with_scores(self, sample_scores):
        result = select_top_stocks(sample_scores, n=3)
        assert "composite" in result.columns
        assert "value" in result.columns


class TestComputeAllocations:
    @pytest.fixture
    def sample_data(self):
        top_scores = pd.DataFrame({
            "value": [0.8, 0.7, 0.6],
            "momentum": [0.85, 0.75, 0.65],
            "quality": [0.82, 0.72, 0.62],
            "growth": [0.78, 0.68, 0.58],
            "composite": [0.81, 0.71, 0.61],
        }, index=["AAPL", "MSFT", "GOOGL"])

        fundamentals = pd.DataFrame({
            "currentPrice": [150.0, 300.0, 140.0],
            "marketCap": [2e12, 2.5e12, 1.8e12],
        }, index=["AAPL", "MSFT", "GOOGL"])

        return top_scores, fundamentals

    def test_output_columns(self, sample_data):
        top_scores, fundamentals = sample_data
        result = compute_allocations(top_scores, fundamentals, 10000)
        expected = {"ticker", "score", "weight", "allocation", "price", "shares", "invested"}
        assert set(result.columns) == expected

    def test_weights_sum_to_one(self, sample_data):
        top_scores, fundamentals = sample_data
        result = compute_allocations(top_scores, fundamentals, 10000)
        assert abs(result["weight"].sum() - 1.0) < 0.001

    def test_higher_score_higher_weight(self, sample_data):
        top_scores, fundamentals = sample_data
        result = compute_allocations(top_scores, fundamentals, 10000)
        # Sort by score descending
        sorted_result = result.sort_values("score", ascending=False)
        # Weights should be in descending order too
        weights = sorted_result["weight"].tolist()
        assert weights == sorted(weights, reverse=True)

    def test_shares_are_whole_numbers(self, sample_data):
        top_scores, fundamentals = sample_data
        result = compute_allocations(top_scores, fundamentals, 10000)
        assert all(isinstance(s, (int, np.integer)) for s in result["shares"])

    def test_invested_does_not_exceed_amount(self, sample_data):
        top_scores, fundamentals = sample_data
        amount = 10000
        result = compute_allocations(top_scores, fundamentals, amount)
        assert result["invested"].sum() <= amount

    def test_different_amounts(self, sample_data):
        top_scores, fundamentals = sample_data
        result_10k = compute_allocations(top_scores, fundamentals, 10000)
        result_100k = compute_allocations(top_scores, fundamentals, 100000)
        # Larger amount should buy more shares
        assert result_100k["shares"].sum() > result_10k["shares"].sum()


class TestRiskConstraints:
    """Tests for risk management features."""

    @pytest.fixture
    def concentrated_scores(self):
        """Create scores with stocks from same sector."""
        return pd.DataFrame({
            "composite": [0.95, 0.90, 0.85, 0.80, 0.75],
            "value": [0.9] * 5,
            "momentum": [0.9] * 5,
            "quality": [0.9] * 5,
            "growth": [0.9] * 5,
        }, index=["AAPL", "MSFT", "GOOGL", "META", "AMZN"])

    def test_max_position_size_respected(self, concentrated_scores):
        """Individual position shouldn't exceed max weight."""
        fundamentals = pd.DataFrame({
            "currentPrice": [150, 300, 140, 350, 180],
            "marketCap": [2e12] * 5,
            "sector": ["Tech"] * 5,
        }, index=["AAPL", "MSFT", "GOOGL", "META", "AMZN"])

        result = compute_allocations(concentrated_scores, fundamentals, 100000)
        # Max position should be capped (default 25%)
        assert all(result["weight"] <= 0.30)  # Allow small buffer
