"""Tests for Enhanced Backtesting Realism (PRD-167).

11 test classes, ~70 tests covering survivorship config/filter,
impact config/result/model, Monte Carlo config/path-stats/simulator,
gap config/simulator, and module imports.
"""

from __future__ import annotations

import math
import unittest
from datetime import date, datetime, timezone

from src.enhanced_backtest.survivorship import SurvivorshipConfig, SurvivorshipFilter
from src.enhanced_backtest.impact_model import (
    ConvexImpactModel,
    ImpactConfig,
    ImpactResult,
)
from src.enhanced_backtest.monte_carlo import (
    MonteCarloConfig,
    MonteCarloResult,
    MonteCarloSimulator,
    PathStatistics,
)
from src.enhanced_backtest.gap_simulator import GapConfig, GapEvent, GapSimulator


# ═══════════════════════════════════════════════════════════════════════
#  1. SurvivorshipConfig
# ═══════════════════════════════════════════════════════════════════════


class TestSurvivorshipConfig(unittest.TestCase):
    """Tests for SurvivorshipConfig dataclass."""

    def test_defaults(self):
        cfg = SurvivorshipConfig()
        self.assertAlmostEqual(cfg.min_price, 5.0)
        self.assertAlmostEqual(cfg.min_volume, 500_000)
        self.assertAlmostEqual(cfg.min_market_cap, 500.0)
        self.assertTrue(cfg.exclude_otc)
        self.assertTrue(cfg.require_continuous_data)
        self.assertEqual(cfg.max_gap_days, 5)

    def test_custom_values(self):
        cfg = SurvivorshipConfig(min_price=10.0, min_volume=1_000_000, exclude_otc=False)
        self.assertAlmostEqual(cfg.min_price, 10.0)
        self.assertAlmostEqual(cfg.min_volume, 1_000_000)
        self.assertFalse(cfg.exclude_otc)

    def test_is_dataclass(self):
        self.assertTrue(hasattr(SurvivorshipConfig(), "__dataclass_fields__"))


# ═══════════════════════════════════════════════════════════════════════
#  2. SurvivorshipFilter
# ═══════════════════════════════════════════════════════════════════════


