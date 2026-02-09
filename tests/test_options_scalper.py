"""Tests for PRD-136: Options & Leveraged ETF Scalping Engine.

Tests options scalping, ETF scalping, strike selection, Greeks validation,
and position sizing.
"""

import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ema_signals.detector import SignalType, TradeSignal
from src.options_scalper.scalper import (
    OptionsScalper,
    ScalpConfig,
    ScalpPosition,
    ScalpResult,
)
from src.options_scalper.etf_scalper import (
    ETFScalper,
    ETFScalpPosition,
    ETFScalpResult,
    ETFScalpSizer,
)
from src.options_scalper.strike_selector import StrikeSelection, StrikeSelector
from src.options_scalper.greeks_gate import GreeksDecision, GreeksGate
from src.options_scalper.sizing import ScalpSizer


def _make_signal(**overrides) -> TradeSignal:
    """Create a TradeSignal with sensible defaults for scalp testing."""
    defaults = {
        "signal_type": SignalType.CLOUD_CROSS_BULLISH,
        "direction": "long",
        "ticker": "SPY",
        "timeframe": "1m",
        "conviction": 80,
        "entry_price": 500.0,
        "stop_loss": 498.0,
        "target_price": 504.0,
        "cloud_states": [],
        "timestamp": datetime.now(timezone.utc),
        "metadata": {},
    }
    defaults.update(overrides)
    return TradeSignal(**defaults)


def _make_chain_data(ticker: str = "SPY", price: float = 500.0) -> list:
    """Create synthetic chain data for testing."""
    return [
        {
            "symbol": f"{ticker}250208C00500000",
            "strike": 500.0,
            "expiry": date.today().isoformat(),
            "option_type": "call",
            "delta": 0.45,
            "gamma": 0.04,
            "theta": -0.08,
            "iv": 0.20,
            "bid": 2.40,
            "ask": 2.60,
            "last": 2.50,
            "volume": 3000,
            "open_interest": 8000,
        },
        {
            "symbol": f"{ticker}250208C00502000",
            "strike": 502.0,
            "expiry": date.today().isoformat(),
            "option_type": "call",
            "delta": 0.35,
            "gamma": 0.05,
            "theta": -0.10,
            "iv": 0.22,
            "bid": 1.50,
            "ask": 1.70,
            "last": 1.60,
            "volume": 2000,
            "open_interest": 5000,
        },
        {
            "symbol": f"{ticker}250208P00498000",
            "strike": 498.0,
            "expiry": date.today().isoformat(),
            "option_type": "put",
            "delta": -0.40,
            "gamma": 0.04,
            "theta": -0.09,
            "iv": 0.21,
            "bid": 2.00,
            "ask": 2.20,
            "last": 2.10,
            "volume": 2500,
            "open_interest": 7000,
        },
    ]


# ═══════════════════════════════════════════════════════════════════════
# 1. StrikeSelector
# ═══════════════════════════════════════════════════════════════════════


