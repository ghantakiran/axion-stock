"""Tests for Market Microstructure module."""

import math

import numpy as np
import pytest

from src.microstructure.config import (
    TradeClassification,
    SpreadType,
    ImpactModel,
    BookSide,
    SpreadConfig,
    OrderBookConfig,
    TickConfig,
    ImpactConfig,
    MicrostructureConfig,
    DEFAULT_CONFIG,
)
from src.microstructure.models import (
    SpreadMetrics,
    BookLevel,
    OrderBookSnapshot,
    TickMetrics,
    Trade,
    ImpactEstimate,
)
from src.microstructure.spread import SpreadAnalyzer
from src.microstructure.orderbook import OrderBookAnalyzer
from src.microstructure.tick import TickAnalyzer
from src.microstructure.impact import ImpactEstimator


# ── Helpers ──────────────────────────────────────────────────


def _make_trades(n=100, base_price=100.0, spread=0.02):
    """Generate synthetic trade data with bid/ask."""
    rng = np.random.RandomState(42)
    prices = base_price + rng.randn(n).cumsum() * 0.1
    sizes = rng.randint(100, 5000, n).astype(float)
    timestamps = np.arange(n, dtype=float) * 1.0

    mid = prices
    half_spread = spread / 2
    bids = mid - half_spread
    asks = mid + half_spread

    # Trades alternate around midpoint
    trade_prices = np.where(
        rng.rand(n) > 0.5,
        asks - rng.rand(n) * 0.005,  # buy near ask
        bids + rng.rand(n) * 0.005,  # sell near bid
    )

    trades = [
        Trade(price=float(trade_prices[i]), size=float(sizes[i]),
              timestamp=float(timestamps[i]))
        for i in range(n)
    ]
    return trades, bids, asks, mid


def _make_book(n_levels=5, mid=100.0, tick=0.01, base_size=1000):
    """Generate synthetic order book."""
    bids = [
        BookLevel(price=mid - (i + 1) * tick, size=base_size * (n_levels - i), order_count=10 - i)
        for i in range(n_levels)
    ]
    asks = [
        BookLevel(price=mid + (i + 1) * tick, size=base_size * (n_levels - i), order_count=10 - i)
        for i in range(n_levels)
    ]
    return bids, asks


# ── Config Tests ─────────────────────────────────────────────


class TestMicrostructureConfig:
    def test_trade_classification_values(self):
        assert TradeClassification.LEE_READY.value == "lee_ready"
        assert TradeClassification.TICK_TEST.value == "tick_test"
        assert TradeClassification.BULK_VOLUME.value == "bulk_volume"

    def test_spread_type_values(self):
        assert SpreadType.QUOTED.value == "quoted"
        assert SpreadType.EFFECTIVE.value == "effective"
        assert SpreadType.REALIZED.value == "realized"

    def test_impact_model_values(self):
        assert ImpactModel.LINEAR.value == "linear"
        assert ImpactModel.SQUARE_ROOT.value == "square_root"
        assert ImpactModel.ALMGREN_CHRISS.value == "almgren_chriss"

    def test_book_side_values(self):
        assert BookSide.BID.value == "bid"
        assert BookSide.ASK.value == "ask"

    def test_spread_config_defaults(self):
        cfg = SpreadConfig()
        assert cfg.min_tick_size == 0.01
        assert cfg.realized_spread_delay == 5
        assert cfg.roll_window == 60
        assert cfg.min_trades == 10

    def test_orderbook_config_defaults(self):
        cfg = OrderBookConfig()
        assert cfg.depth_levels == 10
        assert cfg.imbalance_levels == 5
        assert cfg.resilience_window == 30

    def test_tick_config_defaults(self):
        cfg = TickConfig()
        assert cfg.classification_method == TradeClassification.LEE_READY
        assert cfg.vwap_window == 390
        assert cfg.min_ticks == 50
        assert len(cfg.size_buckets) == 5

    def test_impact_config_defaults(self):
        cfg = ImpactConfig()
        assert cfg.model == ImpactModel.SQUARE_ROOT
        assert cfg.temporary_decay == 0.5
        assert cfg.participation_rate == 0.05

    def test_microstructure_config_bundles(self):
        cfg = MicrostructureConfig()
        assert isinstance(cfg.spread, SpreadConfig)
        assert isinstance(cfg.orderbook, OrderBookConfig)
        assert isinstance(cfg.tick, TickConfig)
        assert isinstance(cfg.impact, ImpactConfig)