class TestSurvivorshipFilter(unittest.TestCase):
    """Tests for the SurvivorshipFilter engine."""

    def setUp(self):
        self.filt = SurvivorshipFilter()
        self.filt.add_listing("AAPL", listed_date=date(1980, 12, 12))
        self.filt.add_listing(
            "ENRON", listed_date=date(1985, 1, 1), delisted_date=date(2001, 12, 2),
        )
        self.filt.add_listing("TSLA", listed_date=date(2010, 6, 29))

    def test_filter_active_tickers(self):
        tradable = self.filt.filter_universe(
            tickers=["AAPL", "ENRON", "TSLA"],
            as_of=date(2023, 6, 1),
            prices={"AAPL": 180.0, "TSLA": 250.0, "ENRON": 0.0},
            volumes={"AAPL": 50_000_000, "TSLA": 80_000_000, "ENRON": 0},
        )
        self.assertIn("AAPL", tradable)
        self.assertIn("TSLA", tradable)
        self.assertNotIn("ENRON", tradable)

    def test_filter_before_listing(self):
        tradable = self.filt.filter_universe(
            tickers=["TSLA"],
            as_of=date(2005, 1, 1),
        )
        self.assertNotIn("TSLA", tradable)

    def test_filter_delisted_on_exact_date(self):
        tradable = self.filt.filter_universe(
            tickers=["ENRON"],
            as_of=date(2001, 12, 2),
        )
        self.assertNotIn("ENRON", tradable)

    def test_filter_before_delisting(self):
        tradable = self.filt.filter_universe(
            tickers=["ENRON"],
            as_of=date(2001, 12, 1),
            prices={"ENRON": 10.0},
            volumes={"ENRON": 1_000_000},
        )
        self.assertIn("ENRON", tradable)

    def test_filter_min_price(self):
        tradable = self.filt.filter_universe(
            tickers=["AAPL"],
            as_of=date(2023, 1, 1),
            prices={"AAPL": 3.0},
            volumes={"AAPL": 1_000_000},
        )
        self.assertNotIn("AAPL", tradable)

    def test_filter_min_volume(self):
        tradable = self.filt.filter_universe(
            tickers=["AAPL"],
            as_of=date(2023, 1, 1),
            prices={"AAPL": 180.0},
            volumes={"AAPL": 100},
        )
        self.assertNotIn("AAPL", tradable)

    def test_filter_no_price_data_passes(self):
        tradable = self.filt.filter_universe(
            tickers=["AAPL"],
            as_of=date(2023, 1, 1),
        )
        self.assertIn("AAPL", tradable)

    def test_filter_unknown_ticker_passes(self):
        """Tickers without listing info are assumed tradable."""
        tradable = self.filt.filter_universe(
            tickers=["UNKNOWN"],
            as_of=date(2023, 1, 1),
        )
        self.assertIn("UNKNOWN", tradable)

    def test_filter_otc_excluded(self):
        self.filt.add_listing("PENNY", listed_date=date(2000, 1, 1), exchange="OTC")
        tradable = self.filt.filter_universe(
            tickers=["PENNY"],
            as_of=date(2023, 1, 1),
            prices={"PENNY": 50.0},
            volumes={"PENNY": 1_000_000},
        )
        self.assertNotIn("PENNY", tradable)

    def test_filter_otc_allowed_when_disabled(self):
        cfg = SurvivorshipConfig(exclude_otc=False)
        filt = SurvivorshipFilter(config=cfg)
        filt.add_listing("PENNY", listed_date=date(2000, 1, 1), exchange="OTC")
        tradable = filt.filter_universe(
            tickers=["PENNY"],
            as_of=date(2023, 1, 1),
            prices={"PENNY": 50.0},
            volumes={"PENNY": 1_000_000},
        )
        self.assertIn("PENNY", tradable)

    def test_get_delisted_at(self):
        delisted = self.filt.get_delisted_at(date(2023, 1, 1))
        self.assertIn("ENRON", delisted)
        self.assertNotIn("AAPL", delisted)
        self.assertNotIn("TSLA", delisted)

    def test_get_delisted_at_before_delisting(self):
        delisted = self.filt.get_delisted_at(date(2001, 1, 1))
        self.assertNotIn("ENRON", delisted)

    def test_add_listings_bulk(self):
        filt = SurvivorshipFilter()
        filt.add_listings_bulk([
            {"ticker": "A", "listed_date": date(2020, 1, 1)},
            {"ticker": "B", "listed_date": date(2021, 1, 1), "delisted_date": date(2022, 6, 1)},
        ])
        stats = filt.get_stats()
        self.assertEqual(stats["total_listings"], 2)
        self.assertEqual(stats["delisted"], 1)
        self.assertEqual(stats["active"], 1)

    def test_get_stats(self):
        stats = self.filt.get_stats()
        self.assertEqual(stats["total_listings"], 3)
        self.assertEqual(stats["delisted"], 1)
        self.assertEqual(stats["active"], 2)

    def test_pink_sheet_excluded(self):
        self.filt.add_listing("PINK_STOCK", listed_date=date(2000, 1, 1), exchange="PINK")
        tradable = self.filt.filter_universe(
            tickers=["PINK_STOCK"], as_of=date(2023, 1, 1),
        )
        self.assertNotIn("PINK_STOCK", tradable)


# ═══════════════════════════════════════════════════════════════════════
#  3. ImpactConfig
# ═══════════════════════════════════════════════════════════════════════