class TestStrikeSelector(unittest.TestCase):
    """Test strike selection logic."""

    def setUp(self):
        self.config = ScalpConfig()
        self.selector = StrikeSelector(self.config)

    def test_synthetic_selection_call(self):
        sel = self.selector.select("SPY", "long", underlying_price=500.0)
        self.assertIsNotNone(sel)
        self.assertEqual(sel.option_type, "call")
        self.assertEqual(sel.strike, 500.0)
        self.assertEqual(sel.dte, 0)

    def test_synthetic_selection_put(self):
        sel = self.selector.select("SPY", "short", underlying_price=500.0)
        self.assertIsNotNone(sel)
        self.assertEqual(sel.option_type, "put")

    def test_select_from_chain_call(self):
        chain = _make_chain_data()
        sel = self.selector.select("SPY", "long", chain_data=chain, underlying_price=500.0)
        self.assertIsNotNone(sel)
        self.assertEqual(sel.option_type, "call")
        self.assertGreater(sel.score, 0)

    def test_select_from_chain_put(self):
        chain = _make_chain_data()
        sel = self.selector.select("SPY", "short", chain_data=chain, underlying_price=500.0)
        self.assertIsNotNone(sel)
        self.assertEqual(sel.option_type, "put")

    def test_delta_filtering(self):
        chain = [
            {"option_type": "call", "delta": 0.10, "strike": 510, "bid": 0.5, "ask": 0.6,
             "volume": 1000, "open_interest": 5000},
            {"option_type": "call", "delta": 0.40, "strike": 500, "bid": 2.5, "ask": 2.7,
             "volume": 2000, "open_interest": 8000},
        ]
        filtered = self.selector._filter_by_delta(chain)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["strike"], 500)

    def test_liquidity_filtering(self):
        chain = [
            {"option_type": "call", "delta": 0.40, "strike": 500, "bid": 2.5, "ask": 2.7,
             "volume": 100, "open_interest": 200},  # Too low
            {"option_type": "call", "delta": 0.40, "strike": 501, "bid": 2.0, "ask": 2.2,
             "volume": 2000, "open_interest": 8000},  # Good
        ]
        filtered = self.selector._filter_by_liquidity(chain)
        self.assertEqual(len(filtered), 1)

    def test_strike_scoring(self):
        chain = [
            {"delta": 0.40, "bid": 2.5, "ask": 2.6, "volume": 5000, "open_interest": 10000},
            {"delta": 0.35, "bid": 1.5, "ask": 1.8, "volume": 1000, "open_interest": 3000},
        ]
        scored = self.selector._score_strikes(chain)
        self.assertGreater(scored[0]["score"], scored[1]["score"])

    def test_selection_to_dict(self):
        sel = self.selector.select("SPY", "long", underlying_price=500.0)
        d = sel.to_dict()
        self.assertIn("strike", d)
        self.assertIn("score", d)


# ═══════════════════════════════════════════════════════════════════════
# 2. GreeksGate
# ═══════════════════════════════════════════════════════════════════════


class TestGreeksGate(unittest.TestCase):
    """Test Greeks-based validation."""

    def setUp(self):
        self.config = ScalpConfig()
        self.gate = GreeksGate(self.config)

    def _make_selection(self, **overrides) -> StrikeSelection:
        defaults = {
            "strike": 500.0, "expiry": date.today(), "dte": 0,
            "option_type": "call", "option_symbol": "SPY250208C00500000",
            "delta": 0.45, "gamma": 0.04, "theta": -0.08,
            "iv": 0.20, "bid": 2.40, "ask": 2.60, "mid": 2.50,
            "spread_pct": 0.04, "open_interest": 5000, "volume": 2000,
            "score": 80.0,
        }
        defaults.update(overrides)
        return StrikeSelection(**defaults)

    def test_approve_good_greeks(self):
        sel = self._make_selection()
        signal = _make_signal()
        decision = self.gate.validate(sel, signal)
        self.assertTrue(decision.approved)

    def test_reject_high_iv_non_zero_dte(self):
        sel = self._make_selection(dte=1, iv=0.90)
        signal = _make_signal()
        decision = self.gate.validate(sel, signal)
        self.assertFalse(decision.approved)
        self.assertIn("IV", decision.reason)

    def test_skip_iv_check_for_zero_dte(self):
        sel = self._make_selection(dte=0, iv=0.90)
        signal = _make_signal()
        decision = self.gate.validate(sel, signal)
        self.assertTrue(decision.approved)

    def test_reject_high_theta_burn(self):
        sel = self._make_selection(dte=1, theta=-0.50, mid=2.50)
        signal = _make_signal()
        decision = self.gate.validate(sel, signal)
        self.assertFalse(decision.approved)
        self.assertIn("Theta", decision.reason)

    def test_reject_wide_spread(self):
        sel = self._make_selection(spread_pct=0.15)
        signal = _make_signal()
        decision = self.gate.validate(sel, signal)
        self.assertFalse(decision.approved)
        self.assertIn("Spread", decision.reason)

    def test_reject_delta_out_of_range(self):
        sel = self._make_selection(delta=0.15)
        signal = _make_signal()
        decision = self.gate.validate(sel, signal)
        self.assertFalse(decision.approved)
        self.assertIn("Delta", decision.reason)

    def test_reject_high_gamma_non_zero_dte(self):
        sel = self._make_selection(dte=1, gamma=0.20)
        signal = _make_signal()
        decision = self.gate.validate(sel, signal)
        self.assertFalse(decision.approved)
        self.assertIn("Gamma", decision.reason)

    def test_greeks_decision_to_dict(self):
        d = GreeksDecision(approved=True).to_dict()
        self.assertTrue(d["approved"])