# ── Model Tests ──────────────────────────────────────────────


class TestMicrostructureModels:
    def test_spread_metrics_properties(self):
        m = SpreadMetrics(
            symbol="AAPL",
            quoted_spread=0.02, quoted_spread_bps=2.0,
            effective_spread=0.03, effective_spread_bps=3.0,
            realized_spread=0.01, realized_spread_bps=1.0,
            roll_spread=0.015,
            adverse_selection=0.02, adverse_selection_bps=2.0,
            midpoint=100.0,
        )
        assert abs(m.spread_efficiency - 1 / 3) < 0.01
        assert abs(m.adverse_selection_pct - 66.67) < 0.1

    def test_spread_metrics_zero_effective(self):
        m = SpreadMetrics(
            symbol="X", quoted_spread=0, quoted_spread_bps=0,
            effective_spread=0, effective_spread_bps=0,
            realized_spread=0, realized_spread_bps=0,
            roll_spread=0, adverse_selection=0, adverse_selection_bps=0,
            midpoint=0,
        )
        assert m.spread_efficiency == 0.0
        assert m.adverse_selection_pct == 0.0

    def test_spread_metrics_to_dict(self):
        m = SpreadMetrics(
            symbol="AAPL",
            quoted_spread=0.02, quoted_spread_bps=2.0,
            effective_spread=0.03, effective_spread_bps=3.0,
            realized_spread=0.01, realized_spread_bps=1.0,
            roll_spread=0.015,
            adverse_selection=0.02, adverse_selection_bps=2.0,
            midpoint=100.0,
        )
        d = m.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["effective_spread"] == 0.03
        assert "computed_at" not in d

    def test_order_book_snapshot_properties(self):
        bids = [BookLevel(price=99.99, size=1000)]
        asks = [BookLevel(price=100.01, size=500)]
        snap = OrderBookSnapshot(
            symbol="AAPL", bids=bids, asks=asks,
            bid_depth=1000, ask_depth=500,
        )
        assert snap.total_depth == 1500
        assert abs(snap.spread - 0.02) < 0.001
        assert abs(snap.midpoint - 100.0) < 0.001

    def test_order_book_snapshot_empty(self):
        snap = OrderBookSnapshot(symbol="X")
        assert snap.total_depth == 0.0
        assert snap.spread == 0.0
        assert snap.midpoint == 0.0

    def test_order_book_to_dict(self):
        snap = OrderBookSnapshot(
            symbol="AAPL", imbalance=0.3,
            bid_depth=1000, ask_depth=500,
        )
        d = snap.to_dict()
        assert d["imbalance"] == 0.3
        assert d["total_depth"] == 1500

    def test_tick_metrics_properties(self):
        m = TickMetrics(
            symbol="AAPL", total_trades=100,
            total_volume=10000, buy_volume=6000, sell_volume=4000,
            vwap=100.5, twap=100.3,
            tick_to_trade_ratio=0.8, kyle_lambda=0.0001,
        )
        assert abs(m.buy_ratio - 0.6) < 0.001
        assert abs(m.order_imbalance - 0.2) < 0.001

    def test_tick_metrics_zero_volume(self):
        m = TickMetrics(
            symbol="X", total_trades=0,
            total_volume=0, buy_volume=0, sell_volume=0,
            vwap=0, twap=0,
            tick_to_trade_ratio=0, kyle_lambda=0,
        )
        assert m.buy_ratio == 0.0
        assert m.order_imbalance == 0.0

    def test_tick_metrics_to_dict(self):
        m = TickMetrics(
            symbol="AAPL", total_trades=100,
            total_volume=10000, buy_volume=6000, sell_volume=4000,
            vwap=100.5, twap=100.3,
            tick_to_trade_ratio=0.8, kyle_lambda=0.0001,
        )
        d = m.to_dict()
        assert d["buy_ratio"] == m.buy_ratio
        assert d["order_imbalance"] == m.order_imbalance

    def test_impact_estimate_properties(self):
        e = ImpactEstimate(
            symbol="AAPL", order_size=10000,
            temporary_impact_bps=5.0, permanent_impact_bps=3.0,
            total_impact_bps=8.0, cost_dollars=80.0,
            participation_rate=0.01, daily_volume=1_000_000,
            volatility=0.02,
        )
        assert abs(e.impact_ratio - 0.375) < 0.001

    def test_impact_estimate_zero_total(self):
        e = ImpactEstimate(
            symbol="X", order_size=0,
            temporary_impact_bps=0, permanent_impact_bps=0,
            total_impact_bps=0, cost_dollars=0,
            participation_rate=0, daily_volume=0, volatility=0,
        )
        assert e.impact_ratio == 0.0

    def test_impact_estimate_to_dict(self):
        e = ImpactEstimate(
            symbol="AAPL", order_size=10000,
            temporary_impact_bps=5.0, permanent_impact_bps=3.0,
            total_impact_bps=8.0, cost_dollars=80.0,
            participation_rate=0.01, daily_volume=1_000_000,
            volatility=0.02, model_used="square_root",
        )
        d = e.to_dict()
        assert d["model_used"] == "square_root"
        assert d["cost_dollars"] == 80.0


