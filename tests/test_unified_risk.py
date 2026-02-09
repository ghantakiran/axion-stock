"""Tests for Unified Risk Context & Correlation Guard (PRD-163).

10 test classes, ~60 tests covering correlation config/matrix/guard,
VaR config/sizer, regime limits/adapter, risk context config/context,
and module imports.
"""

from __future__ import annotations

import math
import unittest
from datetime import datetime, timezone

from src.unified_risk.correlation import (
    CorrelationConfig,
    CorrelationGuard,
    CorrelationMatrix,
)
from src.unified_risk.var_sizer import VaRConfig, VaRPositionSizer, VaRResult
from src.unified_risk.regime_limits import (
    REGIME_PROFILES,
    RegimeLimits,
    RegimeRiskAdapter,
)
from src.unified_risk.context import (
    RiskContext,
    RiskContextConfig,
    UnifiedRiskAssessment,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _deterministic_returns(n: int = 30, seed_offset: int = 0) -> list[float]:
    """Generate deterministic return series for testing."""
    return [0.01 * ((i + seed_offset) % 7 - 3) for i in range(n)]


def _correlated_returns(base: list[float], noise: float = 0.001) -> list[float]:
    """Create a return series highly correlated with *base*."""
    return [r + noise * (i % 3 - 1) for i, r in enumerate(base)]


def _uncorrelated_returns(n: int = 30) -> list[float]:
    """Create a return series with low correlation to typical base."""
    return [0.01 * ((i * 3 + 5) % 11 - 5) for i in range(n)]


def _make_positions(symbols: list[str], value: float = 5000.0) -> list[dict]:
    """Create a list of mock position dicts."""
    return [{"symbol": s, "market_value": value} for s in symbols]


# ═══════════════════════════════════════════════════════════════════════
#  1. CorrelationConfig
# ═══════════════════════════════════════════════════════════════════════


class TestCorrelationConfig(unittest.TestCase):
    """Tests for CorrelationConfig defaults and customisation."""

    def test_default_values(self):
        cfg = CorrelationConfig()
        self.assertAlmostEqual(cfg.max_pairwise_correlation, 0.80)
        self.assertEqual(cfg.max_cluster_size, 4)
        self.assertEqual(cfg.lookback_days, 60)
        self.assertEqual(cfg.min_data_points, 20)
        self.assertAlmostEqual(cfg.cluster_threshold, 0.70)

    def test_custom_values(self):
        cfg = CorrelationConfig(
            max_pairwise_correlation=0.90,
            max_cluster_size=6,
            min_data_points=10,
        )
        self.assertAlmostEqual(cfg.max_pairwise_correlation, 0.90)
        self.assertEqual(cfg.max_cluster_size, 6)
        self.assertEqual(cfg.min_data_points, 10)

    def test_is_dataclass(self):
        cfg = CorrelationConfig()
        self.assertTrue(hasattr(cfg, "__dataclass_fields__"))


# ═══════════════════════════════════════════════════════════════════════
#  2. CorrelationMatrix
# ═══════════════════════════════════════════════════════════════════════


class TestCorrelationMatrix(unittest.TestCase):
    """Tests for the CorrelationMatrix dataclass."""

    def test_default_empty(self):
        m = CorrelationMatrix()
        self.assertEqual(m.tickers, [])
        self.assertEqual(m.matrix, [])
        self.assertEqual(m.clusters, [])
        self.assertAlmostEqual(m.max_correlation, 0.0)

    def test_get_correlation_present(self):
        m = CorrelationMatrix(
            tickers=["AAPL", "MSFT"],
            matrix=[[1.0, 0.85], [0.85, 1.0]],
        )
        self.assertAlmostEqual(m.get_correlation("AAPL", "MSFT"), 0.85)
        self.assertAlmostEqual(m.get_correlation("MSFT", "AAPL"), 0.85)
        self.assertAlmostEqual(m.get_correlation("AAPL", "AAPL"), 1.0)

    def test_get_correlation_missing_ticker(self):
        m = CorrelationMatrix(tickers=["AAPL"], matrix=[[1.0]])
        self.assertIsNone(m.get_correlation("AAPL", "TSLA"))
        self.assertIsNone(m.get_correlation("TSLA", "AAPL"))

    def test_to_dict_keys(self):
        m = CorrelationMatrix(
            tickers=["A", "B"], matrix=[[1.0, 0.5], [0.5, 1.0]],
            clusters=[["A", "B"]], max_correlation=0.5,
        )
        d = m.to_dict()
        expected_keys = {"tickers", "matrix", "clusters", "max_correlation", "computed_at"}
        self.assertEqual(set(d.keys()), expected_keys)
        self.assertAlmostEqual(d["max_correlation"], 0.5)

    def test_computed_at_is_utc(self):
        m = CorrelationMatrix()
        self.assertIsNotNone(m.computed_at.tzinfo)


# ═══════════════════════════════════════════════════════════════════════
#  3. CorrelationGuard
# ═══════════════════════════════════════════════════════════════════════


class TestCorrelationGuard(unittest.TestCase):
    """Tests for the CorrelationGuard engine."""

    def setUp(self):
        self.guard = CorrelationGuard()
        self.base = _deterministic_returns(30)

    def test_compute_matrix_empty(self):
        m = self.guard.compute_matrix({})
        self.assertEqual(m.tickers, [])

    def test_compute_matrix_single_ticker(self):
        m = self.guard.compute_matrix({"AAPL": self.base})
        self.assertEqual(m.tickers, ["AAPL"])
        self.assertAlmostEqual(m.matrix[0][0], 1.0)

    def test_compute_matrix_correlated_pair(self):
        correlated = _correlated_returns(self.base, noise=0.0001)
        m = self.guard.compute_matrix({"AAPL": self.base, "MSFT": correlated})
        corr = m.get_correlation("AAPL", "MSFT")
        self.assertIsNotNone(corr)
        self.assertGreater(abs(corr), 0.90)

    def test_compute_matrix_uncorrelated_pair(self):
        uncorr = _uncorrelated_returns(30)
        m = self.guard.compute_matrix({"AAPL": self.base, "XYZ": uncorr})
        corr = m.get_correlation("AAPL", "XYZ")
        self.assertIsNotNone(corr)
        self.assertLess(abs(corr), 0.80)

    def test_pearson_insufficient_data(self):
        guard = CorrelationGuard(CorrelationConfig(min_data_points=20))
        result = guard._pearson([0.01] * 5, [0.02] * 5)
        self.assertAlmostEqual(result, 0.0)

    def test_pearson_identical_series(self):
        series = _deterministic_returns(30)
        result = self.guard._pearson(series, list(series))
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_check_new_trade_empty_holdings(self):
        m = self.guard.compute_matrix({"AAPL": self.base})
        approved, reason = self.guard.check_new_trade("AAPL", m, [])
        self.assertTrue(approved)
        self.assertEqual(reason, "approved")

    def test_check_new_trade_ticker_not_in_matrix(self):
        m = self.guard.compute_matrix({"AAPL": self.base})
        approved, reason = self.guard.check_new_trade("UNKNOWN", m, ["AAPL"])
        self.assertTrue(approved)

    def test_check_new_trade_blocked_high_correlation(self):
        corr_ret = _correlated_returns(self.base, noise=0.0001)
        guard = CorrelationGuard(CorrelationConfig(max_pairwise_correlation=0.50))
        m = guard.compute_matrix({"AAPL": self.base, "MSFT": corr_ret})
        approved, reason = guard.check_new_trade("MSFT", m, ["AAPL"])
        self.assertFalse(approved)
        self.assertIn("exceeds", reason)

    def test_check_new_trade_approved_low_correlation(self):
        uncorr = _uncorrelated_returns(30)
        m = self.guard.compute_matrix({"AAPL": self.base, "XYZ": uncorr})
        approved, _ = self.guard.check_new_trade("XYZ", m, ["AAPL"])
        self.assertTrue(approved)

    def test_concentration_score_single_holding(self):
        m = self.guard.compute_matrix({"AAPL": self.base})
        score = self.guard.get_portfolio_concentration_score(m, ["AAPL"])
        self.assertAlmostEqual(score, 0.0)

    def test_concentration_score_correlated_pair(self):
        corr_ret = _correlated_returns(self.base, noise=0.0001)
        m = self.guard.compute_matrix({"AAPL": self.base, "MSFT": corr_ret})
        score = self.guard.get_portfolio_concentration_score(m, ["AAPL", "MSFT"])
        self.assertGreater(score, 50.0)

    def test_concentration_score_no_overlap_in_matrix(self):
        m = CorrelationMatrix(tickers=["A"], matrix=[[1.0]])
        score = self.guard.get_portfolio_concentration_score(m, ["X", "Y"])
        self.assertAlmostEqual(score, 0.0)


# ═══════════════════════════════════════════════════════════════════════
#  4. VaRConfig
# ═══════════════════════════════════════════════════════════════════════


class TestVaRConfig(unittest.TestCase):
    """Tests for VaRConfig dataclass."""

    def test_defaults(self):
        cfg = VaRConfig()
        self.assertAlmostEqual(cfg.confidence_level, 0.95)
        self.assertAlmostEqual(cfg.max_portfolio_var_pct, 2.0)
        self.assertAlmostEqual(cfg.max_position_var_pct, 0.5)
        self.assertEqual(cfg.lookback_days, 252)
        self.assertTrue(cfg.use_cvar)
        self.assertAlmostEqual(cfg.decay_factor, 0.97)

    def test_custom_values(self):
        cfg = VaRConfig(confidence_level=0.99, use_cvar=False)
        self.assertAlmostEqual(cfg.confidence_level, 0.99)
        self.assertFalse(cfg.use_cvar)


# ═══════════════════════════════════════════════════════════════════════
#  5. VaRPositionSizer
# ═══════════════════════════════════════════════════════════════════════


class TestVaRPositionSizer(unittest.TestCase):
    """Tests for VaR-based position sizing."""

    def setUp(self):
        self.sizer = VaRPositionSizer(equity=100_000.0)
        self.returns = _deterministic_returns(50)

    def test_compute_var_insufficient_data(self):
        result = self.sizer.compute_var([0.01, -0.01])
        self.assertEqual(result.data_points, 2)
        self.assertAlmostEqual(result.var_pct, 0.0)

    def test_compute_var_enough_data(self):
        result = self.sizer.compute_var(self.returns)
        self.assertEqual(result.data_points, 50)
        self.assertGreater(result.var_pct, 0.0)
        self.assertGreater(result.cvar_pct, 0.0)

    def test_compute_var_confidence_level(self):
        result = self.sizer.compute_var(self.returns)
        self.assertAlmostEqual(result.confidence_level, 0.95)

    def test_var_result_to_dict(self):
        result = self.sizer.compute_var(self.returns)
        d = result.to_dict()
        expected_keys = {
            "var_pct", "cvar_pct", "max_position_size",
            "risk_budget_remaining", "confidence_level", "data_points",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_size_position_positive(self):
        size = self.sizer.size_position(self.returns, current_price=150.0)
        self.assertGreater(size, 0.0)

    def test_size_position_zero_price(self):
        size = self.sizer.size_position(self.returns, current_price=0.0)
        self.assertAlmostEqual(size, 0.0)

    def test_size_position_budget_exhausted(self):
        size = self.sizer.size_position(
            self.returns, current_price=150.0, existing_var_pct=10.0,
        )
        self.assertAlmostEqual(size, 0.0)

    def test_equity_setter_clamps_negative(self):
        self.sizer.equity = -500
        self.assertAlmostEqual(self.sizer.equity, 0.0)

    def test_compute_portfolio_var_empty(self):
        result = self.sizer.compute_portfolio_var({}, {})
        self.assertAlmostEqual(result.var_pct, 0.0)

    def test_compute_portfolio_var_normal(self):
        rets = {"AAPL": self.returns, "MSFT": _deterministic_returns(50, seed_offset=3)}
        weights = {"AAPL": 0.5, "MSFT": 0.5}
        result = self.sizer.compute_portfolio_var(rets, weights)
        self.assertGreater(result.data_points, 0)

    def test_compute_portfolio_var_insufficient_length(self):
        rets = {"AAPL": [0.01, 0.02], "MSFT": [0.01, -0.01]}
        weights = {"AAPL": 0.5, "MSFT": 0.5}
        result = self.sizer.compute_portfolio_var(rets, weights)
        self.assertEqual(result.data_points, 2)


# ═══════════════════════════════════════════════════════════════════════
#  6. RegimeLimits
# ═══════════════════════════════════════════════════════════════════════


class TestRegimeLimits(unittest.TestCase):
    """Tests for RegimeLimits dataclass and REGIME_PROFILES."""

    def test_default_regime(self):
        r = RegimeLimits()
        self.assertEqual(r.regime, "sideways")
        self.assertAlmostEqual(r.position_size_mult, 1.0)

    def test_four_profiles_exist(self):
        expected = {"bull", "bear", "sideways", "crisis"}
        self.assertEqual(set(REGIME_PROFILES.keys()), expected)

    def test_bull_profile_values(self):
        bull = REGIME_PROFILES["bull"]
        self.assertAlmostEqual(bull.position_size_mult, 1.2)
        self.assertAlmostEqual(bull.max_positions_mult, 1.2)

    def test_crisis_profile_values(self):
        crisis = REGIME_PROFILES["crisis"]
        self.assertAlmostEqual(crisis.position_size_mult, 0.2)
        self.assertAlmostEqual(crisis.max_positions_mult, 0.3)

    def test_bear_smaller_than_bull(self):
        bull = REGIME_PROFILES["bull"]
        bear = REGIME_PROFILES["bear"]
        self.assertLess(bear.position_size_mult, bull.position_size_mult)

    def test_to_dict_keys(self):
        r = REGIME_PROFILES["bull"]
        d = r.to_dict()
        expected_keys = {
            "regime", "position_size_mult", "max_positions_mult",
            "sector_concentration_mult", "correlation_threshold_mult",
            "stop_loss_mult", "description",
        }
        self.assertEqual(set(d.keys()), expected_keys)


# ═══════════════════════════════════════════════════════════════════════
#  7. RegimeRiskAdapter
# ═══════════════════════════════════════════════════════════════════════


class TestRegimeRiskAdapter(unittest.TestCase):
    """Tests for the RegimeRiskAdapter."""

    def setUp(self):
        self.adapter = RegimeRiskAdapter()

    def test_default_regime_is_sideways(self):
        self.assertEqual(self.adapter.current_regime, "sideways")

    def test_set_regime(self):
        self.adapter.set_regime("bull")
        self.assertEqual(self.adapter.current_regime, "bull")

    def test_get_limits_known_regime(self):
        limits = self.adapter.get_limits("crisis")
        self.assertEqual(limits.regime, "crisis")
        self.assertAlmostEqual(limits.position_size_mult, 0.2)

    def test_get_limits_unknown_falls_to_default(self):
        limits = self.adapter.get_limits("unknown_regime")
        self.assertEqual(limits.regime, "sideways")

    def test_get_limits_none_uses_current(self):
        self.adapter.set_regime("bear")
        limits = self.adapter.get_limits()
        self.assertEqual(limits.regime, "bear")

    def test_adjust_position_size_bull(self):
        result = self.adapter.adjust_position_size(10_000, "bull")
        self.assertAlmostEqual(result, 12_000.0)

    def test_adjust_position_size_crisis(self):
        result = self.adapter.adjust_position_size(10_000, "crisis")
        self.assertAlmostEqual(result, 2_000.0)

    def test_adjust_max_positions_minimum_one(self):
        result = self.adapter.adjust_max_positions(1, "crisis")
        self.assertGreaterEqual(result, 1)

    def test_adjust_stop_distance(self):
        result = self.adapter.adjust_stop_distance(2.0, "bear")
        self.assertAlmostEqual(result, 2.0 * 0.8)

    def test_get_all_profiles(self):
        profiles = self.adapter.get_all_profiles()
        self.assertIn("bull", profiles)
        self.assertIn("crisis", profiles)
        self.assertIsInstance(profiles["bull"], dict)


# ═══════════════════════════════════════════════════════════════════════
#  8. RiskContextConfig
# ═══════════════════════════════════════════════════════════════════════


class TestRiskContextConfig(unittest.TestCase):
    """Tests for RiskContextConfig dataclass."""

    def test_defaults(self):
        cfg = RiskContextConfig()
        self.assertAlmostEqual(cfg.max_daily_loss_pct, 10.0)
        self.assertEqual(cfg.max_concurrent_positions, 10)
        self.assertAlmostEqual(cfg.max_single_stock_pct, 15.0)
        self.assertAlmostEqual(cfg.max_sector_pct, 30.0)
        self.assertEqual(cfg.default_regime, "sideways")
        self.assertTrue(cfg.enable_correlation_guard)
        self.assertTrue(cfg.enable_var_sizing)

    def test_nested_configs(self):
        cfg = RiskContextConfig()
        self.assertIsInstance(cfg.correlation_config, CorrelationConfig)
        self.assertIsInstance(cfg.var_config, VaRConfig)

    def test_custom_values(self):
        cfg = RiskContextConfig(
            max_daily_loss_pct=5.0,
            max_concurrent_positions=5,
            enable_correlation_guard=False,
        )
        self.assertAlmostEqual(cfg.max_daily_loss_pct, 5.0)
        self.assertEqual(cfg.max_concurrent_positions, 5)
        self.assertFalse(cfg.enable_correlation_guard)


# ═══════════════════════════════════════════════════════════════════════
#  9. RiskContext
# ═══════════════════════════════════════════════════════════════════════


class TestRiskContext(unittest.TestCase):
    """Tests for the unified RiskContext assess() engine."""

    def setUp(self):
        self.ctx = RiskContext(equity=100_000.0)
        self.returns = {
            "AAPL": _deterministic_returns(30),
            "MSFT": _deterministic_returns(30, seed_offset=2),
        }

    def test_assess_basic_approved(self):
        result = self.ctx.assess(
            ticker="AAPL",
            direction="long",
            positions=[],
            returns_by_ticker=self.returns,
            regime="bull",
        )
        self.assertTrue(result.approved)
        self.assertIsNone(result.rejection_reason)
        self.assertEqual(result.regime, "bull")

    def test_assess_kill_switch_rejects(self):
        result = self.ctx.assess(
            ticker="AAPL",
            direction="long",
            positions=[],
            kill_switch_active=True,
        )
        self.assertFalse(result.approved)
        self.assertIn("Kill switch", result.rejection_reason)
        self.assertIn("kill_switch", result.checks_run)

    def test_assess_circuit_breaker_open_rejects(self):
        result = self.ctx.assess(
            ticker="AAPL",
            direction="long",
            positions=[],
            circuit_breaker_status="open",
        )
        self.assertFalse(result.approved)
        self.assertIn("Circuit breaker", result.rejection_reason)

    def test_assess_daily_loss_limit(self):
        self.ctx.record_pnl(-11_000.0)
        result = self.ctx.assess(
            ticker="AAPL",
            direction="long",
            positions=[],
        )
        self.assertFalse(result.approved)
        self.assertIn("Daily loss", result.rejection_reason)

    def test_assess_max_positions_exceeded(self):
        cfg = RiskContextConfig(max_concurrent_positions=2)
        ctx = RiskContext(config=cfg, equity=100_000.0)
        positions = _make_positions(["AAPL", "MSFT", "GOOGL"])
        result = ctx.assess(
            ticker="TSLA",
            direction="long",
            positions=positions,
        )
        self.assertFalse(result.approved)
        self.assertIn("Max positions", result.rejection_reason)

    def test_assess_single_stock_concentration(self):
        cfg = RiskContextConfig(max_single_stock_pct=5.0)
        ctx = RiskContext(config=cfg, equity=100_000.0)
        positions = [{"symbol": "AAPL", "market_value": 6_000.0}]
        result = ctx.assess(
            ticker="AAPL",
            direction="long",
            positions=positions,
        )
        self.assertFalse(result.approved)
        self.assertIn("exposure", result.rejection_reason)

    def test_assess_includes_all_checks_when_approved(self):
        result = self.ctx.assess(
            ticker="AAPL",
            direction="long",
            positions=[],
            returns_by_ticker=self.returns,
        )
        self.assertTrue(result.approved)
        self.assertIn("kill_switch", result.checks_run)
        self.assertIn("circuit_breaker", result.checks_run)
        self.assertIn("daily_loss_limit", result.checks_run)
        self.assertIn("max_positions", result.checks_run)

    def test_assess_circuit_breaker_half_open_reduces_size(self):
        result_normal = self.ctx.assess(
            ticker="AAPL",
            direction="long",
            positions=[],
            returns_by_ticker=self.returns,
        )
        result_half = self.ctx.assess(
            ticker="AAPL",
            direction="long",
            positions=[],
            returns_by_ticker=self.returns,
            circuit_breaker_status="half_open",
        )
        self.assertTrue(result_half.approved)
        self.assertLessEqual(result_half.max_position_size, result_normal.max_position_size)

    def test_record_pnl_and_reset(self):
        self.ctx.record_pnl(-500.0)
        self.ctx.record_pnl(-300.0)
        result = self.ctx.assess(
            ticker="AAPL", direction="long", positions=[],
        )
        self.assertAlmostEqual(result.daily_pnl, -800.0)

        self.ctx.reset_daily()
        result2 = self.ctx.assess(
            ticker="AAPL", direction="long", positions=[],
        )
        self.assertAlmostEqual(result2.daily_pnl, 0.0)

    def test_assess_to_dict(self):
        result = self.ctx.assess(
            ticker="AAPL", direction="long", positions=[],
        )
        d = result.to_dict()
        self.assertIn("approved", d)
        self.assertIn("regime", d)
        self.assertIn("timestamp", d)
        self.assertIn("checks_run", d)

    def test_equity_property(self):
        self.assertAlmostEqual(self.ctx.equity, 100_000.0)
        self.ctx.equity = 50_000.0
        self.assertAlmostEqual(self.ctx.equity, 50_000.0)

    def test_equity_clamps_to_zero(self):
        self.ctx.equity = -1000.0
        self.assertAlmostEqual(self.ctx.equity, 0.0)

    def test_assess_no_returns_skips_correlation(self):
        result = self.ctx.assess(
            ticker="AAPL", direction="long", positions=[],
            returns_by_ticker=None,
        )
        self.assertTrue(result.approved)
        self.assertNotIn("correlation_guard", result.checks_run)

    def test_assess_disabled_correlation_guard(self):
        cfg = RiskContextConfig(enable_correlation_guard=False)
        ctx = RiskContext(config=cfg, equity=100_000.0)
        result = ctx.assess(
            ticker="AAPL", direction="long", positions=[],
            returns_by_ticker=self.returns,
        )
        self.assertTrue(result.approved)
        self.assertNotIn("correlation_guard", result.checks_run)


# ═══════════════════════════════════════════════════════════════════════
#  10. Module Imports
# ═══════════════════════════════════════════════════════════════════════


class TestModuleImports(unittest.TestCase):
    """Verify public API is importable from the package."""

    def test_import_from_package(self):
        from src.unified_risk import (
            CorrelationConfig,
            CorrelationGuard,
            CorrelationMatrix,
            RegimeLimits,
            RegimeRiskAdapter,
            RiskContext,
            RiskContextConfig,
            UnifiedRiskAssessment,
            VaRConfig,
            VaRPositionSizer,
            VaRResult,
        )
        self.assertIsNotNone(RiskContext)
        self.assertIsNotNone(CorrelationGuard)

    def test_regime_profiles_importable(self):
        from src.unified_risk.regime_limits import REGIME_PROFILES
        self.assertIsInstance(REGIME_PROFILES, dict)
        self.assertEqual(len(REGIME_PROFILES), 4)