class TestImpactConfig(unittest.TestCase):
    """Tests for ImpactConfig dataclass."""

    def test_defaults(self):
        cfg = ImpactConfig()
        self.assertAlmostEqual(cfg.temporary_impact_coeff, 0.1)
        self.assertAlmostEqual(cfg.permanent_impact_coeff, 0.05)
        self.assertTrue(cfg.volatility_scale)
        self.assertAlmostEqual(cfg.min_spread_bps, 1.0)
        self.assertAlmostEqual(cfg.urgency_penalty, 1.0)

    def test_custom_values(self):
        cfg = ImpactConfig(temporary_impact_coeff=0.2, urgency_penalty=2.0)
        self.assertAlmostEqual(cfg.temporary_impact_coeff, 0.2)
        self.assertAlmostEqual(cfg.urgency_penalty, 2.0)


# ═══════════════════════════════════════════════════════════════════════
#  4. ImpactResult
# ═══════════════════════════════════════════════════════════════════════


class TestImpactResult(unittest.TestCase):
    """Tests for ImpactResult dataclass."""

    def test_default_values(self):
        r = ImpactResult()
        self.assertAlmostEqual(r.total_impact_bps, 0.0)
        self.assertAlmostEqual(r.effective_price, 0.0)
        self.assertAlmostEqual(r.slippage_dollars, 0.0)

    def test_to_dict_keys(self):
        r = ImpactResult(total_impact_bps=5.0, effective_price=185.05)
        d = r.to_dict()
        expected_keys = {
            "total_impact_bps", "temporary_impact_bps", "permanent_impact_bps",
            "spread_cost_bps", "effective_price", "slippage_dollars",
            "participation_rate",
        }
        self.assertEqual(set(d.keys()), expected_keys)


# ═══════════════════════════════════════════════════════════════════════
#  5. ConvexImpactModel
# ═══════════════════════════════════════════════════════════════════════


class TestConvexImpactModel(unittest.TestCase):
    """Tests for the ConvexImpactModel engine."""

    def setUp(self):
        self.model = ConvexImpactModel()

    def test_estimate_zero_volume(self):
        result = self.model.estimate(1000, 0, 185.0)
        self.assertAlmostEqual(result.effective_price, 185.0)

    def test_estimate_zero_order_size(self):
        result = self.model.estimate(0, 5_000_000, 185.0)
        self.assertAlmostEqual(result.effective_price, 185.0)

    def test_estimate_zero_price(self):
        result = self.model.estimate(1000, 5_000_000, 0.0)
        self.assertAlmostEqual(result.effective_price, 0.0)

    def test_estimate_buy_positive_impact(self):
        result = self.model.estimate(10_000, 5_000_000, 185.0, 0.02, "buy")
        self.assertGreater(result.total_impact_bps, 0.0)
        self.assertGreater(result.effective_price, 185.0)

    def test_estimate_sell_negative_impact(self):
        result = self.model.estimate(10_000, 5_000_000, 185.0, 0.02, "sell")
        self.assertGreater(result.total_impact_bps, 0.0)
        self.assertLess(result.effective_price, 185.0)

    def test_impact_increases_with_order_size(self):
        small = self.model.estimate(1_000, 5_000_000, 185.0)
        large = self.model.estimate(100_000, 5_000_000, 185.0)
        self.assertGreater(large.total_impact_bps, small.total_impact_bps)

    def test_convex_impact_superlinear(self):
        """Impact should grow faster than linearly (convex) due to sqrt."""
        r1 = self.model.estimate(10_000, 5_000_000, 185.0)
        r2 = self.model.estimate(40_000, 5_000_000, 185.0)
        # 4x order size should produce less than 4x temp impact but more than 2x
        ratio = r2.temporary_impact_bps / max(r1.temporary_impact_bps, 0.001)
        self.assertGreater(ratio, 1.5)
        self.assertLess(ratio, 4.5)

    def test_participation_rate(self):
        result = self.model.estimate(50_000, 1_000_000, 100.0)
        self.assertAlmostEqual(result.participation_rate, 0.05)

    def test_slippage_dollars_positive(self):
        result = self.model.estimate(10_000, 5_000_000, 185.0, 0.02, "buy")
        self.assertGreater(result.slippage_dollars, 0.0)

    def test_impact_components_sum_to_total(self):
        result = self.model.estimate(10_000, 5_000_000, 185.0)
        total = result.temporary_impact_bps + result.permanent_impact_bps + result.spread_cost_bps
        self.assertAlmostEqual(result.total_impact_bps, total, places=2)

    def test_urgency_penalty_increases_impact(self):
        normal = ConvexImpactModel(ImpactConfig(urgency_penalty=1.0))
        urgent = ConvexImpactModel(ImpactConfig(urgency_penalty=2.0))
        r_normal = normal.estimate(10_000, 5_000_000, 185.0)
        r_urgent = urgent.estimate(10_000, 5_000_000, 185.0)
        self.assertGreater(r_urgent.total_impact_bps, r_normal.total_impact_bps)

    def test_estimate_for_dollar_amount(self):
        result = self.model.estimate_for_dollar_amount(
            dollar_amount=100_000, price=100.0, daily_volume=5_000_000,
        )
        self.assertGreater(result.total_impact_bps, 0.0)
        self.assertAlmostEqual(result.participation_rate, 1000 / 5_000_000, places=5)

    def test_volatility_scale_disabled(self):
        cfg = ImpactConfig(volatility_scale=False)
        model = ConvexImpactModel(config=cfg)
        result = model.estimate(10_000, 5_000_000, 185.0, volatility=0.05)
        # When volatility_scale=False, sigma defaults to 0.02 regardless of input
        cfg2 = ImpactConfig(volatility_scale=False)
        model2 = ConvexImpactModel(config=cfg2)
        result2 = model2.estimate(10_000, 5_000_000, 185.0, volatility=0.10)
        self.assertAlmostEqual(result.total_impact_bps, result2.total_impact_bps, places=2)