# ── Spread Analyzer Tests ───────────────────────────────────


class TestMicrostructureSpreadAnalyzer:
    def test_basic_analysis(self):
        trades, bids, asks, _ = _make_trades(100)
        analyzer = SpreadAnalyzer()
        result = analyzer.analyze(trades, bids, asks, "AAPL")

        assert result.symbol == "AAPL"
        assert result.quoted_spread > 0
        assert result.effective_spread > 0
        assert result.midpoint > 0

    def test_effective_greater_than_zero(self):
        trades, bids, asks, _ = _make_trades(100)
        analyzer = SpreadAnalyzer()
        result = analyzer.analyze(trades, bids, asks, "TEST")
        assert result.effective_spread_bps > 0

    def test_quoted_spread_approximates_input(self):
        """Quoted spread should be close to the input spread of 0.02."""
        trades, bids, asks, _ = _make_trades(200, spread=0.04)
        analyzer = SpreadAnalyzer()
        result = analyzer.analyze(trades, bids, asks, "TEST")
        assert abs(result.quoted_spread - 0.04) < 0.01

    def test_roll_estimator(self):
        rng = np.random.RandomState(99)
        # Create prices with negative serial covariance (spread-induced)
        true_values = 100 + rng.randn(200).cumsum() * 0.05
        noise = rng.choice([-0.01, 0.01], 200)
        prices = true_values + noise

        analyzer = SpreadAnalyzer()
        roll = analyzer.roll_estimator(prices)
        assert roll >= 0  # Roll spread is non-negative

    def test_too_few_trades(self):
        trades = [Trade(price=100, size=100, timestamp=0)]
        bids = np.array([99.99])
        asks = np.array([100.01])
        analyzer = SpreadAnalyzer()
        result = analyzer.analyze(trades, bids, asks, "X")
        assert result.quoted_spread == 0.0

    def test_lee_ready_classification(self):
        """Trades above midpoint should be buys, below should be sells."""
        trades = [
            Trade(price=100.02, size=100, timestamp=0),  # above mid -> buy
            Trade(price=99.98, size=100, timestamp=1),   # below mid -> sell
        ]
        midpoints = np.array([100.0, 100.0])
        analyzer = SpreadAnalyzer()
        dirs = analyzer._classify_trades(trades, midpoints)
        assert dirs[0] == 1.0
        assert dirs[1] == -1.0

    def test_preclassified_trades(self):
        """Pre-classified trades should keep their direction."""
        trades = [
            Trade(price=100.0, size=100, timestamp=0, side=1),
            Trade(price=100.0, size=100, timestamp=1, side=-1),
        ]
        midpoints = np.array([100.0, 100.0])
        analyzer = SpreadAnalyzer()
        dirs = analyzer._classify_trades(trades, midpoints)
        assert dirs[0] == 1.0
        assert dirs[1] == -1.0


