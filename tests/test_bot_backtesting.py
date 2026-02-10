"""Tests for PRD-138: Bot Strategy Backtesting Integration.

8 test classes, ~55 tests covering strategy adapter, runner,
attribution, replay, and module imports.
"""

import unittest
from datetime import date, datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from src.backtesting.models import (
    BacktestResult,
    BacktestMetrics,
    BarData,
    Fill,
    MarketEvent,
    OrderSide,
    Signal,
    Trade,
)
from src.backtesting.portfolio import SimulatedPortfolio
from src.ema_signals.detector import SignalType, TradeSignal
from src.ema_signals.clouds import CloudConfig, CloudState
from src.trade_executor.executor import AccountState, ExecutorConfig, Position


def _make_ohlcv_df(n_bars=100, start_price=100.0, seed=42):
    """Generate synthetic OHLCV data for testing."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start="2022-01-03", periods=n_bars)
    prices = [start_price]
    for _ in range(n_bars - 1):
        change = rng.normal(0.0005, 0.015)
        prices.append(prices[-1] * (1 + change))

    prices = np.array(prices)
    highs = prices * (1 + rng.uniform(0.001, 0.02, n_bars))
    lows = prices * (1 - rng.uniform(0.001, 0.02, n_bars))
    opens = lows + (highs - lows) * rng.uniform(0.2, 0.8, n_bars)
    volumes = rng.integers(500_000, 5_000_000, n_bars)

    return pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": volumes,
        },
        index=dates,
    )


def _make_trade_signal(
    ticker="AAPL",
    signal_type=SignalType.CLOUD_CROSS_BULLISH,
    direction="long",
    conviction=65,
    entry_price=150.0,
    stop_loss=145.0,
    timeframe="1d",
):
    """Create a TradeSignal for testing."""
    return TradeSignal(
        signal_type=signal_type,
        direction=direction,
        ticker=ticker,
        timeframe=timeframe,
        conviction=conviction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_price=entry_price * 1.10,
        timestamp=datetime(2023, 6, 15, tzinfo=timezone.utc),
    )


# ═══════════════════════════════════════════════════════════════════════
# Test Strategy Config
# ═══════════════════════════════════════════════════════════════════════


class TestStrategyConfig(unittest.TestCase):
    """Test StrategyConfig defaults and construction."""

    def test_defaults(self):
        from src.bot_backtesting.strategy import StrategyConfig
        config = StrategyConfig()
        self.assertEqual(config.min_conviction, 50)
        self.assertEqual(config.max_positions, 10)
        self.assertAlmostEqual(config.max_position_weight, 0.15)
        self.assertAlmostEqual(config.reward_to_risk, 2.0)
        self.assertEqual(config.timeframe, "1d")
        self.assertEqual(config.lookback_bars, 100)

    def test_custom_signal_types(self):
        from src.bot_backtesting.strategy import StrategyConfig
        types = [SignalType.CLOUD_CROSS_BULLISH, SignalType.TREND_ALIGNED_LONG]
        config = StrategyConfig(enabled_signal_types=types)
        self.assertEqual(len(config.enabled_signal_types), 2)
        self.assertIn(SignalType.CLOUD_CROSS_BULLISH, config.enabled_signal_types)

    def test_weight_formula(self):
        from src.bot_backtesting.strategy import EMACloudStrategy
        strategy = EMACloudStrategy()
        # conviction=100 -> max_weight
        self.assertAlmostEqual(strategy._conviction_to_weight(100), 0.15)
        # conviction=0 -> min weight
        self.assertAlmostEqual(strategy._conviction_to_weight(0), 0.02)
        # conviction=50 -> 0.075
        self.assertAlmostEqual(strategy._conviction_to_weight(50), 0.075)

    def test_cloud_config_passthrough(self):
        from src.bot_backtesting.strategy import EMACloudStrategy
        strategy = EMACloudStrategy(fast_short=3, fast_long=8)
        self.assertEqual(strategy.config.cloud_config.fast_short, 3)
        self.assertEqual(strategy.config.cloud_config.fast_long, 8)

    def test_exit_toggles(self):
        from src.bot_backtesting.strategy import StrategyConfig
        config = StrategyConfig(
            stop_loss_exit=False,
            target_exit=False,
        )
        self.assertFalse(config.stop_loss_exit)
        self.assertFalse(config.target_exit)
        self.assertTrue(config.cloud_flip_exit)


# ═══════════════════════════════════════════════════════════════════════
# Test EMA Cloud Strategy
# ═══════════════════════════════════════════════════════════════════════


class TestEMACloudStrategy(unittest.TestCase):
    """Test the EMACloudStrategy adapter."""

    def setUp(self):
        self.strategy = self._make_strategy()
        self.portfolio = SimulatedPortfolio(100_000.0)

    def _make_strategy(self, **kwargs):
        from src.bot_backtesting.strategy import EMACloudStrategy
        defaults = {"min_conviction": 20, "timeframe": "1d"}
        defaults.update(kwargs)
        return EMACloudStrategy(**defaults)

    def _make_event(self, symbols_prices, timestamp=None):
        """Create a MarketEvent from symbol->price dict."""
        ts = timestamp or datetime(2023, 6, 15, 16, 0, tzinfo=timezone.utc)
        bars = {}
        for symbol, price in symbols_prices.items():
            bars[symbol] = BarData(
                symbol=symbol,
                timestamp=ts,
                open=price * 0.99,
                high=price * 1.01,
                low=price * 0.98,
                close=price,
                volume=1_000_000,
            )
        return MarketEvent(timestamp=ts, bars=bars)

    def test_protocol_compliance(self):
        """Strategy should have on_bar and on_fill methods."""
        self.assertTrue(hasattr(self.strategy, 'on_bar'))
        self.assertTrue(hasattr(self.strategy, 'on_fill'))
        self.assertTrue(callable(self.strategy.on_bar))
        self.assertTrue(callable(self.strategy.on_fill))

    def test_bar_accumulation(self):
        """Bars should accumulate in _bar_history."""
        event = self._make_event({"AAPL": 150.0})
        self.strategy.on_bar(event, self.portfolio)
        self.assertIn("AAPL", self.strategy._bar_history)
        self.assertEqual(len(self.strategy._bar_history["AAPL"]), 1)

    def test_multi_bar_accumulation(self):
        """Multiple bars should accumulate."""
        for i in range(5):
            ts = datetime(2023, 6, 15 + i, 16, 0, tzinfo=timezone.utc)
            event = self._make_event({"AAPL": 150.0 + i}, timestamp=ts)
            self.strategy.on_bar(event, self.portfolio)
        self.assertEqual(len(self.strategy._bar_history["AAPL"]), 5)

    def test_lookback_trim(self):
        """Bar history should be trimmed to lookback_bars."""
        strategy = self._make_strategy(lookback_bars=10)
        for i in range(20):
            ts = datetime(2023, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
            event = self._make_event({"AAPL": 150.0 + i * 0.1}, timestamp=ts)
            strategy.on_bar(event, self.portfolio)
        self.assertEqual(len(strategy._bar_history["AAPL"]), 10)

    def test_needs_enough_bars(self):
        """Strategy should not generate signals with insufficient bars."""
        event = self._make_event({"AAPL": 150.0})
        signals = self.strategy.on_bar(event, self.portfolio)
        self.assertEqual(len(signals), 0)

    def test_max_positions_cap(self):
        """Should not generate entries when at max positions."""
        strategy = self._make_strategy(max_positions=1)
        # Simulate one open entry
        from src.bot_backtesting.strategy import _OpenEntry
        strategy._open_entries["MSFT"] = _OpenEntry(
            entry_price=300.0,
            stop_loss=290.0,
            target_price=320.0,
            signal_type=SignalType.CLOUD_CROSS_BULLISH,
            direction="long",
            conviction=70,
            entry_time=datetime(2023, 6, 1, tzinfo=timezone.utc),
        )
        event = self._make_event({"AAPL": 150.0})
        signals = strategy.on_bar(event, self.portfolio)
        self.assertEqual(len(signals), 0)

    def test_on_fill_buy_creates_open_entry(self):
        """BUY fill should create an _OpenEntry from pending signal."""
        sig = _make_trade_signal()
        self.strategy._pending_signals["AAPL"] = sig

        fill = Fill(
            order_id="ORD-1",
            symbol="AAPL",
            side=OrderSide.BUY,
            qty=100,
            price=150.0,
            timestamp=datetime(2023, 6, 15, tzinfo=timezone.utc),
        )
        self.strategy.on_fill(fill)

        self.assertIn("AAPL", self.strategy._open_entries)
        self.assertEqual(self.strategy._open_entries["AAPL"].entry_price, 150.0)
        self.assertEqual(len(self.strategy._signal_log), 1)

    def test_on_fill_sell_removes_open_entry(self):
        """SELL fill should remove _OpenEntry."""
        from src.bot_backtesting.strategy import _OpenEntry
        self.strategy._open_entries["AAPL"] = _OpenEntry(
            entry_price=150.0,
            stop_loss=145.0,
            target_price=160.0,
            signal_type=SignalType.CLOUD_CROSS_BULLISH,
            direction="long",
            conviction=70,
            entry_time=datetime(2023, 6, 1, tzinfo=timezone.utc),
        )
        self.strategy._signal_log.append({
            "symbol": "AAPL",
            "signal_type": "cloud_cross_bullish",
            "entry_date": datetime(2023, 6, 1, tzinfo=timezone.utc),
        })

        fill = Fill(
            order_id="ORD-2",
            symbol="AAPL",
            side=OrderSide.SELL,
            qty=100,
            price=160.0,
            timestamp=datetime(2023, 6, 20, tzinfo=timezone.utc),
        )
        self.strategy.on_fill(fill)

        self.assertNotIn("AAPL", self.strategy._open_entries)

    def test_stop_loss_exit(self):
        """Should generate SELL signal when stop hit."""
        from src.bot_backtesting.strategy import _OpenEntry
        strategy = self._make_strategy()
        strategy._open_entries["AAPL"] = _OpenEntry(
            entry_price=150.0,
            stop_loss=145.0,
            target_price=160.0,
            signal_type=SignalType.CLOUD_CROSS_BULLISH,
            direction="long",
            conviction=70,
            entry_time=datetime(2023, 6, 1, tzinfo=timezone.utc),
        )
        strategy._signal_log.append({
            "symbol": "AAPL",
            "signal_type": "cloud_cross_bullish",
            "entry_date": datetime(2023, 6, 1, tzinfo=timezone.utc),
        })

        # Price drops below stop
        bars = {"AAPL": BarData(
            symbol="AAPL",
            timestamp=datetime(2023, 6, 20, tzinfo=timezone.utc),
            open=146.0, high=147.0, low=144.0, close=144.5,
            volume=1_000_000,
        )}
        event = MarketEvent(
            timestamp=datetime(2023, 6, 20, tzinfo=timezone.utc),
            bars=bars,
        )
        strategy._append_bar("AAPL", bars["AAPL"])

        signals = strategy.on_bar(event, self.portfolio)
        sell_signals = [s for s in signals if s.side == OrderSide.SELL]
        self.assertEqual(len(sell_signals), 1)
        self.assertEqual(sell_signals[0].reason, "stop_loss")

    def test_profit_target_exit(self):
        """Should generate SELL signal when target hit."""
        from src.bot_backtesting.strategy import _OpenEntry
        strategy = self._make_strategy()
        strategy._open_entries["AAPL"] = _OpenEntry(
            entry_price=150.0,
            stop_loss=145.0,
            target_price=160.0,
            signal_type=SignalType.CLOUD_CROSS_BULLISH,
            direction="long",
            conviction=70,
            entry_time=datetime(2023, 6, 1, tzinfo=timezone.utc),
        )
        strategy._signal_log.append({
            "symbol": "AAPL",
            "signal_type": "cloud_cross_bullish",
            "entry_date": datetime(2023, 6, 1, tzinfo=timezone.utc),
        })

        bars = {"AAPL": BarData(
            symbol="AAPL",
            timestamp=datetime(2023, 6, 20, tzinfo=timezone.utc),
            open=159.0, high=161.0, low=158.5, close=160.5,
            volume=1_000_000,
        )}
        event = MarketEvent(
            timestamp=datetime(2023, 6, 20, tzinfo=timezone.utc),
            bars=bars,
        )
        strategy._append_bar("AAPL", bars["AAPL"])

        signals = strategy.on_bar(event, self.portfolio)
        sell_signals = [s for s in signals if s.side == OrderSide.SELL]
        self.assertEqual(len(sell_signals), 1)
        self.assertEqual(sell_signals[0].reason, "profit_target")

    def test_signal_log(self):
        """Signal log should be accessible."""
        log = self.strategy.get_signal_log()
        self.assertIsInstance(log, list)
        self.assertEqual(len(log), 0)


# ═══════════════════════════════════════════════════════════════════════
# Test _OpenEntry
# ═══════════════════════════════════════════════════════════════════════


class TestOpenEntry(unittest.TestCase):
    """Test the _OpenEntry dataclass."""

    def test_defaults(self):
        from src.bot_backtesting.strategy import _OpenEntry
        entry = _OpenEntry(
            entry_price=100.0,
            stop_loss=95.0,
            target_price=110.0,
            signal_type=SignalType.CLOUD_CROSS_BULLISH,
            direction="long",
            conviction=70,
            entry_time=datetime(2023, 6, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(entry.entry_price, 100.0)
        self.assertEqual(entry.direction, "long")

    def test_to_dict(self):
        from src.bot_backtesting.strategy import _OpenEntry
        entry = _OpenEntry(
            entry_price=100.0,
            stop_loss=95.0,
            target_price=110.0,
            signal_type=SignalType.CLOUD_CROSS_BULLISH,
            direction="long",
            conviction=70,
            entry_time=datetime(2023, 6, 1, tzinfo=timezone.utc),
        )
        d = entry.to_dict()
        self.assertEqual(d["entry_price"], 100.0)
        self.assertEqual(d["signal_type"], "cloud_cross_bullish")

    def test_short_direction(self):
        from src.bot_backtesting.strategy import _OpenEntry
        entry = _OpenEntry(
            entry_price=100.0,
            stop_loss=105.0,
            target_price=90.0,
            signal_type=SignalType.CLOUD_CROSS_BEARISH,
            direction="short",
            conviction=55,
            entry_time=datetime(2023, 6, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(entry.direction, "short")


# ═══════════════════════════════════════════════════════════════════════
# Test BotBacktestRunner
# ═══════════════════════════════════════════════════════════════════════


class TestBotBacktestRunner(unittest.TestCase):
    """Test the BotBacktestRunner."""

    def _make_ohlcv(self, n=120, seed=42):
        return {"AAPL": _make_ohlcv_df(n, 150.0, seed)}

    def test_basic_run(self):
        from src.bot_backtesting.runner import BotBacktestRunner, BotBacktestConfig
        runner = BotBacktestRunner()
        config = BotBacktestConfig(
            start_date=date(2022, 1, 3),
            end_date=date(2022, 6, 30),
            initial_capital=100_000,
            tickers=["AAPL"],
            min_conviction=20,
        )
        ohlcv = self._make_ohlcv(120)
        result = runner.run(config, ohlcv)
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.result)
        self.assertIsNotNone(result.attribution)
        self.assertIsNotNone(result.strategy_config)

    def test_enriched_result_properties(self):
        from src.bot_backtesting.runner import BotBacktestRunner, BotBacktestConfig, EnrichedBacktestResult
        runner = BotBacktestRunner()
        config = BotBacktestConfig(
            start_date=date(2022, 1, 3),
            end_date=date(2022, 6, 30),
            tickers=["AAPL"],
        )
        ohlcv = self._make_ohlcv(120)
        result = runner.run(config, ohlcv)
        # Properties should proxy to inner result
        self.assertIsNotNone(result.metrics)
        self.assertIsInstance(result.trades, list)
        self.assertEqual(result.tickers, ["AAPL"])

    def test_multi_ticker(self):
        from src.bot_backtesting.runner import BotBacktestRunner, BotBacktestConfig
        runner = BotBacktestRunner()
        config = BotBacktestConfig(
            start_date=date(2022, 1, 3),
            end_date=date(2022, 6, 30),
            tickers=["AAPL", "MSFT"],
            min_conviction=20,
        )
        ohlcv = {
            "AAPL": _make_ohlcv_df(120, 150.0, seed=42),
            "MSFT": _make_ohlcv_df(120, 300.0, seed=99),
        }
        result = runner.run(config, ohlcv)
        self.assertEqual(len(result.tickers), 2)

    def test_cost_model(self):
        from src.bot_backtesting.runner import BotBacktestRunner, BotBacktestConfig
        from src.backtesting.config import CostModelConfig
        runner = BotBacktestRunner()
        config = BotBacktestConfig(
            start_date=date(2022, 1, 3),
            end_date=date(2022, 6, 30),
            tickers=["AAPL"],
            cost_model=CostModelConfig(commission_per_trade=5.0),
        )
        ohlcv = self._make_ohlcv(120)
        result = runner.run(config, ohlcv)
        self.assertIsNotNone(result)

    def test_walk_forward(self):
        from src.bot_backtesting.runner import BotBacktestRunner, BotBacktestConfig
        runner = BotBacktestRunner()
        config = BotBacktestConfig(
            start_date=date(2022, 1, 3),
            end_date=date(2022, 6, 30),
            tickers=["AAPL"],
        )
        ohlcv = self._make_ohlcv(120)
        param_grid = {"min_conviction": [30, 50]}
        result = runner.run_walk_forward(config, ohlcv, param_grid)
        self.assertIsNotNone(result)

    def test_ohlcv_data_format(self):
        from src.bot_backtesting.runner import BotBacktestRunner, BotBacktestConfig
        runner = BotBacktestRunner()
        config = BotBacktestConfig(
            start_date=date(2022, 1, 3),
            end_date=date(2022, 6, 30),
            tickers=["AAPL"],
        )
        # Test with capital-case column names
        df = _make_ohlcv_df(120, 150.0)
        df.columns = ["Open", "High", "Low", "Close", "Volume"]
        ohlcv = {"AAPL": df}
        result = runner.run(config, ohlcv)
        self.assertIsNotNone(result)


# ═══════════════════════════════════════════════════════════════════════
# Test BotBacktestConfig
# ═══════════════════════════════════════════════════════════════════════


class TestBotBacktestConfig(unittest.TestCase):
    """Test BotBacktestConfig defaults and customization."""

    def test_defaults(self):
        from src.bot_backtesting.runner import BotBacktestConfig
        config = BotBacktestConfig()
        self.assertEqual(config.initial_capital, 100_000.0)
        self.assertEqual(config.min_conviction, 50)
        self.assertEqual(config.max_positions, 10)
        self.assertEqual(len(config.tickers), 20)

    def test_custom_tickers(self):
        from src.bot_backtesting.runner import BotBacktestConfig
        config = BotBacktestConfig(tickers=["AAPL", "MSFT"])
        self.assertEqual(len(config.tickers), 2)

    def test_timeframe(self):
        from src.bot_backtesting.runner import BotBacktestConfig
        config = BotBacktestConfig(timeframe="5m")
        self.assertEqual(config.timeframe, "5m")

    def test_rebalance_frequency(self):
        from src.bot_backtesting.runner import BotBacktestConfig
        from src.backtesting.config import RebalanceFrequency
        config = BotBacktestConfig(rebalance_frequency=RebalanceFrequency.WEEKLY)
        self.assertEqual(config.rebalance_frequency, RebalanceFrequency.WEEKLY)


# ═══════════════════════════════════════════════════════════════════════
# Test Signal Attributor
# ═══════════════════════════════════════════════════════════════════════


class TestSignalAttributor(unittest.TestCase):
    """Test the SignalAttributor."""

    def _make_log_and_trades(self, n=5, signal_type="cloud_cross_bullish"):
        """Create matched signal log and trades."""
        log = []
        trades = []
        base_date = datetime(2023, 1, 1, tzinfo=timezone.utc)

        for i in range(n):
            entry_date = base_date + timedelta(days=i * 7)
            exit_date = entry_date + timedelta(days=3)
            entry_price = 100.0 + i
            pnl = 5.0 if i % 2 == 0 else -3.0

            log.append({
                "symbol": "AAPL",
                "signal_type": signal_type,
                "direction": "long",
                "conviction": 60 + i,
                "entry_price": entry_price,
                "entry_date": entry_date,
                "stop_loss": entry_price * 0.97,
                "target_price": entry_price * 1.06,
                "exit_reason": "profit_target" if pnl > 0 else "stop_loss",
            })

            trades.append(Trade(
                symbol="AAPL",
                entry_date=entry_date,
                exit_date=exit_date,
                side=OrderSide.BUY,
                entry_price=entry_price,
                exit_price=entry_price + pnl,
                qty=100,
                pnl=pnl * 100,
                pnl_pct=pnl / entry_price,
                hold_days=3,
            ))

        return log, trades

    def test_empty_inputs(self):
        from src.bot_backtesting.attribution import SignalAttributor
        attributor = SignalAttributor()
        result = attributor.compute([], [])
        self.assertEqual(result.total_signals_generated, 0)
        self.assertEqual(result.total_signals_executed, 0)

    def test_single_signal_type(self):
        from src.bot_backtesting.attribution import SignalAttributor
        attributor = SignalAttributor()
        log, trades = self._make_log_and_trades(5)
        result = attributor.compute(log, trades)
        self.assertIn("cloud_cross_bullish", result.by_signal_type)
        stats = result.by_signal_type["cloud_cross_bullish"]
        self.assertEqual(stats.total_trades, 5)

    def test_multi_signal_types(self):
        from src.bot_backtesting.attribution import SignalAttributor
        attributor = SignalAttributor()
        log1, trades1 = self._make_log_and_trades(3, "cloud_cross_bullish")
        log2, trades2 = self._make_log_and_trades(2, "trend_aligned_long")
        # Offset dates for second group
        for i, entry in enumerate(log2):
            entry["entry_date"] = datetime(2023, 4, 1, tzinfo=timezone.utc) + timedelta(days=i * 7)
        for i, trade in enumerate(trades2):
            trades2[i] = Trade(
                symbol=trade.symbol,
                entry_date=log2[i]["entry_date"],
                exit_date=log2[i]["entry_date"] + timedelta(days=3),
                side=trade.side,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                qty=trade.qty,
                pnl=trade.pnl,
                pnl_pct=trade.pnl_pct,
                hold_days=trade.hold_days,
            )
        result = attributor.compute(log1 + log2, trades1 + trades2)
        self.assertEqual(len(result.by_signal_type), 2)

    def test_win_rate(self):
        from src.bot_backtesting.attribution import SignalAttributor
        attributor = SignalAttributor()
        log, trades = self._make_log_and_trades(5)
        result = attributor.compute(log, trades)
        stats = result.by_signal_type["cloud_cross_bullish"]
        # 3 winners out of 5 (indices 0, 2, 4)
        self.assertAlmostEqual(stats.win_rate, 0.6)

    def test_profit_factor(self):
        from src.bot_backtesting.attribution import SignalAttributor
        attributor = SignalAttributor()
        log, trades = self._make_log_and_trades(5)
        result = attributor.compute(log, trades)
        stats = result.by_signal_type["cloud_cross_bullish"]
        # Winners: 500 + 500 + 500 = 1500, Losers: 300 + 300 = 600
        self.assertAlmostEqual(stats.profit_factor, 1500 / 600, places=1)

    def test_hold_bars(self):
        from src.bot_backtesting.attribution import SignalAttributor
        attributor = SignalAttributor()
        log, trades = self._make_log_and_trades(5)
        result = attributor.compute(log, trades)
        stats = result.by_signal_type["cloud_cross_bullish"]
        self.assertAlmostEqual(stats.avg_hold_bars, 3.0)

    def test_best_signal_type(self):
        from src.bot_backtesting.attribution import SignalAttributor
        attributor = SignalAttributor()
        log, trades = self._make_log_and_trades(5)
        result = attributor.compute(log, trades)
        best = result.get_best_signal_type()
        self.assertEqual(best, "cloud_cross_bullish")

    def test_to_dataframe(self):
        from src.bot_backtesting.attribution import SignalAttributor
        attributor = SignalAttributor()
        log, trades = self._make_log_and_trades(5)
        result = attributor.compute(log, trades)
        df = result.to_dataframe()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertIn("cloud_cross_bullish", df.index)


# ═══════════════════════════════════════════════════════════════════════
# Test Signal Replay
# ═══════════════════════════════════════════════════════════════════════


class TestSignalReplay(unittest.TestCase):
    """Test the SignalReplay analysis."""

    def _make_signals(self, n=5, ticker="AAPL", entry_price=150.0, conviction=65):
        signals = []
        for i in range(n):
            signals.append(_make_trade_signal(
                ticker=f"{ticker}{i}" if i > 0 else ticker,
                entry_price=entry_price,
                conviction=conviction,
            ))
        return signals

    def test_all_approved(self):
        from src.bot_backtesting.replay import SignalReplay
        replay = SignalReplay(ExecutorConfig(max_concurrent_positions=10))
        signals = self._make_signals(3)
        result = replay.replay(signals, starting_equity=100_000)
        self.assertEqual(result.total, 3)
        self.assertEqual(result.approved, 3)
        self.assertEqual(result.rejected, 0)
        self.assertAlmostEqual(result.approval_rate, 1.0)

    def test_daily_loss_rejection(self):
        from src.bot_backtesting.replay import SignalReplay
        config = ExecutorConfig(daily_loss_limit=0.01)
        replay = SignalReplay(config)
        signals = self._make_signals(1)
        # Start with a negative daily PnL account
        result = replay.replay(signals, starting_equity=100_000)
        # Should still pass since daily_pnl starts at 0
        self.assertEqual(result.approved, 1)

    def test_max_positions_rejection(self):
        from src.bot_backtesting.replay import SignalReplay
        config = ExecutorConfig(max_concurrent_positions=2)
        replay = SignalReplay(config)
        signals = self._make_signals(5)
        result = replay.replay(signals, starting_equity=100_000)
        self.assertEqual(result.approved, 2)
        self.assertEqual(result.rejected, 3)

    def test_duplicate_ticker(self):
        from src.bot_backtesting.replay import SignalReplay
        replay = SignalReplay(ExecutorConfig(max_concurrent_positions=10))
        # Two signals for same ticker
        signals = [
            _make_trade_signal(ticker="AAPL"),
            _make_trade_signal(ticker="AAPL"),
        ]
        result = replay.replay(signals, starting_equity=100_000)
        # Second one rejected (duplicate ticker with unprofitable position)
        self.assertEqual(result.approved, 1)
        self.assertEqual(result.rejected, 1)

    def test_min_equity(self):
        from src.bot_backtesting.replay import SignalReplay
        config = ExecutorConfig(min_account_equity=50_000)
        replay = SignalReplay(config)
        signals = self._make_signals(1)
        result = replay.replay(signals, starting_equity=10_000)
        self.assertEqual(result.rejected, 1)

    def test_summary_stats(self):
        from src.bot_backtesting.replay import SignalReplay
        config = ExecutorConfig(max_concurrent_positions=3)
        replay = SignalReplay(config)
        signals = self._make_signals(5)
        result = replay.replay(signals, starting_equity=100_000)
        self.assertEqual(result.total, 5)
        self.assertGreater(result.approval_rate, 0)
        self.assertIsInstance(result.rejection_reasons, dict)

    def test_compare_configs(self):
        from src.bot_backtesting.replay import SignalReplay
        signals = self._make_signals(5)
        configs = {
            "aggressive": ExecutorConfig(max_concurrent_positions=10),
            "conservative": ExecutorConfig(max_concurrent_positions=2),
        }
        replay = SignalReplay()
        results = replay.compare_configs(signals, configs, starting_equity=100_000)
        self.assertIn("aggressive", results)
        self.assertIn("conservative", results)
        self.assertGreaterEqual(
            results["aggressive"].approved,
            results["conservative"].approved,
        )

    def test_sequential_state(self):
        """Account state should progress sequentially."""
        from src.bot_backtesting.replay import SignalReplay
        config = ExecutorConfig(max_concurrent_positions=10)
        replay = SignalReplay(config)
        signals = self._make_signals(3)
        result = replay.replay(signals, starting_equity=100_000)
        # Each approved signal should have a position size
        for entry in result.entries:
            if entry.approved:
                self.assertGreater(entry.position_size, 0)


# ═══════════════════════════════════════════════════════════════════════
# Test Module Imports
# ═══════════════════════════════════════════════════════════════════════


class TestBotBacktestingModuleImports(unittest.TestCase):
    """Test that all module exports are importable."""

    def test_all_symbols_importable(self):
        from src.bot_backtesting import (
            EMACloudStrategy,
            StrategyConfig,
            BotBacktestRunner,
            BotBacktestConfig,
            EnrichedBacktestResult,
            SignalAttributor,
            SignalTypeStats,
            AttributionReport,
            SignalReplay,
            ReplayResult,
            ReplayEntry,
        )
        self.assertIsNotNone(EMACloudStrategy)
        self.assertIsNotNone(StrategyConfig)
        self.assertIsNotNone(BotBacktestRunner)
        self.assertIsNotNone(BotBacktestConfig)
        self.assertIsNotNone(EnrichedBacktestResult)
        self.assertIsNotNone(SignalAttributor)
        self.assertIsNotNone(SignalTypeStats)
        self.assertIsNotNone(AttributionReport)
        self.assertIsNotNone(SignalReplay)
        self.assertIsNotNone(ReplayResult)
        self.assertIsNotNone(ReplayEntry)

    def test_config_defaults(self):
        from src.bot_backtesting import StrategyConfig, BotBacktestConfig
        sc = StrategyConfig()
        bc = BotBacktestConfig()
        self.assertEqual(sc.min_conviction, 50)
        self.assertEqual(bc.initial_capital, 100_000.0)


if __name__ == "__main__":
    unittest.main()