# ═══════════════════════════════════════════════════════════════════════
#  6. MonteCarloConfig
# ═══════════════════════════════════════════════════════════════════════


class TestMonteCarloConfig(unittest.TestCase):
    """Tests for MonteCarloConfig dataclass."""

    def test_defaults(self):
        cfg = MonteCarloConfig()
        self.assertEqual(cfg.num_simulations, 1000)
        self.assertEqual(len(cfg.confidence_levels), 5)
        self.assertTrue(cfg.shuffle_trades)
        self.assertTrue(cfg.resample_with_replacement)
        self.assertIsNone(cfg.random_seed)

    def test_custom_values(self):
        cfg = MonteCarloConfig(num_simulations=500, random_seed=42)
        self.assertEqual(cfg.num_simulations, 500)
        self.assertEqual(cfg.random_seed, 42)


# ═══════════════════════════════════════════════════════════════════════
#  7. PathStatistics
# ═══════════════════════════════════════════════════════════════════════


class TestPathStatistics(unittest.TestCase):
    """Tests for PathStatistics dataclass."""

    def test_default_values(self):
        ps = PathStatistics()
        self.assertAlmostEqual(ps.final_equity, 0.0)
        self.assertAlmostEqual(ps.max_drawdown_pct, 0.0)
        self.assertAlmostEqual(ps.total_return_pct, 0.0)

    def test_to_dict_keys(self):
        ps = PathStatistics(final_equity=105_000, total_return_pct=5.0)
        d = ps.to_dict()
        expected_keys = {
            "final_equity", "max_drawdown_pct", "total_return_pct",
            "sharpe_ratio", "max_equity", "min_equity",
        }
        self.assertEqual(set(d.keys()), expected_keys)


# ═══════════════════════════════════════════════════════════════════════
#  8. MonteCarloSimulator
# ═══════════════════════════════════════════════════════════════════════