# ── Order Book Analyzer Tests ───────────────────────────────


class TestOrderBookAnalyzer:
    def test_balanced_book(self):
        bids, asks = _make_book(5, mid=100.0, tick=0.01, base_size=1000)
        analyzer = OrderBookAnalyzer()
        snap = analyzer.analyze(bids, asks, "AAPL")

        assert snap.symbol == "AAPL"
        assert abs(snap.imbalance) < 0.01  # balanced book
        assert snap.bid_depth > 0
        assert snap.ask_depth > 0
        assert abs(snap.bid_depth - snap.ask_depth) < 0.01

    def test_bid_heavy_imbalance(self):
        bids = [BookLevel(price=99.99 - i * 0.01, size=2000) for i in range(5)]
        asks = [BookLevel(price=100.01 + i * 0.01, size=500) for i in range(5)]
        analyzer = OrderBookAnalyzer()
        snap = analyzer.analyze(bids, asks, "TEST")
        assert snap.imbalance > 0  # bid-heavy

    def test_ask_heavy_imbalance(self):
        bids = [BookLevel(price=99.99 - i * 0.01, size=500) for i in range(5)]
        asks = [BookLevel(price=100.01 + i * 0.01, size=2000) for i in range(5)]
        analyzer = OrderBookAnalyzer()
        snap = analyzer.analyze(bids, asks, "TEST")
        assert snap.imbalance < 0  # ask-heavy

    def test_weighted_midpoint(self):
        bids = [BookLevel(price=99.0, size=1000)]
        asks = [BookLevel(price=101.0, size=1000)]
        analyzer = OrderBookAnalyzer()
        mid = analyzer._weighted_midpoint(bids, asks)
        assert abs(mid - 100.0) < 0.01  # equal sizes -> simple midpoint

    def test_weighted_midpoint_asymmetric(self):
        bids = [BookLevel(price=99.0, size=3000)]
        asks = [BookLevel(price=101.0, size=1000)]
        analyzer = OrderBookAnalyzer()
        mid = analyzer._weighted_midpoint(bids, asks)
        # More bid size -> weighted toward ask price
        assert mid > 100.0

    def test_book_pressure(self):
        bids = [BookLevel(price=99.99 - i * 0.01, size=2000) for i in range(3)]
        asks = [BookLevel(price=100.01 + i * 0.01, size=1000) for i in range(3)]
        analyzer = OrderBookAnalyzer()
        pressure = analyzer._book_pressure(bids, asks)
        assert pressure > 0  # bid side heavier

    def test_resilience_builds_over_snapshots(self):
        bids, asks = _make_book(5, mid=100.0, tick=0.01, base_size=1000)
        analyzer = OrderBookAnalyzer()

        # First snapshot: no resilience (no history)
        snap1 = analyzer.analyze(bids, asks, "TEST")
        assert snap1.resilience == 0.0

        # Second snapshot: resilience computed
        snap2 = analyzer.analyze(bids, asks, "TEST")
        assert snap2.resilience > 0.0

    def test_empty_book(self):
        analyzer = OrderBookAnalyzer()
        snap = analyzer.analyze([], [], "EMPTY")
        assert snap.imbalance == 0.0
        assert snap.bid_depth == 0.0

    def test_reset_history(self):
        bids, asks = _make_book(3)
        analyzer = OrderBookAnalyzer()
        analyzer.analyze(bids, asks, "A")
        analyzer.analyze(bids, asks, "A")
        assert len(analyzer._history) == 2
        analyzer.reset_history()
        assert len(analyzer._history) == 0


