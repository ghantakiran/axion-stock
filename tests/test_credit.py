"""Tests for PRD-53: Credit Risk Analysis."""

import pytest
import numpy as np
from datetime import date, timedelta

from src.credit.config import (
    CreditRating,
    RatingOutlook,
    SpreadType,
    DefaultModel,
    RATING_ORDER,
    INVESTMENT_GRADE,
    DEFAULT_CREDIT_CONFIG,
)
from src.credit.models import (
    CreditSpread,
    SpreadSummary,
    DefaultProbability,
    RatingSnapshot,
    RatingTransition,
    DebtItem,
    DebtStructure,
)
from src.credit.spreads import SpreadAnalyzer
from src.credit.default import DefaultEstimator
from src.credit.rating import RatingTracker
from src.credit.structure import DebtAnalyzer


# ── Config Tests ────────────────────────────────────────────────────


class TestConfig:
    """Test configuration."""

    def test_enums(self):
        assert len(CreditRating) == 8
        assert len(RatingOutlook) == 4
        assert len(SpreadType) == 3
        assert len(DefaultModel) == 3

    def test_rating_order(self):
        assert RATING_ORDER[CreditRating.AAA] < RATING_ORDER[CreditRating.D]
        assert RATING_ORDER[CreditRating.BBB] < RATING_ORDER[CreditRating.BB]

    def test_investment_grade(self):
        assert CreditRating.AAA in INVESTMENT_GRADE
        assert CreditRating.BBB in INVESTMENT_GRADE
        assert CreditRating.BB not in INVESTMENT_GRADE

    def test_default_config(self):
        c = DEFAULT_CREDIT_CONFIG
        assert c.default.default_recovery_rate == 0.40
        assert c.spread.lookback_periods == 252
        assert c.structure.high_leverage_threshold == 4.0


# ── Model Tests ─────────────────────────────────────────────────────


class TestModels:
    """Test data models."""

    def test_credit_spread_pct(self):
        s = CreditSpread(symbol="X", spread_bps=150)
        assert abs(s.spread_pct - 1.5) < 1e-10

    def test_credit_spread_wide(self):
        s = CreditSpread(symbol="X", z_score=1.5)
        assert s.is_wide
        assert not s.is_tight

    def test_credit_spread_tight(self):
        s = CreditSpread(symbol="X", z_score=-1.5)
        assert s.is_tight

    def test_spread_summary_widening(self):
        s = SpreadSummary(symbol="X", trend=5.0, min_spread=100, max_spread=200)
        assert s.is_widening
        assert abs(s.range_bps - 100) < 1e-10

    def test_default_probability_survival(self):
        dp = DefaultProbability(symbol="X", pd_1y=0.02, pd_5y=0.10, recovery_rate=0.40)
        assert abs(dp.survival_1y - 0.98) < 1e-10
        assert abs(dp.survival_5y - 0.90) < 1e-10
        assert abs(dp.expected_loss_1y - 0.012) < 1e-10

    def test_rating_snapshot_investment_grade(self):
        r = RatingSnapshot(symbol="X", rating=CreditRating.A)
        assert r.is_investment_grade

    def test_rating_snapshot_high_yield(self):
        r = RatingSnapshot(symbol="X", rating=CreditRating.BB)
        assert not r.is_investment_grade

    def test_rating_migration_upgrade(self):
        r = RatingSnapshot(
            symbol="X", rating=CreditRating.A,
            previous_rating=CreditRating.BBB,
        )
        assert r.migration_direction == "upgrade"

    def test_rating_migration_downgrade(self):
        r = RatingSnapshot(
            symbol="X", rating=CreditRating.BB,
            previous_rating=CreditRating.BBB,
        )
        assert r.migration_direction == "downgrade"

    def test_rating_migration_stable(self):
        r = RatingSnapshot(symbol="X", rating=CreditRating.A)
        assert r.migration_direction == "stable"

    def test_rating_transition_upgrade(self):
        t = RatingTransition(
            from_rating=CreditRating.BBB, to_rating=CreditRating.A,
        )
        assert t.is_upgrade
        assert not t.is_downgrade

    def test_debt_item_years_to_maturity(self):
        future = date.today() + timedelta(days=730)
        d = DebtItem(name="Bond", amount=100e6, maturity_date=future)
        assert abs(d.years_to_maturity - 2.0) < 0.1

    def test_debt_structure_high_leverage(self):
        ds = DebtStructure(symbol="X", leverage_ratio=5.0, interest_coverage=1.5)
        assert ds.is_high_leverage
        assert ds.is_low_coverage

    def test_debt_structure_healthy(self):
        ds = DebtStructure(symbol="X", leverage_ratio=2.0, interest_coverage=5.0)
        assert not ds.is_high_leverage
        assert not ds.is_low_coverage


