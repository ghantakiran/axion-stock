"""Tests for PRD-51: Risk Decomposition & Performance Contribution."""

import pytest
import numpy as np
import pandas as pd

from src.attribution.risk import RiskDecomposer
from src.attribution.performance import (
    PositionContribution,
    ContributionSummary,
    PerformanceContributor,
)


def _make_correlated_returns(n=100, seed=42):
    """Generate correlated returns for 4 positions."""
    rng = np.random.RandomState(seed)
    # Base factor
    market = rng.normal(0.0005, 0.012, n)
    # Position-specific
    returns = pd.DataFrame({
        "AAPL": market + rng.normal(0.0002, 0.008, n),
        "MSFT": market + rng.normal(0.0001, 0.006, n),
        "GOOGL": market * 1.2 + rng.normal(0.0003, 0.010, n),
        "AMZN": market * 0.8 + rng.normal(0.0001, 0.009, n),
    }, index=pd.bdate_range("2025-01-02", periods=n))
    return returns


# ── PositionContribution Model Tests ────────────────────────────────


class TestPositionContribution:
    """Test PositionContribution dataclass."""

    def test_basic_creation(self):
        pc = PositionContribution(
            symbol="AAPL", weight=0.25, return_=0.10,
            contribution=0.025, pct_of_total=0.50,
        )
        assert pc.symbol == "AAPL"
        assert pc.contribution == 0.025

    def test_defaults(self):
        pc = PositionContribution(symbol="X")
        assert pc.weight == 0.0
        assert pc.return_ == 0.0
        assert pc.contribution == 0.0
        assert pc.sector == ""


class TestContributionSummary:
    """Test ContributionSummary dataclass."""

    def test_hit_rate(self):
        cs = ContributionSummary(n_positive=7, n_negative=3)
        assert abs(cs.hit_rate - 0.7) < 1e-10

    def test_hit_rate_zero(self):
        cs = ContributionSummary(n_positive=0, n_negative=0)
        assert cs.hit_rate == 0.0

    def test_concentration(self):
        top = [
            PositionContribution(symbol="A", contribution=0.05),
            PositionContribution(symbol="B", contribution=0.03),
        ]
        cs = ContributionSummary(
            total_return=0.10, top_contributors=top,
        )
        # (0.05 + 0.03) / 0.10 = 0.80
        assert abs(cs.concentration - 0.80) < 1e-10

    def test_concentration_zero_return(self):
        cs = ContributionSummary(total_return=0.0)
        assert cs.concentration == 0.0


# ── RiskDecomposer Tests ────────────────────────────────────────────