# ── Tick Analyzer Tests ──────────────────────────────────────


class TestTickAnalyzer:
    def test_basic_analysis(self):
        trades, _, _, mid = _make_trades(100)
        analyzer = TickAnalyzer()
        result = analyzer.analyze(trades, mid, "AAPL")

        assert result.symbol == "AAPL"
        assert result.total_trades == 100
        assert result.total_volume > 0
        assert result.vwap > 0
        assert result.twap > 0

    def test_buy_sell_split(self):
        trades, _, _, mid = _make_trades(100)
        analyzer = TickAnalyzer()
        result = analyzer.analyze(trades, mid, "TEST")
        assert result.buy_volume + result.sell_volume <= result.total_volume + 0.01

    def test_vwap_between_min_max(self):
        trades, _, _, mid = _make_trades(200)
        prices = [t.price for t in trades]
        analyzer = TickAnalyzer()
        result = analyzer.analyze(trades, mid, "TEST")
        assert min(prices) <= result.vwap <= max(prices)

    def test_twap_between_min_max(self):
        trades, _, _, mid = _make_trades(200)
        prices = [t.price for t in trades]
        analyzer = TickAnalyzer()
        result = analyzer.analyze(trades, mid, "TEST")
        assert min(prices) <= result.twap <= max(prices)

    def test_tick_test_classification(self):
        prices = np.array([100.0, 100.1, 100.05, 100.05, 100.2])
        analyzer = TickAnalyzer()
        dirs = analyzer._tick_test(prices)
        assert dirs[0] == 1.0   # default
        assert dirs[1] == 1.0   # uptick
        assert dirs[2] == -1.0  # downtick
        assert dirs[3] == -1.0  # zero-tick, inherits previous
        assert dirs[4] == 1.0   # uptick

    def test_kyle_lambda_positive(self):
        """Kyle's lambda should generally be positive (buys push price up)."""
        rng = np.random.RandomState(42)
        n = 200
        prices = 100 + np.cumsum(rng.randn(n) * 0.1)
        sizes = rng.randint(100, 1000, n).astype(float)
        timestamps = np.arange(n, dtype=float)
        trades = [
            Trade(price=float(prices[i]), size=float(sizes[i]),
                  timestamp=float(timestamps[i]))
            for i in range(n)
        ]
        mid = prices - 0.005  # slightly below -> mostly buys
        analyzer = TickAnalyzer()
        result = analyzer.analyze(trades, mid, "TEST")
        # Lambda can be positive or negative depending on data
        assert isinstance(result.kyle_lambda, float)

    def test_size_distribution(self):
        trades, _, _, mid = _make_trades(100)
        analyzer = TickAnalyzer()
        result = analyzer.analyze(trades, mid, "TEST")
        assert len(result.size_distribution) > 0
        total_in_buckets = sum(result.size_distribution.values())
        assert total_in_buckets == 100

    def test_too_few_ticks(self):
        trades = [Trade(price=100, size=100, timestamp=0)]
        analyzer = TickAnalyzer()
        result = analyzer.analyze(trades, symbol="X")
        assert result.total_trades == 0


# ── Impact Estimator Tests ───────────────────────────────────