# ── SpreadAnalyzer Tests ────────────────────────────────────────────


class TestSpreadAnalyzer:
    """Test spread analyzer."""

    def test_add_and_analyze(self):
        sa = SpreadAnalyzer()
        for bps in [100, 110, 105, 120, 115]:
            sa.add_spread(CreditSpread(symbol="X", spread_bps=bps))

        summary = sa.analyze("X")
        assert summary.n_observations == 5
        assert summary.current_spread == 115
        assert summary.avg_spread > 0

    def test_z_score_computation(self):
        sa = SpreadAnalyzer()
        for bps in [100, 105, 98, 102, 200]:
            sa.add_spread(CreditSpread(symbol="X", spread_bps=bps))

        # Last observation (200) should have positive z-score
        history = sa.get_history("X")
        assert history[-1].z_score > 0

    def test_trend_widening(self):
        sa = SpreadAnalyzer()
        for i, bps in enumerate([100, 110, 120, 130, 140]):
            sa.add_spread(CreditSpread(symbol="X", spread_bps=bps))

        summary = sa.analyze("X")
        assert summary.is_widening
        assert summary.trend > 0

    def test_term_structure(self):
        sa = SpreadAnalyzer()
        sa.add_spread(CreditSpread(symbol="X", spread_bps=80, term=2.0))
        sa.add_spread(CreditSpread(symbol="X", spread_bps=120, term=5.0))
        sa.add_spread(CreditSpread(symbol="X", spread_bps=160, term=10.0))

        ts = sa.term_structure("X")
        assert len(ts) == 3
        assert ts[0]["term"] == 2.0
        assert ts[2]["term"] == 10.0

    def test_relative_value(self):
        sa = SpreadAnalyzer()
        for bps in [100, 100, 100, 200]:
            sa.add_spread(CreditSpread(symbol="A", spread_bps=bps))
        for bps in [150, 150, 150, 150]:
            sa.add_spread(CreditSpread(symbol="B", spread_bps=bps))

        rv = sa.relative_value(["A", "B"])
        assert len(rv) == 2
        # A has wider z-score (200 vs avg 100)
        assert rv[0]["symbol"] == "A"

    def test_empty_analyze(self):
        sa = SpreadAnalyzer()
        summary = sa.analyze("UNKNOWN")
        assert summary.n_observations == 0

    def test_reset(self):
        sa = SpreadAnalyzer()
        sa.add_spread(CreditSpread(symbol="X", spread_bps=100))
        sa.reset()
        assert sa.analyze("X").n_observations == 0


# ── DefaultEstimator Tests ──────────────────────────────────────────