# ═══════════════════════════════════════════════════════════════════════
# 3. ScalpSizer
# ═══════════════════════════════════════════════════════════════════════


class TestScalpSizer(unittest.TestCase):
    """Test options scalp position sizing."""

    def setUp(self):
        self.config = ScalpConfig()
        self.sizer = ScalpSizer(self.config)

    def test_high_conviction_full_size(self):
        contracts = self.sizer.calculate(premium=2.50, conviction=80, account_equity=100_000)
        self.assertGreater(contracts, 0)

    def test_medium_conviction_half_size(self):
        high = self.sizer.calculate(premium=2.50, conviction=80, account_equity=100_000)
        med = self.sizer.calculate(premium=2.50, conviction=60, account_equity=100_000)
        self.assertGreater(high, med)

    def test_zero_premium_returns_zero(self):
        contracts = self.sizer.calculate(premium=0, conviction=80, account_equity=100_000)
        self.assertEqual(contracts, 0)

    def test_minimum_one_contract(self):
        contracts = self.sizer.calculate(premium=50.0, conviction=80, account_equity=100_000)
        self.assertGreaterEqual(contracts, 1)

    def test_respects_risk_budget(self):
        contracts = self.sizer.calculate(premium=2.50, conviction=80, account_equity=100_000)
        max_risk = 100_000 * 0.02
        actual_risk = contracts * 2.50 * 100 * 0.50
        self.assertLessEqual(actual_risk, max_risk * 1.01)  # Small float tolerance


# ═══════════════════════════════════════════════════════════════════════
# 4. OptionsScalper
# ═══════════════════════════════════════════════════════════════════════


class TestOptionsScalper(unittest.TestCase):
    """Test full options scalping pipeline."""

    def setUp(self):
        self.config = ScalpConfig()
        self.scalper = OptionsScalper(config=self.config)

    def test_process_valid_signal(self):
        signal = _make_signal(ticker="SPY", conviction=80)
        result = self.scalper.process_signal(signal, account_equity=100_000)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.position)
        self.assertEqual(len(self.scalper.positions), 1)

    def test_reject_low_conviction(self):
        signal = _make_signal(conviction=30)
        result = self.scalper.process_signal(signal)
        self.assertFalse(result.success)
        self.assertIn("filtered", result.rejection_reason)

    def test_reject_non_scalp_ticker(self):
        signal = _make_signal(ticker="UNKNOWN_CO")
        result = self.scalper.process_signal(signal)
        self.assertFalse(result.success)

    def test_max_concurrent_scalps(self):
        for i in range(3):
            signal = _make_signal(
                ticker=["SPY", "QQQ", "NVDA"][i],
                conviction=80,
            )
            self.scalper.process_signal(signal)
        signal = _make_signal(ticker="AAPL", conviction=80)
        result = self.scalper.process_signal(signal)
        self.assertFalse(result.success)
        self.assertIn("Max concurrent", result.rejection_reason)

    def test_no_average_up_losing(self):
        signal = _make_signal(ticker="SPY", conviction=80)
        self.scalper.process_signal(signal)
        # Simulate loss
        self.scalper.positions[0].current_price = self.scalper.positions[0].entry_price * 0.7
        signal2 = _make_signal(ticker="SPY", conviction=80)
        result = self.scalper.process_signal(signal2)
        self.assertFalse(result.success)
        self.assertIn("losing", result.rejection_reason)

    def test_with_chain_data(self):
        signal = _make_signal(ticker="SPY", conviction=80)
        chain = _make_chain_data()
        result = self.scalper.process_signal(signal, chain_data=chain)
        self.assertTrue(result.success)

    def test_scalp_result_to_dict(self):
        signal = _make_signal(ticker="SPY", conviction=80)
        result = self.scalper.process_signal(signal)
        d = result.to_dict()
        self.assertTrue(d["success"])