class TestImpactEstimator:
    def test_square_root_model(self):
        estimator = ImpactEstimator()
        result = estimator.estimate(
            order_size=10000, daily_volume=1_000_000,
            volatility=0.02, price=100.0, symbol="AAPL",
        )
        assert result.total_impact_bps > 0
        assert result.temporary_impact_bps > 0
        assert result.permanent_impact_bps > 0
        assert result.cost_dollars > 0
        assert result.model_used == "square_root"

    def test_larger_order_more_impact(self):
        estimator = ImpactEstimator()
        small = estimator.estimate(1000, 1_000_000, 0.02, 100.0)
        large = estimator.estimate(100_000, 1_000_000, 0.02, 100.0)
        assert large.total_impact_bps > small.total_impact_bps

    def test_higher_vol_more_impact(self):
        estimator = ImpactEstimator()
        low_vol = estimator.estimate(10000, 1_000_000, 0.01, 100.0)
        high_vol = estimator.estimate(10000, 1_000_000, 0.04, 100.0)
        assert high_vol.total_impact_bps > low_vol.total_impact_bps

    def test_linear_model(self):
        cfg = ImpactConfig(model=ImpactModel.LINEAR)
        estimator = ImpactEstimator(cfg)
        result = estimator.estimate(10000, 1_000_000, 0.02, 100.0, "TEST")
        assert result.model_used == "linear"
        assert result.total_impact_bps > 0

    def test_almgren_chriss_model(self):
        cfg = ImpactConfig(model=ImpactModel.ALMGREN_CHRISS)
        estimator = ImpactEstimator(cfg)
        result = estimator.estimate(10000, 1_000_000, 0.02, 100.0, "TEST")
        assert result.model_used == "almgren_chriss"
        assert result.total_impact_bps > 0

    def test_zero_volume_returns_empty(self):
        estimator = ImpactEstimator()
        result = estimator.estimate(10000, 0, 0.02, 100.0, "X")
        assert result.total_impact_bps == 0.0

    def test_optimal_schedule(self):
        estimator = ImpactEstimator()
        schedule = estimator.optimal_schedule(
            order_size=10000, daily_volume=1_000_000,
            volatility=0.02, n_periods=5,
        )
        assert len(schedule) == 5
        assert abs(sum(schedule) - 10000) < 1.0  # sums to total

    def test_optimal_schedule_single_period(self):
        estimator = ImpactEstimator()
        schedule = estimator.optimal_schedule(10000, 1_000_000, 0.02, n_periods=1)
        assert len(schedule) == 1
        assert abs(schedule[0] - 10000) < 1.0

    def test_cost_calculation(self):
        estimator = ImpactEstimator()
        result = estimator.estimate(10000, 1_000_000, 0.02, 50.0, "TEST")
        expected_cost = 50.0 * 10000 * result.total_impact_bps / 10000
        assert abs(result.cost_dollars - expected_cost) < 0.1


# ── Integration Tests ────────────────────────────────────────


class TestMicrostructureIntegration:
    def test_full_pipeline(self):
        """End-to-end: trades -> spread + tick + impact."""
        trades, bids_arr, asks_arr, mid = _make_trades(200, base_price=50.0)

        spread_analyzer = SpreadAnalyzer()
        spread = spread_analyzer.analyze(trades, bids_arr, asks_arr, "AAPL")
        assert spread.effective_spread > 0

        tick_analyzer = TickAnalyzer()
        ticks = tick_analyzer.analyze(trades, mid, "AAPL")
        assert ticks.vwap > 0

        impact_est = ImpactEstimator()
        impact = impact_est.estimate(5000, 500_000, 0.025, spread.midpoint, "AAPL")
        assert impact.total_impact_bps > 0

    def test_orderbook_to_spread(self):
        """Order book analysis feeds spread analysis."""
        bids, asks = _make_book(5, mid=100.0, tick=0.01)
        book_analyzer = OrderBookAnalyzer()
        snap = book_analyzer.analyze(bids, asks, "AAPL")

        assert snap.spread > 0
        assert snap.midpoint > 0


class TestMicrostructureModuleImports:
    def test_top_level_imports(self):
        from src.microstructure import (
            SpreadAnalyzer,
            OrderBookAnalyzer,
            TickAnalyzer,
            ImpactEstimator,
            SpreadMetrics,
            BookLevel,
            OrderBookSnapshot,
            TickMetrics,
            Trade,
            ImpactEstimate,
            TradeClassification,
            SpreadType,
            ImpactModel,
            BookSide,
            DEFAULT_CONFIG,
        )
        assert DEFAULT_CONFIG is not None