class TestDefaultEstimator:
    """Test default probability estimator."""

    def test_merton_healthy_firm(self):
        de = DefaultEstimator()
        result = de.merton_model(
            symbol="AAPL",
            equity_value=3_000e9,
            debt_face=100e9,
            equity_vol=0.25,
        )
        assert result.pd_1y < 0.01  # Very low PD for healthy firm
        assert result.distance_to_default > 2.0
        assert result.model == DefaultModel.MERTON

    def test_merton_distressed_firm(self):
        de = DefaultEstimator()
        result = de.merton_model(
            symbol="DIST",
            equity_value=50e6,
            debt_face=500e6,
            equity_vol=0.80,
        )
        assert result.pd_1y > 0.01  # Higher PD than healthy firm
        assert result.distance_to_default < 3.0

    def test_merton_invalid_inputs(self):
        de = DefaultEstimator()
        result = de.merton_model(
            symbol="X", equity_value=0, debt_face=100, equity_vol=0.3,
        )
        assert result.pd_1y == 0.0

    def test_merton_5y_pd(self):
        de = DefaultEstimator()
        result = de.merton_model(
            symbol="X", equity_value=1e9, debt_face=500e6, equity_vol=0.30,
        )
        assert result.pd_5y >= result.pd_1y

    def test_cds_implied(self):
        de = DefaultEstimator()
        result = de.cds_implied("X", cds_spread_bps=100)
        # PD = 100/10000 / (1 - 0.40) = 0.01 / 0.60 ≈ 0.0167
        assert abs(result.pd_1y - 100 / 10000 / 0.60) < 1e-4
        assert result.model == DefaultModel.CDS_IMPLIED

    def test_cds_implied_zero(self):
        de = DefaultEstimator()
        result = de.cds_implied("X", cds_spread_bps=0)
        assert result.pd_1y == 0.0

    def test_cds_implied_5y(self):
        de = DefaultEstimator()
        result = de.cds_implied("X", cds_spread_bps=200)
        assert result.pd_5y > result.pd_1y

    def test_statistical_safe(self):
        de = DefaultEstimator()
        result = de.statistical_model(
            symbol="SAFE",
            working_capital_to_assets=0.30,
            retained_earnings_to_assets=0.40,
            ebit_to_assets=0.15,
            equity_to_debt=2.0,
            sales_to_assets=1.5,
        )
        # High Z-score → low PD
        assert result.pd_1y < 0.15
        assert result.distance_to_default > 2.5
        assert result.model == DefaultModel.STATISTICAL

    def test_statistical_distressed(self):
        de = DefaultEstimator()
        result = de.statistical_model(
            symbol="DIST",
            working_capital_to_assets=-0.10,
            retained_earnings_to_assets=-0.20,
            ebit_to_assets=-0.05,
            equity_to_debt=0.3,
            sales_to_assets=0.5,
        )
        assert result.pd_1y > 0.30


# ── RatingTracker Tests ─────────────────────────────────────────────