class TestRiskDecomposer:
    """Test risk-based decomposition."""

    def test_basic_decomposition(self):
        decomposer = RiskDecomposer()
        returns = _make_correlated_returns()
        weights = {"AAPL": 0.30, "MSFT": 0.25, "GOOGL": 0.25, "AMZN": 0.20}

        result = decomposer.decompose(weights, returns)

        assert len(result) == 4
        # Component risks should sum to portfolio vol
        total_cr = sum(r["component_risk"] for r in result)
        port_vol = np.sqrt(
            np.array([0.30, 0.25, 0.25, 0.20])
            @ (np.cov(returns.values, rowvar=False, ddof=1) * 252)
            @ np.array([0.30, 0.25, 0.25, 0.20])
        )
        assert abs(total_cr - port_vol) < 1e-6

    def test_pct_contributions_sum_to_one(self):
        decomposer = RiskDecomposer()
        returns = _make_correlated_returns()
        weights = {"AAPL": 0.30, "MSFT": 0.25, "GOOGL": 0.25, "AMZN": 0.20}

        result = decomposer.decompose(weights, returns)
        total_pct = sum(r["pct_contribution"] for r in result)
        assert abs(total_pct - 1.0) < 1e-6

    def test_marginal_risk_positive(self):
        decomposer = RiskDecomposer()
        returns = _make_correlated_returns()
        weights = {"AAPL": 0.50, "MSFT": 0.50}

        result = decomposer.decompose(weights, returns)
        for r in result:
            # With positive correlations, marginal risk should be positive
            assert r["marginal_risk"] > 0

    def test_individual_volatility(self):
        decomposer = RiskDecomposer()
        returns = _make_correlated_returns()
        weights = {"AAPL": 0.50, "MSFT": 0.50}

        result = decomposer.decompose(weights, returns)
        for r in result:
            assert r["volatility"] > 0

    def test_insufficient_data(self):
        decomposer = RiskDecomposer()
        returns = pd.DataFrame({"A": [0.01], "B": [0.02]})
        result = decomposer.decompose({"A": 0.5, "B": 0.5}, returns)
        assert result == []

    def test_insufficient_positions(self):
        decomposer = RiskDecomposer()
        returns = pd.DataFrame({"A": [0.01, 0.02, 0.03]})
        result = decomposer.decompose({"A": 1.0}, returns)
        assert result == []

    def test_no_annualize(self):
        decomposer = RiskDecomposer()
        returns = _make_correlated_returns()
        weights = {"AAPL": 0.50, "MSFT": 0.50}

        ann = decomposer.decompose(weights, returns, annualize=True)
        raw = decomposer.decompose(weights, returns, annualize=False)

        # Annualized should have larger risk values
        assert ann[0]["component_risk"] > raw[0]["component_risk"]

    def test_sector_decomposition(self):
        decomposer = RiskDecomposer()
        returns = _make_correlated_returns()
        weights = {"AAPL": 0.30, "MSFT": 0.25, "GOOGL": 0.25, "AMZN": 0.20}
        sector_map = {
            "AAPL": "Tech", "MSFT": "Tech",
            "GOOGL": "Comm", "AMZN": "Consumer",
        }

        result = decomposer.decompose_by_sector(
            weights, returns, sector_map,
        )

        assert len(result) == 3
        sectors = {r["sector"] for r in result}
        assert "Tech" in sectors
        assert "Comm" in sectors
        assert "Consumer" in sectors

        # Sector weights should sum to 1
        total_w = sum(r["weight"] for r in result)
        assert abs(total_w - 1.0) < 1e-10

    def test_tracking_error_decomposition(self):
        decomposer = RiskDecomposer()
        returns = _make_correlated_returns()

        port_w = {"AAPL": 0.35, "MSFT": 0.25, "GOOGL": 0.25, "AMZN": 0.15}
        bm_w = {"AAPL": 0.25, "MSFT": 0.25, "GOOGL": 0.25, "AMZN": 0.25}

        result = decomposer.tracking_error_decomposition(
            port_w, bm_w, returns,
        )

        assert len(result) == 4
        # Active weights should sum to 0
        total_active = sum(r["active_weight"] for r in result)
        assert abs(total_active) < 1e-10

    def test_tracking_error_zero_for_same_weights(self):
        decomposer = RiskDecomposer()
        returns = _make_correlated_returns()
        weights = {"AAPL": 0.25, "MSFT": 0.25, "GOOGL": 0.25, "AMZN": 0.25}

        result = decomposer.tracking_error_decomposition(
            weights, weights, returns,
        )
        # Same weights → zero active weights → empty result (zero TE var)
        assert result == []

    def test_missing_columns(self):
        decomposer = RiskDecomposer()
        returns = _make_correlated_returns()
        # Weight for non-existent column
        weights = {"AAPL": 0.50, "MISSING": 0.50}
        result = decomposer.decompose(weights, returns)
        assert result == []


# ── PerformanceContributor Tests ────────────────────────────────────


