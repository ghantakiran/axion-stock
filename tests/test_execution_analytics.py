"""Tests for PRD-58: Execution Analytics."""

import numpy as np
import pytest

from src.execution.tca import (
    CostComponent,
    TCAResult,
    AggregateTCA,
    TCAEngine,
)
from src.execution.scheduling import (
    TimeSlice,
    ExecutionSchedule,
    ScheduleComparison,
    ExecutionScheduler,
)
from src.execution.broker_compare import (
    BrokerStats,
    BrokerComparison,
    TradeRecord,
    BrokerComparator,
)
from src.execution.fill_quality import (
    FillMetrics,
    FillDistribution,
    SymbolFillProfile,
    FillQualityAnalyzer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sample_trades(broker: str, n: int = 20, seed: int = 42) -> list[TradeRecord]:
    rng = np.random.RandomState(seed)
    trades = []
    for i in range(n):
        expected = 100.0 + rng.normal(0, 2)
        slip = rng.normal(0.05, 0.1)
        fill_price = expected + slip
        trades.append(TradeRecord(
            broker=broker,
            symbol="AAPL" if i % 2 == 0 else "MSFT",
            side="buy" if i % 3 != 0 else "sell",
            quantity=100.0,
            filled_quantity=100.0 if rng.random() > 0.1 else 90.0,
            expected_price=round(expected, 4),
            fill_price=round(fill_price, 4),
            commission=round(rng.uniform(0.5, 2.0), 2),
            fill_time_ms=round(rng.uniform(10, 500), 1),
            is_filled=True,
            is_rejected=False,
        ))
    return trades


def _sample_fills(n: int = 15, seed: int = 42) -> list[FillMetrics]:
    rng = np.random.RandomState(seed)
    analyzer = FillQualityAnalyzer()
    fills = []
    for i in range(n):
        mid = 150.0 + rng.normal(0, 3)
        spread = rng.uniform(0.02, 0.10)
        bid = mid - spread / 2
        ask = mid + spread / 2
        side = "buy" if i % 2 == 0 else "sell"
        fill = mid + rng.normal(0, spread * 0.5) * (1 if side == "buy" else -1)
        qty = 100.0
        filled = qty if rng.random() > 0.15 else qty * 0.8
        post_mid = mid + rng.normal(0, 0.05)
        fm = analyzer.analyze_fill(
            symbol="AAPL" if i % 3 != 0 else "GOOGL",
            side=side,
            quantity=qty,
            filled_quantity=filled,
            fill_price=round(fill, 4),
            bid=round(bid, 4),
            ask=round(ask, 4),
            post_trade_mid=round(post_mid, 4),
        )
        fills.append(fm)
    return fills


# ---------------------------------------------------------------------------
# TCAResult dataclass
# ---------------------------------------------------------------------------
class TestTCAResult:
    def test_components(self):
        r = TCAResult(
            total_cost_bps=10.0,
            spread_cost_bps=3.0,
            timing_cost_bps=2.0,
            impact_cost_bps=4.0,
            opportunity_cost_bps=0.5,
            commission_bps=0.5,
        )
        comps = r.components
        assert len(comps) == 5
        assert comps[0].name == "Spread"

    def test_vs_vwap_bps(self):
        r = TCAResult(
            side="buy",
            execution_price=101.0,
            benchmark_vwap=100.0,
        )
        assert r.vs_vwap_bps == pytest.approx(100.0, abs=1.0)

    def test_implementation_shortfall_pct(self):
        r = TCAResult(total_cost_bps=50.0)
        assert r.implementation_shortfall_pct == pytest.approx(0.005)


class TestAggregateTCA:
    def test_cost_per_million(self):
        agg = AggregateTCA(
            total_notional=2_000_000,
            total_cost_dollar=1_000,
        )
        assert agg.cost_per_million == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# TCAEngine
# ---------------------------------------------------------------------------
class TestTCAEngine:
    def test_analyze_buy_trade(self):
        engine = TCAEngine()
        result = engine.analyze_trade(
            symbol="AAPL",
            side="buy",
            quantity=1000,
            decision_price=150.00,
            arrival_price=150.10,
            execution_price=150.20,
            filled_quantity=1000,
            commission=5.0,
        )
        assert result.total_cost_bps > 0
        assert result.timing_cost_bps > 0  # Price went up before arrival
        assert result.impact_cost_bps > 0  # Fill price > arrival
        assert result.fill_rate == 1.0
        assert result.symbol == "AAPL"

    def test_analyze_sell_trade(self):
        engine = TCAEngine()
        result = engine.analyze_trade(
            symbol="MSFT",
            side="sell",
            quantity=500,
            decision_price=380.00,
            arrival_price=379.90,
            execution_price=379.80,
            filled_quantity=500,
        )
        # For sells, price going down is bad (timing cost positive)
        assert result.fill_rate == 1.0

    def test_partial_fill(self):
        engine = TCAEngine()
        result = engine.analyze_trade(
            symbol="GOOGL",
            side="buy",
            quantity=1000,
            decision_price=140.00,
            arrival_price=140.05,
            execution_price=140.10,
            filled_quantity=800,
        )
        assert result.fill_rate == pytest.approx(0.8)
        assert result.opportunity_cost_bps > 0

    def test_zero_decision_price(self):
        engine = TCAEngine()
        result = engine.analyze_trade(
            symbol="X", side="buy", quantity=100,
            decision_price=0, arrival_price=10, execution_price=10,
        )
        assert result.total_cost_bps == 0.0

    def test_aggregate(self):
        engine = TCAEngine()
        results = []
        for i in range(5):
            r = engine.analyze_trade(
                symbol="AAPL", side="buy", quantity=100,
                decision_price=150 + i * 0.1,
                arrival_price=150 + i * 0.1 + 0.05,
                execution_price=150 + i * 0.1 + 0.1,
                filled_quantity=100,
                commission=1.0,
            )
            results.append(r)
        agg = engine.aggregate(results)
        assert agg.n_trades == 5
        assert agg.total_notional > 0
        assert agg.avg_cost_bps > 0

    def test_aggregate_empty(self):
        engine = TCAEngine()
        agg = engine.aggregate([])
        assert agg.n_trades == 0

    def test_estimate_impact(self):
        engine = TCAEngine()
        impact = engine.estimate_impact(
            quantity=10000, price=150.0, adv=1_000_000, volatility=0.02
        )
        assert impact > 0

    def test_estimate_impact_zero_adv(self):
        engine = TCAEngine()
        assert engine.estimate_impact(1000, 150.0, 0) == 0.0

    def test_with_spread(self):
        engine = TCAEngine()
        result = engine.analyze_trade(
            symbol="AAPL", side="buy", quantity=100,
            decision_price=150.00, arrival_price=150.00,
            execution_price=150.05, filled_quantity=100,
            spread=0.10,
        )
        assert result.spread_cost_bps > 0


# ---------------------------------------------------------------------------
# TimeSlice / ExecutionSchedule
# ---------------------------------------------------------------------------
class TestTimeSlice:
    def test_duration(self):
        ts = TimeSlice(start_minute=0, end_minute=30)
        assert ts.duration_minutes == 30


class TestExecutionSchedule:
    def test_avg_slice_quantity(self):
        sched = ExecutionSchedule(total_quantity=1000, n_slices=10)
        assert sched.avg_slice_quantity == 100.0

    def test_avg_slice_zero_slices(self):
        sched = ExecutionSchedule(total_quantity=1000, n_slices=0)
        assert sched.avg_slice_quantity == 0.0


# ---------------------------------------------------------------------------
# ExecutionScheduler
# ---------------------------------------------------------------------------
class TestExecutionScheduler:
    def test_twap(self):
        scheduler = ExecutionScheduler()
        sched = scheduler.twap("AAPL", 10000, n_slices=10)
        assert sched.n_slices == 10
        assert sched.strategy == "twap"
        assert len(sched.slices) == 10
        # Each slice should have equal quantity
        qtys = [s.quantity for s in sched.slices]
        assert max(qtys) == pytest.approx(min(qtys), abs=0.1)

    def test_twap_zero_quantity(self):
        scheduler = ExecutionScheduler()
        sched = scheduler.twap("AAPL", 0)
        assert sched.n_slices == 0

    def test_vwap(self):
        scheduler = ExecutionScheduler()
        sched = scheduler.vwap("AAPL", 10000)
        assert sched.strategy == "vwap"
        assert len(sched.slices) == 13  # Default profile length
        # First and last slices should be larger (U-shape)
        first = sched.slices[0].pct_of_total
        middle = sched.slices[6].pct_of_total
        assert first > middle

    def test_vwap_custom_profile(self):
        scheduler = ExecutionScheduler()
        profile = [0.5, 0.3, 0.2]
        sched = scheduler.vwap("AAPL", 1000, volume_profile=profile)
        assert sched.n_slices == 3
        assert sched.slices[0].quantity > sched.slices[2].quantity

    def test_implementation_shortfall(self):
        scheduler = ExecutionScheduler()
        sched = scheduler.implementation_shortfall(
            "AAPL", 10000, urgency=0.8, n_slices=10
        )
        assert sched.strategy == "is"
        assert sched.urgency == 0.8
        # Front-loaded: first slice > last slice
        assert sched.slices[0].quantity > sched.slices[-1].quantity

    def test_is_low_urgency(self):
        scheduler = ExecutionScheduler()
        low = scheduler.implementation_shortfall("X", 1000, urgency=0.1, n_slices=5)
        high = scheduler.implementation_shortfall("X", 1000, urgency=0.9, n_slices=5)
        # High urgency should have more front-loading
        assert high.slices[0].pct_of_total > low.slices[0].pct_of_total

    def test_compare_strategies(self):
        scheduler = ExecutionScheduler()
        comp = scheduler.compare_strategies("AAPL", 10000)
        assert comp.recommended in ("twap", "vwap", "is")
        assert comp.reason != ""

    def test_compare_high_urgency(self):
        scheduler = ExecutionScheduler()
        comp = scheduler.compare_strategies("AAPL", 10000, urgency=0.9)
        assert comp.recommended == "is"

    def test_compare_high_volatility(self):
        scheduler = ExecutionScheduler()
        comp = scheduler.compare_strategies("AAPL", 10000, volatility=0.05, urgency=0.3)
        assert comp.recommended == "is"


# ---------------------------------------------------------------------------
# BrokerStats / BrokerComparison
# ---------------------------------------------------------------------------
class TestBrokerStats:
    def test_total_cost_dollar(self):
        bs = BrokerStats(avg_total_cost_bps=10, total_notional=1_000_000)
        assert bs.total_cost_dollar == pytest.approx(1000.0)

    def test_is_top_performer(self):
        assert BrokerStats(score=85).is_top_performer is True
        assert BrokerStats(score=70).is_top_performer is False


class TestBrokerComparison:
    def test_n_brokers(self):
        bc = BrokerComparison(brokers=[BrokerStats(), BrokerStats()])
        assert bc.n_brokers == 2

    def test_avg_score(self):
        bc = BrokerComparison(brokers=[
            BrokerStats(score=80), BrokerStats(score=60),
        ])
        assert bc.avg_score == pytest.approx(70.0)


# ---------------------------------------------------------------------------
# BrokerComparator
# ---------------------------------------------------------------------------
class TestBrokerComparator:
    def test_compute_broker_stats(self):
        trades = _sample_trades("alpha")
        comp = BrokerComparator()
        stats = comp.compute_broker_stats(trades, "alpha")
        assert stats.broker == "alpha"
        assert stats.n_orders == 20
        assert stats.fill_rate > 0
        assert stats.score > 0

    def test_empty_trades(self):
        comp = BrokerComparator()
        stats = comp.compute_broker_stats([], "empty")
        assert stats.n_orders == 0
        assert stats.score == 0.0

    def test_compare_brokers(self):
        comp = BrokerComparator()
        records = {
            "alpha": _sample_trades("alpha", seed=42),
            "beta": _sample_trades("beta", seed=99),
        }
        result = comp.compare(records)
        assert result.n_brokers == 2
        assert result.best_broker != ""
        assert result.best_score >= result.worst_score

    def test_compare_empty(self):
        comp = BrokerComparator()
        result = comp.compare({})
        assert result.n_brokers == 0

    def test_price_improvement_tracked(self):
        # Create trades where fill is better than expected
        trades = [
            TradeRecord(
                broker="good", symbol="X", side="buy", quantity=100,
                filled_quantity=100, expected_price=100.0,
                fill_price=99.90, commission=0.0, fill_time_ms=50,
                is_filled=True,
            ),
        ]
        comp = BrokerComparator()
        stats = comp.compute_broker_stats(trades, "good")
        assert stats.price_improvement_rate == 1.0
        assert stats.avg_price_improvement_bps > 0


# ---------------------------------------------------------------------------
# FillMetrics
# ---------------------------------------------------------------------------
class TestFillMetrics:
    def test_has_price_improvement(self):
        fm = FillMetrics(price_improvement_bps=5.0)
        assert fm.has_price_improvement is True
        fm2 = FillMetrics(price_improvement_bps=-2.0)
        assert fm2.has_price_improvement is False

    def test_is_fully_filled(self):
        fm = FillMetrics(fill_rate=1.0)
        assert fm.is_fully_filled is True
        fm2 = FillMetrics(fill_rate=0.8)
        assert fm2.is_fully_filled is False


class TestFillDistribution:
    def test_quality_score(self):
        fd = FillDistribution(
            avg_fill_rate=0.95,
            avg_effective_spread_bps=5.0,
            pct_with_improvement=0.4,
        )
        assert 0 < fd.quality_score <= 100


# ---------------------------------------------------------------------------
# FillQualityAnalyzer
# ---------------------------------------------------------------------------
class TestFillQualityAnalyzer:
    def test_analyze_buy_fill(self):
        analyzer = FillQualityAnalyzer()
        fm = analyzer.analyze_fill(
            symbol="AAPL", side="buy", quantity=100,
            filled_quantity=100, fill_price=150.05,
            bid=149.98, ask=150.08,
        )
        assert fm.fill_rate == 1.0
        assert fm.effective_spread_bps > 0
        assert fm.midpoint == pytest.approx(150.03, abs=0.01)

    def test_analyze_sell_fill(self):
        analyzer = FillQualityAnalyzer()
        fm = analyzer.analyze_fill(
            symbol="MSFT", side="sell", quantity=200,
            filled_quantity=200, fill_price=380.10,
            bid=380.05, ask=380.15,
        )
        assert fm.fill_rate == 1.0

    def test_analyze_with_post_trade(self):
        analyzer = FillQualityAnalyzer()
        fm = analyzer.analyze_fill(
            symbol="AAPL", side="buy", quantity=100,
            filled_quantity=100, fill_price=150.05,
            bid=149.98, ask=150.08,
            post_trade_mid=150.10,
        )
        assert fm.adverse_selection_bps != 0

    def test_analyze_zero_prices(self):
        analyzer = FillQualityAnalyzer()
        fm = analyzer.analyze_fill(
            symbol="X", side="buy", quantity=100,
            filled_quantity=100, fill_price=0,
            bid=0, ask=0,
        )
        assert fm.effective_spread_bps == 0.0

    def test_compute_distribution(self):
        fills = _sample_fills()
        analyzer = FillQualityAnalyzer()
        dist = analyzer.compute_distribution(fills)
        assert dist.n_fills == 15
        assert dist.avg_fill_rate > 0
        assert dist.spread_p50_bps >= 0

    def test_compute_distribution_empty(self):
        analyzer = FillQualityAnalyzer()
        dist = analyzer.compute_distribution([])
        assert dist.n_fills == 0

    def test_profile_by_symbol(self):
        fills = _sample_fills()
        analyzer = FillQualityAnalyzer()
        profiles = analyzer.profile_by_symbol(fills)
        assert len(profiles) == 2  # AAPL and GOOGL
        for p in profiles:
            assert p.symbol in ("AAPL", "GOOGL")
            assert p.n_orders > 0

    def test_profile_empty(self):
        analyzer = FillQualityAnalyzer()
        assert analyzer.profile_by_symbol([]) == []