class TestRatingTracker:
    """Test rating tracker."""

    def test_add_and_get_history(self):
        rt = RatingTracker()
        rt.add_rating(RatingSnapshot(
            symbol="X", rating=CreditRating.A, as_of=date(2024, 1, 1),
        ))
        rt.add_rating(RatingSnapshot(
            symbol="X", rating=CreditRating.BBB, as_of=date(2025, 1, 1),
        ))

        history = rt.get_history("X")
        assert len(history) == 2
        assert history[0].as_of > history[1].as_of  # Most recent first

    def test_previous_rating_auto_populated(self):
        rt = RatingTracker()
        rt.add_rating(RatingSnapshot(
            symbol="X", rating=CreditRating.A, as_of=date(2024, 1, 1),
        ))
        snap = rt.add_rating(RatingSnapshot(
            symbol="X", rating=CreditRating.BBB, as_of=date(2025, 1, 1),
        ))
        assert snap.previous_rating == CreditRating.A
        assert snap.migration_direction == "downgrade"

    def test_current_rating(self):
        rt = RatingTracker()
        rt.add_rating(RatingSnapshot(
            symbol="X", rating=CreditRating.A, as_of=date(2024, 1, 1),
        ))
        rt.add_rating(RatingSnapshot(
            symbol="X", rating=CreditRating.BBB, as_of=date(2025, 1, 1),
        ))
        current = rt.current_rating("X")
        assert current.rating == CreditRating.BBB

    def test_current_rating_none(self):
        rt = RatingTracker()
        assert rt.current_rating("UNKNOWN") is None

    def test_migration_matrix(self):
        rt = RatingTracker()
        # Simulate A → BBB → BB transitions
        rt.add_rating(RatingSnapshot(symbol="X", rating=CreditRating.A, as_of=date(2023, 1, 1)))
        rt.add_rating(RatingSnapshot(symbol="X", rating=CreditRating.BBB, as_of=date(2024, 1, 1)))
        rt.add_rating(RatingSnapshot(symbol="X", rating=CreditRating.BB, as_of=date(2025, 1, 1)))

        matrix = rt.migration_matrix()
        assert matrix[CreditRating.A][CreditRating.BBB] > 0
        assert matrix[CreditRating.BBB][CreditRating.BB] > 0

    def test_migration_matrix_default_stays(self):
        rt = RatingTracker()
        matrix = rt.migration_matrix()
        # No history → 100% stay in same rating
        assert matrix[CreditRating.AAA][CreditRating.AAA] == 1.0

    def test_rating_momentum_downgrade(self):
        rt = RatingTracker()
        rt.add_rating(RatingSnapshot(symbol="X", rating=CreditRating.A, as_of=date(2023, 1, 1)))
        rt.add_rating(RatingSnapshot(symbol="X", rating=CreditRating.BBB, as_of=date(2024, 1, 1)))
        rt.add_rating(RatingSnapshot(symbol="X", rating=CreditRating.BB, as_of=date(2025, 1, 1)))

        momentum = rt.rating_momentum("X")
        assert momentum > 0  # Positive = deteriorating (higher numeric rating)

    def test_rating_momentum_stable(self):
        rt = RatingTracker()
        rt.add_rating(RatingSnapshot(symbol="X", rating=CreditRating.A, as_of=date(2024, 1, 1)))
        momentum = rt.rating_momentum("X")
        assert momentum == 0.0

    def test_watchlist(self):
        rt = RatingTracker()
        rt.add_rating(RatingSnapshot(
            symbol="X", rating=CreditRating.BB,
            outlook=RatingOutlook.NEGATIVE, as_of=date(2025, 1, 1),
        ))
        rt.add_rating(RatingSnapshot(
            symbol="Y", rating=CreditRating.A,
            outlook=RatingOutlook.STABLE, as_of=date(2025, 1, 1),
        ))
        rt.add_rating(RatingSnapshot(
            symbol="Z", rating=CreditRating.B,
            outlook=RatingOutlook.WATCH, as_of=date(2025, 1, 1),
        ))

        watchlist = rt.watchlist()
        assert len(watchlist) == 2
        symbols = {w.symbol for w in watchlist}
        assert "X" in symbols
        assert "Z" in symbols

    def test_transitions_for(self):
        rt = RatingTracker()
        rt.add_rating(RatingSnapshot(symbol="X", rating=CreditRating.A, as_of=date(2023, 1, 1)))
        rt.add_rating(RatingSnapshot(symbol="X", rating=CreditRating.A, as_of=date(2024, 1, 1)))
        rt.add_rating(RatingSnapshot(symbol="X", rating=CreditRating.BBB, as_of=date(2025, 1, 1)))

        transitions = rt.transitions_for("X")
        assert len(transitions) == 1  # Only one actual change
        assert transitions[0].from_rating == CreditRating.A

    def test_reset(self):
        rt = RatingTracker()
        rt.add_rating(RatingSnapshot(symbol="X", rating=CreditRating.A))
        rt.reset()
        assert rt.current_rating("X") is None


# ── DebtAnalyzer Tests ──────────────────────────────────────────────