class TestPerformanceContributor:
    """Test performance contribution analysis."""

    def test_basic_contributions(self):
        pc = PerformanceContributor()
        weights = {"AAPL": 0.30, "MSFT": 0.40, "GOOGL": 0.30}
        returns = {"AAPL": 0.10, "MSFT": 0.05, "GOOGL": -0.03}

        result = pc.analyze(weights, returns)

        expected_total = 0.30 * 0.10 + 0.40 * 0.05 + 0.30 * (-0.03)
        assert abs(result.total_return - expected_total) < 1e-10
        assert len(result.positions) == 3
        assert result.n_positive == 2
        assert result.n_negative == 1

    def test_positions_sorted_descending(self):
        pc = PerformanceContributor()
        weights = {"A": 0.50, "B": 0.50}
        returns = {"A": -0.05, "B": 0.10}

        result = pc.analyze(weights, returns)
        # First position should have highest contribution
        assert result.positions[0].symbol == "B"

    def test_pct_of_total(self):
        pc = PerformanceContributor()
        weights = {"A": 0.50, "B": 0.50}
        returns = {"A": 0.10, "B": 0.10}

        result = pc.analyze(weights, returns)
        for p in result.positions:
            assert abs(p.pct_of_total - 0.5) < 1e-10

    def test_top_bottom_contributors(self):
        pc = PerformanceContributor(top_n=2)
        weights = {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}
        returns = {"A": 0.10, "B": -0.05, "C": 0.08, "D": -0.02}

        result = pc.analyze(weights, returns)
        assert len(result.top_contributors) == 2
        assert result.top_contributors[0].symbol == "A"
        assert len(result.bottom_contributors) == 2
        assert result.bottom_contributors[0].symbol == "B"

    def test_sector_contributions(self):
        pc = PerformanceContributor()
        weights = {"AAPL": 0.30, "MSFT": 0.30, "JPM": 0.40}
        returns = {"AAPL": 0.10, "MSFT": 0.08, "JPM": 0.05}
        sector_map = {"AAPL": "Tech", "MSFT": "Tech", "JPM": "Finance"}

        result = pc.sector_contributions(weights, returns, sector_map)

        assert len(result) == 2
        tech = next(s for s in result if s["sector"] == "Tech")
        assert abs(tech["weight"] - 0.60) < 1e-10
        expected_tech = 0.30 * 0.10 + 0.30 * 0.08
        assert abs(tech["contribution"] - expected_tech) < 1e-10

    def test_relative_contributions(self):
        pc = PerformanceContributor()
        port_w = {"A": 0.60, "B": 0.40}
        port_r = {"A": 0.10, "B": 0.05}
        bm_w = {"A": 0.50, "B": 0.50}
        bm_r = {"A": 0.08, "B": 0.06}

        result = pc.relative_contributions(port_w, port_r, bm_w, bm_r)

        # Port: 0.60*0.10 + 0.40*0.05 = 0.08
        # BM:   0.50*0.08 + 0.50*0.06 = 0.07
        # Active = 0.01
        assert abs(result.total_return - 0.01) < 1e-10
        assert len(result.positions) == 2

    def test_relative_missing_in_benchmark(self):
        pc = PerformanceContributor()
        result = pc.relative_contributions(
            {"A": 0.50, "B": 0.50},
            {"A": 0.10, "B": 0.05},
            {"A": 0.50, "C": 0.50},
            {"A": 0.08, "C": 0.03},
        )
        # Should handle A (in both), B (port only), C (bm only)
        assert len(result.positions) == 3

    def test_cumulative_contributions(self):
        pc = PerformanceContributor()
        dates = pd.bdate_range("2025-01-02", periods=5)
        daily_w = pd.DataFrame(
            {"A": [0.6] * 5, "B": [0.4] * 5},
            index=dates,
        )
        daily_r = pd.DataFrame(
            {"A": [0.01, 0.02, -0.01, 0.01, 0.03],
             "B": [-0.01, 0.01, 0.02, -0.01, 0.01]},
            index=dates,
        )

        result = pc.cumulative_contributions(daily_w, daily_r)
        assert result.shape == (5, 2)
        # Last row should be cumulative sum of daily contributions
        assert abs(result.iloc[-1]["A"] - 0.6 * (0.01 + 0.02 - 0.01 + 0.01 + 0.03)) < 1e-10

    def test_cumulative_empty(self):
        pc = PerformanceContributor()
        result = pc.cumulative_contributions(
            pd.DataFrame(), pd.DataFrame(),
        )
        assert result.empty

    def test_analyze_with_sectors(self):
        pc = PerformanceContributor()
        weights = {"A": 0.50, "B": 0.50}
        returns = {"A": 0.10, "B": -0.05}
        sector_map = {"A": "Tech", "B": "Finance"}

        result = pc.analyze(weights, returns, sector_map)
        for p in result.positions:
            assert p.sector != ""

    def test_hit_rate_via_analyze(self):
        pc = PerformanceContributor()
        weights = {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}
        returns = {"A": 0.10, "B": 0.05, "C": 0.08, "D": -0.02}

        result = pc.analyze(weights, returns)
        assert abs(result.hit_rate - 0.75) < 1e-10


# ── Integration Tests ───────────────────────────────────────────────


class TestIntegration:
    """Integration tests combining risk and performance."""

    def test_risk_and_performance_together(self):
        """Compute both risk decomp and performance contribution."""
        returns = _make_correlated_returns(100)
        weights = {"AAPL": 0.30, "MSFT": 0.25, "GOOGL": 0.25, "AMZN": 0.20}

        # Risk decomposition
        rd = RiskDecomposer()
        risk = rd.decompose(weights, returns)
        assert len(risk) == 4

        # Performance contribution (single period)
        period_returns = {
            col: float(returns[col].sum()) for col in returns.columns
        }
        pc = PerformanceContributor()
        perf = pc.analyze(weights, period_returns)
        assert len(perf.positions) == 4

        # Verify names match
        risk_names = {r["name"] for r in risk}
        perf_names = {p.symbol for p in perf.positions}
        assert risk_names == perf_names

    def test_module_imports(self):
        """Verify new exports are accessible."""
        from src.attribution import (
            RiskDecomposer,
            PerformanceContributor,
            PositionContribution,
            ContributionSummary,
        )
        assert RiskDecomposer is not None
        assert PerformanceContributor is not None