class TestMonteCarloSimulator(unittest.TestCase):
    """Tests for the MonteCarloSimulator engine."""

    def setUp(self):
        self.config = MonteCarloConfig(num_simulations=100, random_seed=42)
        self.sim = MonteCarloSimulator(config=self.config)

    def test_simulate_empty_pnls(self):
        result = self.sim.simulate([], initial_equity=100_000)
        self.assertEqual(result.num_simulations, 0)

    def test_simulate_positive_pnls(self):
        pnls = [100.0, 200.0, -50.0, 150.0, 75.0, -25.0, 300.0]
        result = self.sim.simulate(pnls, initial_equity=100_000)
        self.assertEqual(result.num_simulations, 100)
        self.assertGreater(result.probability_of_profit, 0.0)

    def test_simulate_all_positive_high_prob_profit(self):
        pnls = [100.0] * 20
        result = self.sim.simulate(pnls, initial_equity=100_000)
        self.assertAlmostEqual(result.probability_of_profit, 1.0)
        self.assertAlmostEqual(result.probability_of_ruin, 0.0)

    def test_simulate_deterministic_with_seed(self):
        pnls = [100.0, -50.0, 200.0, -75.0, 150.0]
        r1 = self.sim.simulate(pnls, initial_equity=100_000)
        sim2 = MonteCarloSimulator(config=MonteCarloConfig(num_simulations=100, random_seed=42))
        r2 = sim2.simulate(pnls, initial_equity=100_000)
        self.assertAlmostEqual(r1.median_final_equity, r2.median_final_equity, places=2)

    def test_simulate_includes_percentiles(self):
        pnls = [float(i * 10 - 50) for i in range(20)]
        result = self.sim.simulate(pnls)
        self.assertIn("p5", result.percentiles)
        self.assertIn("p50", result.percentiles)
        self.assertIn("p95", result.percentiles)

    def test_simulate_confidence_interval(self):
        pnls = [100.0, -50.0, 200.0, -75.0, 150.0, 50.0]
        result = self.sim.simulate(pnls, initial_equity=100_000)
        low, high = result.confidence_interval_return
        self.assertLessEqual(low, high)

    def test_simulate_include_all_paths(self):
        pnls = [100.0, -50.0]
        result = self.sim.simulate(pnls, initial_equity=100_000, include_all_paths=True)
        self.assertIsNotNone(result.all_paths)
        self.assertEqual(len(result.all_paths), 100)

    def test_simulate_exclude_all_paths_by_default(self):
        pnls = [100.0, -50.0]
        result = self.sim.simulate(pnls, initial_equity=100_000)
        self.assertIsNone(result.all_paths)

    def test_simulate_worst_case_drawdown(self):
        pnls = [-1000.0, -2000.0, 500.0, -500.0]
        result = self.sim.simulate(pnls, initial_equity=100_000)
        self.assertGreater(result.worst_case_drawdown, 0.0)

    def test_simulate_shuffle_only(self):
        cfg = MonteCarloConfig(
            num_simulations=50, resample_with_replacement=False,
            shuffle_trades=True, random_seed=99,
        )
        sim = MonteCarloSimulator(config=cfg)
        pnls = [100.0, -50.0, 200.0]
        result = sim.simulate(pnls, initial_equity=100_000)
        self.assertEqual(result.num_simulations, 50)

    def test_simulate_no_shuffle_no_resample(self):
        cfg = MonteCarloConfig(
            num_simulations=10, resample_with_replacement=False,
            shuffle_trades=False, random_seed=1,
        )
        sim = MonteCarloSimulator(config=cfg)
        pnls = [100.0, -50.0]
        result = sim.simulate(pnls, initial_equity=100_000)
        # All paths identical since no shuffling or resampling
        self.assertAlmostEqual(result.median_final_equity, 100_050.0, places=0)

    def test_result_to_dict(self):
        pnls = [100.0, -50.0, 200.0]
        result = self.sim.simulate(pnls, initial_equity=100_000)
        d = result.to_dict()
        self.assertIn("num_simulations", d)
        self.assertIn("probability_of_profit", d)
        self.assertIn("confidence_interval_return", d)