class TestDebtAnalyzer:
    """Test debt structure analyzer."""

    def _make_debt_items(self):
        return [
            DebtItem("Bond A", 500e6, date.today() + timedelta(days=365), 0.04, True),
            DebtItem("Bond B", 300e6, date.today() + timedelta(days=1825), 0.05, False),
            DebtItem("Bond C", 200e6, date.today() + timedelta(days=3650), 0.055, False),
        ]

    def test_basic_analysis(self):
        da = DebtAnalyzer()
        items = self._make_debt_items()
        result = da.analyze(
            "X", items, cash=100e6, ebitda=250e6,
            interest_expense=40e6, equity_value=2e9,
        )
        assert result.total_debt == 1e9
        assert result.net_debt == 900e6
        assert result.leverage_ratio == 4.0
        assert abs(result.interest_coverage - 6.25) < 0.01

    def test_maturity_profile(self):
        da = DebtAnalyzer()
        items = self._make_debt_items()
        profile = da.maturity_profile(items)
        assert len(profile) >= 2
        assert profile[0]["year"] <= profile[-1]["year"]
        total_pct = sum(p["pct"] for p in profile)
        assert abs(total_pct - 1.0) < 0.01

    def test_leverage_ratios(self):
        da = DebtAnalyzer()
        ratios = da.leverage_ratios(1000e6, 2000e6, 300e6)
        assert abs(ratios["debt_to_equity"] - 0.5) < 0.01
        assert abs(ratios["debt_to_ebitda"] - 3.33) < 0.01
        assert abs(ratios["debt_to_capital"] - 1000 / 3000) < 0.01

    def test_empty_debt(self):
        da = DebtAnalyzer()
        result = da.analyze("X", [])
        assert result.total_debt == 0.0

    def test_credit_health_healthy(self):
        da = DebtAnalyzer()
        items = [
            DebtItem("Bond", 200e6, date.today() + timedelta(days=3650), 0.04),
        ]
        result = da.analyze(
            "X", items, cash=50e6, ebitda=200e6,
            interest_expense=10e6,
        )
        assert result.credit_health > 0.5

    def test_credit_health_distressed(self):
        da = DebtAnalyzer()
        items = [
            DebtItem("Bond", 1e9, date.today() + timedelta(days=180), 0.08),
        ]
        result = da.analyze(
            "X", items, cash=10e6, ebitda=100e6,
            interest_expense=80e6,
        )
        assert result.credit_health < 0.5
        assert result.refinancing_risk > 0.3

    def test_near_term_pct(self):
        da = DebtAnalyzer()
        items = [
            DebtItem("Short", 500e6, date.today() + timedelta(days=365), 0.04),
            DebtItem("Long", 500e6, date.today() + timedelta(days=3650), 0.05),
        ]
        result = da.analyze("X", items, ebitda=250e6)
        assert abs(result.near_term_pct - 0.5) < 0.01


# ── Integration Tests ───────────────────────────────────────────────


class TestIntegration:
    """Integration tests."""

    def test_full_credit_workflow(self):
        """End-to-end: spreads, default, ratings, structure."""
        # 1. Spread analysis
        sa = SpreadAnalyzer()
        for bps in [150, 160, 155, 170, 180]:
            sa.add_spread(CreditSpread(symbol="XYZ", spread_bps=bps))
        spread_sum = sa.analyze("XYZ")
        assert spread_sum.is_widening

        # 2. Default probability
        de = DefaultEstimator()
        dp = de.merton_model("XYZ", 1e9, 500e6, 0.35)
        assert dp.pd_1y >= 0

        # 3. Rating
        rt = RatingTracker()
        rt.add_rating(RatingSnapshot(
            symbol="XYZ", rating=CreditRating.BBB,
            outlook=RatingOutlook.NEGATIVE, as_of=date(2025, 1, 1),
        ))
        assert rt.watchlist()[0].symbol == "XYZ"

        # 4. Structure
        da = DebtAnalyzer()
        items = [
            DebtItem("Bond", 500e6, date.today() + timedelta(days=1825), 0.05),
        ]
        ds = da.analyze("XYZ", items, ebitda=150e6, interest_expense=25e6)
        assert ds.credit_health > 0

    def test_module_imports(self):
        """Verify all exports are accessible."""
        from src.credit import (
            CreditRating, RatingOutlook, SpreadType, DefaultModel,
            RATING_ORDER, INVESTMENT_GRADE,
            SpreadConfig, DefaultConfig, RatingConfig, StructureConfig,
            CreditConfig, DEFAULT_CREDIT_CONFIG,
            CreditSpread, SpreadSummary, DefaultProbability,
            RatingSnapshot, RatingTransition, DebtItem, DebtStructure,
            SpreadAnalyzer, DefaultEstimator, RatingTracker, DebtAnalyzer,
        )