# ═══════════════════════════════════════════════════════════════════════
# 5. ScalpPosition
# ═══════════════════════════════════════════════════════════════════════


class TestScalpPosition(unittest.TestCase):
    """Test scalp position properties."""

    def _make_pos(self, **overrides) -> ScalpPosition:
        defaults = {
            "ticker": "SPY", "option_symbol": "SPY250208C00500000",
            "option_type": "call", "strike": 500.0, "expiry": date.today(),
            "dte": 0, "direction": "long_call", "contracts": 5,
            "entry_price": 2.50, "current_price": 3.00,
            "delta": 0.45, "theta": -0.08, "iv": 0.20,
            "entry_time": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return ScalpPosition(**defaults)

    def test_unrealized_pnl(self):
        pos = self._make_pos(entry_price=2.50, current_price=3.00, contracts=5)
        self.assertAlmostEqual(pos.unrealized_pnl, 250.0)  # 0.50 * 5 * 100

    def test_unrealized_pnl_pct(self):
        pos = self._make_pos(entry_price=2.00, current_price=2.50)
        self.assertAlmostEqual(pos.unrealized_pnl_pct, 0.25)

    def test_to_dict(self):
        pos = self._make_pos()
        d = pos.to_dict()
        self.assertIn("delta", d)
        self.assertIn("pnl", d)


# ═══════════════════════════════════════════════════════════════════════
# 6. ETFScalper
# ═══════════════════════════════════════════════════════════════════════


class TestETFScalper(unittest.TestCase):
    """Test leveraged ETF scalping."""

    def setUp(self):
        self.config = ScalpConfig()
        self.scalper = ETFScalper(config=self.config)

    def test_process_valid_signal(self):
        signal = _make_signal(ticker="QQQ", direction="long", conviction=80)
        result = self.scalper.process_signal(signal)
        self.assertTrue(result.success)
        self.assertEqual(result.position.ticker, "TQQQ")
        self.assertEqual(result.position.leverage, 3.0)

    def test_short_signal_uses_inverse(self):
        signal = _make_signal(ticker="SPY", direction="short", conviction=80)
        result = self.scalper.process_signal(signal)
        self.assertTrue(result.success)
        self.assertEqual(result.position.ticker, "SPXS")

    def test_reject_low_conviction(self):
        signal = _make_signal(conviction=30)
        result = self.scalper.process_signal(signal)
        self.assertFalse(result.success)

    def test_max_concurrent_etf_scalps(self):
        tickers = ["SPY", "QQQ", "NVDA", "AAPL", "MSFT"]
        for t in tickers:
            signal = _make_signal(ticker=t, direction="long", conviction=80)
            self.scalper.process_signal(signal)
        signal = _make_signal(ticker="META", conviction=80)
        result = self.scalper.process_signal(signal)
        self.assertFalse(result.success)
        self.assertIn("Max concurrent", result.rejection_reason)

    def test_stop_loss_exit(self):
        signal = _make_signal(ticker="QQQ", direction="long", conviction=80)
        self.scalper.process_signal(signal)
        pos = self.scalper.positions[0]
        pos.current_price = pos.stop_loss - 1.0  # Below stop
        exits = self.scalper.check_exits()
        self.assertEqual(len(exits), 1)
        self.assertEqual(exits[0]["reason"], "stop_loss")
        self.assertEqual(len(self.scalper.positions), 0)

    def test_profit_target_exit(self):
        signal = _make_signal(ticker="QQQ", direction="long", conviction=80)
        self.scalper.process_signal(signal)
        pos = self.scalper.positions[0]
        pos.current_price = pos.target_price + 1.0  # Above target
        exits = self.scalper.check_exits()
        self.assertEqual(len(exits), 1)
        self.assertEqual(exits[0]["reason"], "profit_target")

    def test_etf_scalp_result_to_dict(self):
        signal = _make_signal(ticker="QQQ", conviction=80)
        result = self.scalper.process_signal(signal)
        d = result.to_dict()
        self.assertTrue(d["success"])

    def test_sector_mapping(self):
        signal = _make_signal(ticker="NVDA", direction="long", conviction=80)
        result = self.scalper.process_signal(signal)
        self.assertTrue(result.success)
        self.assertEqual(result.position.ticker, "SOXL")


# ═══════════════════════════════════════════════════════════════════════
# 7. ETFScalpSizer
# ═══════════════════════════════════════════════════════════════════════


class TestETFScalpSizer(unittest.TestCase):
    """Test leveraged ETF scalp sizing."""

    def setUp(self):
        self.config = ScalpConfig()
        self.sizer = ETFScalpSizer(self.config)

    def test_basic_sizing(self):
        shares = self.sizer.calculate(
            etf_price=50.0, leverage=3.0, conviction=80, account_equity=100_000
        )
        self.assertGreater(shares, 0)

    def test_conviction_adjustment(self):
        high = self.sizer.calculate(50.0, 3.0, 80, 100_000)
        low = self.sizer.calculate(50.0, 3.0, 60, 100_000)
        self.assertGreater(high, low)

    def test_compute_stop_target_long(self):
        stop, target = self.sizer.compute_stop_target(50.0, "long")
        self.assertLess(stop, 50.0)
        self.assertGreater(target, 50.0)

    def test_compute_stop_target_short(self):
        stop, target = self.sizer.compute_stop_target(50.0, "short")
        self.assertGreater(stop, 50.0)
        self.assertLess(target, 50.0)

    def test_zero_price_returns_zero(self):
        shares = self.sizer.calculate(0.0, 3.0, 80, 100_000)
        self.assertEqual(shares, 0)


# ═══════════════════════════════════════════════════════════════════════
# 8. ETFScalpPosition
# ═══════════════════════════════════════════════════════════════════════


class TestETFScalpPosition(unittest.TestCase):
    """Test ETF scalp position properties."""

    def test_unrealized_pnl_long(self):
        pos = ETFScalpPosition(
            ticker="TQQQ", original_signal_ticker="QQQ",
            leverage=3.0, direction="long", shares=100,
            entry_price=50.0, current_price=51.0,
            stop_loss=49.0, target_price=52.0,
            entry_time=datetime.now(timezone.utc),
        )
        self.assertAlmostEqual(pos.unrealized_pnl, 100.0)

    def test_unrealized_pnl_short(self):
        pos = ETFScalpPosition(
            ticker="SQQQ", original_signal_ticker="QQQ",
            leverage=3.0, direction="short", shares=100,
            entry_price=50.0, current_price=48.0,
            stop_loss=52.0, target_price=47.0,
            entry_time=datetime.now(timezone.utc),
        )
        self.assertAlmostEqual(pos.unrealized_pnl, 200.0)

    def test_to_dict(self):
        pos = ETFScalpPosition(
            ticker="TQQQ", original_signal_ticker="QQQ",
            leverage=3.0, direction="long", shares=100,
            entry_price=50.0, current_price=51.0,
            stop_loss=49.0, target_price=52.0,
            entry_time=datetime.now(timezone.utc),
        )
        d = pos.to_dict()
        self.assertIn("leverage", d)
        self.assertIn("pnl", d)


# ═══════════════════════════════════════════════════════════════════════
# 9. Module Imports
# ═══════════════════════════════════════════════════════════════════════


class TestModuleImports(unittest.TestCase):
    """Test that all public symbols are importable."""

    def test_import_all(self):
        from src.options_scalper import (
            OptionsScalper, ScalpConfig, ScalpPosition, ScalpResult,
            ETFScalper, ETFScalpPosition, ETFScalpResult, ETFScalpSizer,
            StrikeSelector, StrikeSelection,
            GreeksGate, GreeksDecision,
            ScalpSizer,
        )
        self.assertTrue(callable(OptionsScalper))
        self.assertTrue(callable(ETFScalper))
        self.assertTrue(callable(ScalpSizer))


if __name__ == "__main__":
    unittest.main()