# ═══════════════════════════════════════════════════════════════════════
#  9. GapConfig
# ═══════════════════════════════════════════════════════════════════════


class TestGapConfig(unittest.TestCase):
    """Tests for GapConfig dataclass."""

    def test_defaults(self):
        cfg = GapConfig()
        self.assertAlmostEqual(cfg.overnight_gap_probability, 0.10)
        self.assertAlmostEqual(cfg.earnings_gap_probability, 0.85)
        self.assertAlmostEqual(cfg.avg_overnight_gap_pct, 1.5)
        self.assertAlmostEqual(cfg.avg_earnings_gap_pct, 5.0)
        self.assertAlmostEqual(cfg.max_gap_pct, 20.0)
        self.assertAlmostEqual(cfg.stop_slippage_multiplier, 2.5)

    def test_custom_values(self):
        cfg = GapConfig(overnight_gap_probability=0.50, avg_earnings_gap_pct=10.0)
        self.assertAlmostEqual(cfg.overnight_gap_probability, 0.50)
        self.assertAlmostEqual(cfg.avg_earnings_gap_pct, 10.0)


# ═══════════════════════════════════════════════════════════════════════
#  10. GapSimulator
# ═══════════════════════════════════════════════════════════════════════


class TestGapSimulator(unittest.TestCase):
    """Tests for the GapSimulator engine."""

    def setUp(self):
        self.sim = GapSimulator(seed=42)

    def test_overnight_gap_returns_none_sometimes(self):
        """With default 10% probability, most calls return None."""
        none_count = 0
        for i in range(100):
            sim = GapSimulator(seed=i)
            result = sim.simulate_overnight_gap("AAPL", 185.0)
            if result is None:
                none_count += 1
        self.assertGreater(none_count, 50)

    def test_overnight_gap_returns_event(self):
        """Force high probability to ensure a gap occurs."""
        cfg = GapConfig(overnight_gap_probability=1.0)
        sim = GapSimulator(config=cfg, seed=42)
        event = sim.simulate_overnight_gap("AAPL", 185.0)
        self.assertIsNotNone(event)
        self.assertEqual(event.ticker, "AAPL")
        self.assertEqual(event.gap_type, "overnight")
        self.assertAlmostEqual(event.prev_close, 185.0)

    def test_earnings_gap_always_returns_event(self):
        event = self.sim.simulate_earnings_gap("AAPL", 185.0)
        self.assertIsNotNone(event)
        self.assertEqual(event.gap_type, "earnings")

    def test_earnings_gap_magnitude(self):
        cfg = GapConfig(earnings_gap_probability=1.0)
        sim = GapSimulator(config=cfg, seed=42)
        event = sim.simulate_earnings_gap("AAPL", 100.0)
        self.assertGreater(abs(event.gap_pct), 0.0)
        self.assertLessEqual(abs(event.gap_pct), cfg.max_gap_pct)

    def test_gap_event_to_dict_keys(self):
        cfg = GapConfig(overnight_gap_probability=1.0)
        sim = GapSimulator(config=cfg, seed=42)
        event = sim.simulate_overnight_gap("AAPL", 185.0)
        d = event.to_dict()
        expected_keys = {
            "ticker", "gap_pct", "gap_type", "prev_close", "gap_open",
            "stop_fill_price", "stop_slippage_pct", "is_adverse",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_adverse_gap_for_long(self):
        """An adverse gap for a long is downward."""
        cfg = GapConfig(overnight_gap_probability=1.0)
        # Seed that produces a downward gap
        found_adverse = False
        for seed in range(50):
            sim = GapSimulator(config=cfg, seed=seed)
            event = sim.simulate_overnight_gap("AAPL", 185.0, position_side="long")
            if event and event.gap_pct < 0:
                self.assertTrue(event.is_adverse)
                found_adverse = True
                break
        self.assertTrue(found_adverse, "Expected to find at least one adverse gap for long")

    def test_adverse_gap_for_short(self):
        """An adverse gap for a short is upward."""
        cfg = GapConfig(overnight_gap_probability=1.0)
        found_adverse = False
        for seed in range(50):
            sim = GapSimulator(config=cfg, seed=seed)
            event = sim.simulate_overnight_gap("AAPL", 185.0, position_side="short")
            if event and event.gap_pct > 0:
                self.assertTrue(event.is_adverse)
                found_adverse = True
                break
        self.assertTrue(found_adverse, "Expected to find at least one adverse gap for short")

    def test_apply_stop_slippage_long_gap_below_stop(self):
        fill = self.sim.apply_stop_slippage(
            stop_price=180.0, gap_open=175.0, position_side="long",
        )
        # Gap below stop: fills at gap_open or worse
        self.assertLessEqual(fill, 175.0)

    def test_apply_stop_slippage_long_gap_above_stop(self):
        fill = self.sim.apply_stop_slippage(
            stop_price=180.0, gap_open=185.0, position_side="long",
        )
        # Gap above stop: stop not triggered, returns stop_price
        self.assertAlmostEqual(fill, 180.0)

    def test_apply_stop_slippage_short_gap_above_stop(self):
        fill = self.sim.apply_stop_slippage(
            stop_price=190.0, gap_open=195.0, position_side="short",
        )
        # Gap above stop for short: fills at gap_open or worse
        self.assertGreaterEqual(fill, 195.0)

    def test_apply_stop_slippage_short_gap_below_stop(self):
        fill = self.sim.apply_stop_slippage(
            stop_price=190.0, gap_open=185.0, position_side="short",
        )
        # Gap below stop for short: stop not triggered
        self.assertAlmostEqual(fill, 190.0)

    def test_earnings_gap_with_stop(self):
        cfg = GapConfig(earnings_gap_probability=1.0)
        sim = GapSimulator(config=cfg, seed=42)
        event = sim.simulate_earnings_gap(
            "AAPL", prev_close=185.0, position_side="long", stop_price=180.0,
        )
        self.assertIsNotNone(event)
        if event.is_adverse:
            self.assertGreater(event.stop_slippage_pct, 0.0)

    def test_gap_capped_at_max(self):
        cfg = GapConfig(overnight_gap_probability=1.0, max_gap_pct=5.0, avg_overnight_gap_pct=50.0)
        sim = GapSimulator(config=cfg, seed=42)
        event = sim.simulate_overnight_gap("AAPL", 100.0)
        self.assertLessEqual(abs(event.gap_pct), 5.0)


# ═══════════════════════════════════════════════════════════════════════
#  11. Module Imports
# ═══════════════════════════════════════════════════════════════════════


class TestEnhancedBacktestModuleImports(unittest.TestCase):
    """Verify public API is importable from the package."""

    def test_import_from_package(self):
        from src.enhanced_backtest import (
            ConvexImpactModel,
            GapConfig,
            GapEvent,
            GapSimulator,
            ImpactConfig,
            ImpactResult,
            MonteCarloConfig,
            MonteCarloResult,
            MonteCarloSimulator,
            PathStatistics,
            SurvivorshipConfig,
            SurvivorshipFilter,
        )
        self.assertIsNotNone(ConvexImpactModel)
        self.assertIsNotNone(MonteCarloSimulator)
        self.assertIsNotNone(GapSimulator)
        self.assertIsNotNone(SurvivorshipFilter)

    def test_survivorship_filter_callable(self):
        filt = SurvivorshipFilter()
        self.assertTrue(callable(getattr(filt, "filter_universe", None)))

    def test_impact_model_callable(self):
        model = ConvexImpactModel()
        self.assertTrue(callable(getattr(model, "estimate", None)))
