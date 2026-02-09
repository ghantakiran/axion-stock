"""Tests for Live Signal-to-Trade Pipeline (PRD-149)."""

import json
import pytest

from src.trade_pipeline.bridge import (
    SignalType, OrderSide, OrderType, PipelineOrder, SignalBridge,
)
from src.trade_pipeline.executor import (
    PipelineStatus, PipelineConfig, PipelineResult, PipelineExecutor,
)
from src.trade_pipeline.reconciler import (
    ReconciliationRecord, SlippageStats, ExecutionReconciler,
)
from src.trade_pipeline.position_store import (
    TrackedPosition, PositionStore,
)


# ── Helpers ──────────────────────────────────────────────────────────


class _MockRecommendation:
    """Mock signal_fusion Recommendation for testing."""

    def __init__(self, symbol="AAPL", action="BUY", position_size_pct=5.0,
                 stop_loss_pct=3.0, take_profit_pct=6.0, time_horizon="swing",
                 risk_level="medium", reasoning="test"):
        self.symbol = symbol
        self.action = action
        self.position_size_pct = position_size_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.time_horizon = time_horizon
        self.risk_level = risk_level
        self.reasoning = reasoning
        self.fused_signal = _MockFusedSignal()

    def to_dict(self):
        return {"symbol": self.symbol, "action": self.action,
                "position_size_pct": self.position_size_pct}


class _MockFusedSignal:
    """Mock FusedSignal."""

    def __init__(self, confidence=0.75, composite_score=45.0):
        self.confidence = confidence
        self.composite_score = composite_score


class _MockSocialSignal:
    """Mock SocialTradingSignal."""

    class _Action:
        def __init__(self, value):
            self.value = value

    def __init__(self, symbol="TSLA", action="buy", confidence=70.0,
                 final_score=65.0, reasons=None):
        self.symbol = symbol
        self.action = self._Action(action)
        self.confidence = confidence
        self.final_score = final_score
        self.reasons = reasons or ["volume surge", "positive sentiment"]


class _MockTradeSignal:
    """Mock EMA TradeSignal."""

    class _SigType:
        def __init__(self, value):
            self.value = value

    def __init__(self, ticker="NVDA", direction="long", conviction=75,
                 entry_price=500.0, stop_loss=485.0, target_price=530.0,
                 timeframe="1d", signal_type="cloud_cross_bullish"):
        self.ticker = ticker
        self.direction = direction
        self.conviction = conviction
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.target_price = target_price
        self.timeframe = timeframe
        self.signal_type = self._SigType(signal_type)

    def to_dict(self):
        return {"ticker": self.ticker, "direction": self.direction,
                "conviction": self.conviction}


# ── PipelineOrder ────────────────────────────────────────────────────


class TestPipelineOrder:

    def test_defaults(self):
        o = PipelineOrder()
        assert o.side == OrderSide.BUY
        assert o.order_type == OrderType.MARKET
        assert len(o.order_id) == 12

    def test_to_broker_order(self):
        o = PipelineOrder(symbol="AAPL", side=OrderSide.BUY, qty=50,
                          order_type=OrderType.LIMIT, limit_price=185.0,
                          asset_type="stock")
        broker_dict = o.to_broker_order()
        assert broker_dict["symbol"] == "AAPL"
        assert broker_dict["side"] == "buy"
        assert broker_dict["qty"] == 50
        assert broker_dict["limit_price"] == 185.0
        assert broker_dict["order_type"] == "limit"

    def test_to_dict_roundtrip(self):
        o = PipelineOrder(symbol="GOOG", side=OrderSide.SELL, qty=10,
                          confidence=0.85, signal_type=SignalType.FUSION)
        d = o.to_dict()
        assert d["symbol"] == "GOOG"
        assert d["side"] == "sell"
        assert d["signal_type"] == "fusion"
        assert d["confidence"] == 0.85

    def test_stop_price_in_broker_order(self):
        o = PipelineOrder(symbol="SPY", side=OrderSide.SELL, qty=20,
                          order_type=OrderType.STOP, stop_price=450.0)
        d = o.to_broker_order()
        assert d["stop_price"] == 450.0
        assert "limit_price" not in d


# ── SignalBridge ─────────────────────────────────────────────────────


class TestSignalBridge:

    def test_from_recommendation_buy(self):
        bridge = SignalBridge(account_equity=100_000)
        rec = _MockRecommendation(action="BUY")
        order = bridge.from_recommendation(rec)
        assert order is not None
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.signal_type == SignalType.FUSION
        assert order.order_type == OrderType.LIMIT

    def test_from_recommendation_strong_buy(self):
        bridge = SignalBridge(account_equity=100_000)
        rec = _MockRecommendation(action="STRONG_BUY")
        order = bridge.from_recommendation(rec)
        assert order is not None
        assert order.order_type == OrderType.MARKET

    def test_from_recommendation_sell(self):
        bridge = SignalBridge()
        rec = _MockRecommendation(action="SELL")
        order = bridge.from_recommendation(rec)
        assert order is not None
        assert order.side == OrderSide.SELL

    def test_from_recommendation_hold_returns_none(self):
        bridge = SignalBridge()
        rec = _MockRecommendation(action="HOLD")
        order = bridge.from_recommendation(rec)
        assert order is None

    def test_from_social_signal_buy(self):
        bridge = SignalBridge(account_equity=100_000)
        sig = _MockSocialSignal(action="buy", confidence=70.0)
        order = bridge.from_social_signal(sig)
        assert order is not None
        assert order.symbol == "TSLA"
        assert order.side == OrderSide.BUY
        assert order.signal_type == SignalType.SOCIAL
        assert 0 < order.confidence <= 1.0

    def test_from_social_signal_strong_sell(self):
        bridge = SignalBridge()
        sig = _MockSocialSignal(action="strong_sell", confidence=85.0)
        order = bridge.from_social_signal(sig)
        assert order is not None
        assert order.side == OrderSide.SELL
        assert order.order_type == OrderType.MARKET

    def test_from_social_signal_watch_returns_none(self):
        bridge = SignalBridge()
        sig = _MockSocialSignal(action="watch")
        order = bridge.from_social_signal(sig)
        assert order is None

    def test_from_trade_signal_long(self):
        bridge = SignalBridge(account_equity=100_000)
        sig = _MockTradeSignal(direction="long", conviction=75)
        order = bridge.from_trade_signal(sig, current_price=500.0)
        assert order is not None
        assert order.symbol == "NVDA"
        assert order.side == OrderSide.BUY
        assert order.signal_type == SignalType.EMA_CLOUD
        assert order.qty > 0

    def test_from_trade_signal_short(self):
        bridge = SignalBridge()
        sig = _MockTradeSignal(direction="short", conviction=65)
        order = bridge.from_trade_signal(sig)
        assert order is not None
        assert order.side == OrderSide.SELL

    def test_from_trade_signal_low_conviction_returns_none(self):
        bridge = SignalBridge()
        sig = _MockTradeSignal(conviction=20)
        order = bridge.from_trade_signal(sig)
        assert order is None

    def test_from_trade_signal_high_conviction_market_order(self):
        bridge = SignalBridge()
        sig = _MockTradeSignal(conviction=80)
        order = bridge.from_trade_signal(sig)
        assert order is not None
        assert order.order_type == OrderType.MARKET

    def test_from_dict(self):
        bridge = SignalBridge()
        data = {"symbol": "META", "side": "buy", "qty": 25,
                "order_type": "limit", "limit_price": 320.0,
                "confidence": 0.6}
        order = bridge.from_dict(data)
        assert order.symbol == "META"
        assert order.side == OrderSide.BUY
        assert order.qty == 25
        assert order.signal_type == SignalType.MANUAL

    def test_equity_setter(self):
        bridge = SignalBridge(account_equity=50_000)
        assert bridge.account_equity == 50_000
        bridge.account_equity = 75_000
        assert bridge.account_equity == 75_000

    def test_pct_to_shares(self):
        bridge = SignalBridge(account_equity=100_000)
        shares = bridge._pct_to_shares(5.0, 200.0)
        assert shares == 25  # 5% of 100K = 5K / 200 = 25


# ── PipelineConfig ───────────────────────────────────────────────────


class TestPipelineConfig:

    def test_defaults(self):
        cfg = PipelineConfig()
        assert cfg.min_confidence == 0.3
        assert cfg.max_positions == 20
        assert cfg.paper_mode is True

    def test_custom_config(self):
        cfg = PipelineConfig(max_positions=5, paper_mode=False,
                             blocked_symbols=["GME", "AMC"])
        assert cfg.max_positions == 5
        assert cfg.paper_mode is False
        assert "GME" in cfg.blocked_symbols


# ── PipelineExecutor ─────────────────────────────────────────────────


class TestPipelineExecutor:

    def _make_order(self, **kwargs):
        defaults = dict(symbol="AAPL", side=OrderSide.BUY,
                        order_type=OrderType.MARKET, qty=50,
                        confidence=0.7, position_size_pct=5.0)
        defaults.update(kwargs)
        return PipelineOrder(**defaults)

    def test_process_basic_paper_mode(self):
        executor = PipelineExecutor()
        order = self._make_order()
        result = executor.process(order)
        assert result.status == PipelineStatus.EXECUTED
        assert result.broker_name == "paper"
        assert result.fill_qty == 50
        assert len(result.stages_passed) == 5

    def test_process_reject_missing_symbol(self):
        executor = PipelineExecutor()
        order = self._make_order(symbol="")
        result = executor.process(order)
        assert result.status == PipelineStatus.REJECTED
        assert "Missing symbol" in result.rejection_reason

    def test_process_reject_zero_qty(self):
        executor = PipelineExecutor()
        order = self._make_order(qty=0)
        result = executor.process(order)
        assert result.status == PipelineStatus.REJECTED
        assert "quantity" in result.rejection_reason.lower()

    def test_process_reject_low_confidence(self):
        executor = PipelineExecutor(PipelineConfig(min_confidence=0.5))
        order = self._make_order(confidence=0.2)
        result = executor.process(order)
        assert result.status == PipelineStatus.REJECTED
        assert "Confidence" in result.rejection_reason

    def test_process_reject_blocked_symbol(self):
        cfg = PipelineConfig(blocked_symbols=["GME"])
        executor = PipelineExecutor(cfg)
        order = self._make_order(symbol="GME")
        result = executor.process(order)
        assert result.status == PipelineStatus.REJECTED
        assert "blocked" in result.rejection_reason

    def test_process_reject_max_positions(self):
        cfg = PipelineConfig(max_positions=2)
        executor = PipelineExecutor(cfg)
        # Fill up positions
        executor.set_positions({"AAPL": 50, "GOOG": 30})
        order = self._make_order(symbol="TSLA")
        result = executor.process(order)
        assert result.status == PipelineStatus.REJECTED
        assert "Max positions" in result.rejection_reason

    def test_process_reject_position_size(self):
        cfg = PipelineConfig(max_position_pct=5.0)
        executor = PipelineExecutor(cfg)
        order = self._make_order(position_size_pct=10.0)
        result = executor.process(order)
        assert result.status == PipelineStatus.REJECTED
        assert "Position size" in result.rejection_reason

    def test_process_reject_daily_loss_limit(self):
        executor = PipelineExecutor(PipelineConfig(daily_loss_limit_pct=5.0),
                                    account_equity=100_000)
        executor.record_pnl(-5500.0)  # 5.5% loss
        order = self._make_order()
        result = executor.process(order)
        assert result.status == PipelineStatus.REJECTED
        assert "Daily loss" in result.rejection_reason

    def test_process_reject_limit_order_no_price(self):
        executor = PipelineExecutor()
        order = self._make_order(order_type=OrderType.LIMIT, limit_price=None)
        result = executor.process(order)
        assert result.status == PipelineStatus.REJECTED
        assert "limit_price" in result.rejection_reason

    def test_process_tracks_positions(self):
        executor = PipelineExecutor()
        order = self._make_order(symbol="AAPL", qty=100)
        executor.process(order)
        assert executor.open_position_count == 1
        # Sell to close
        sell = self._make_order(symbol="AAPL", side=OrderSide.SELL, qty=100)
        executor.process(sell)
        assert executor.open_position_count == 0

    def test_process_batch(self):
        executor = PipelineExecutor()
        orders = [
            self._make_order(symbol="AAPL"),
            self._make_order(symbol="GOOG"),
            self._make_order(symbol="TSLA"),
        ]
        results = executor.process_batch(orders)
        assert len(results) == 3
        assert all(r.status == PipelineStatus.EXECUTED for r in results)

    def test_get_execution_stats(self):
        executor = PipelineExecutor()
        executor.process(self._make_order(symbol="AAPL"))
        executor.process(self._make_order(symbol="", qty=0))  # will be rejected
        stats = executor.get_execution_stats()
        assert stats["total_processed"] == 2
        assert stats["executed"] == 1
        assert stats["rejected"] == 1

    def test_get_rejection_summary(self):
        cfg = PipelineConfig(blocked_symbols=["GME"])
        executor = PipelineExecutor(cfg)
        executor.process(self._make_order(symbol="GME"))
        executor.process(self._make_order(symbol="GME"))
        summary = executor.get_rejection_summary()
        assert any("blocked" in k for k in summary)

    def test_live_mode_routes(self):
        cfg = PipelineConfig(paper_mode=False)
        executor = PipelineExecutor(cfg)
        order = self._make_order()
        result = executor.process(order)
        assert result.status == PipelineStatus.ROUTED
        assert result.broker_name == "pending"

    def test_reset_daily(self):
        executor = PipelineExecutor()
        executor.record_pnl(-1000)
        executor.reset_daily()
        # Should now pass the daily loss check
        order = self._make_order()
        result = executor.process(order)
        assert result.status == PipelineStatus.EXECUTED

    def test_equity_property(self):
        executor = PipelineExecutor(account_equity=200_000)
        assert executor.account_equity == 200_000
        executor.account_equity = 150_000
        assert executor.account_equity == 150_000

    def test_result_to_dict(self):
        executor = PipelineExecutor()
        result = executor.process(self._make_order())
        d = result.to_dict()
        assert d["status"] == "executed"
        assert d["symbol"] == "AAPL"
        assert d["broker_name"] == "paper"


# ── ReconciliationRecord ────────────────────────────────────────────


class TestReconciliationRecord:

    def test_defaults(self):
        rec = ReconciliationRecord()
        assert rec.slippage_pct == 0.0
        assert rec.fill_ratio == 1.0

    def test_to_dict(self):
        rec = ReconciliationRecord(order_id="abc", symbol="AAPL",
                                   expected_price=185.0, actual_price=185.30,
                                   slippage_pct=0.162)
        d = rec.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["slippage_pct"] == 0.162


# ── ExecutionReconciler ──────────────────────────────────────────────


class TestExecutionReconciler:

    def test_reconcile_basic(self):
        reconciler = ExecutionReconciler()
        record = reconciler.reconcile(
            order_id="ord1", symbol="AAPL",
            expected_price=185.0, actual_price=185.50,
            expected_qty=100, actual_qty=100,
            broker_name="alpaca", latency_ms=42.0,
        )
        assert record.slippage_pct == pytest.approx(0.2703, rel=0.01)
        assert record.fill_ratio == 1.0

    def test_reconcile_partial_fill(self):
        reconciler = ExecutionReconciler()
        record = reconciler.reconcile(
            order_id="ord2", symbol="GOOG",
            expected_price=150.0, actual_price=150.0,
            expected_qty=100, actual_qty=60,
        )
        assert record.fill_ratio == 0.6

    def test_reconcile_negative_slippage(self):
        reconciler = ExecutionReconciler()
        record = reconciler.reconcile(
            order_id="ord3", symbol="TSLA",
            expected_price=200.0, actual_price=199.0,
            expected_qty=50, actual_qty=50,
        )
        assert record.slippage_pct < 0  # Better than expected

    def test_get_stats(self):
        reconciler = ExecutionReconciler()
        reconciler.reconcile("o1", "AAPL", 100.0, 100.5, 10, 10, "alpaca", 30)
        reconciler.reconcile("o2", "GOOG", 150.0, 150.3, 20, 20, "schwab", 50)
        reconciler.reconcile("o3", "TSLA", 200.0, 199.0, 15, 10, "alpaca", 40)
        stats = reconciler.get_stats()
        assert stats.total_records == 3
        assert stats.avg_slippage_pct != 0.0
        assert "alpaca" in stats.by_broker
        assert "schwab" in stats.by_broker

    def test_get_stats_empty(self):
        reconciler = ExecutionReconciler()
        stats = reconciler.get_stats()
        assert stats.total_records == 0
        assert stats.avg_slippage_pct == 0.0

    def test_get_records_by_symbol(self):
        reconciler = ExecutionReconciler()
        reconciler.reconcile("o1", "AAPL", 100, 101, 10, 10)
        reconciler.reconcile("o2", "GOOG", 150, 151, 20, 20)
        records = reconciler.get_records_by_symbol("AAPL")
        assert len(records) == 1
        assert records[0].symbol == "AAPL"

    def test_get_records_by_broker(self):
        reconciler = ExecutionReconciler()
        reconciler.reconcile("o1", "AAPL", 100, 101, 10, 10, "alpaca")
        reconciler.reconcile("o2", "GOOG", 150, 151, 20, 20, "schwab")
        records = reconciler.get_records_by_broker("alpaca")
        assert len(records) == 1

    def test_clear(self):
        reconciler = ExecutionReconciler()
        reconciler.reconcile("o1", "AAPL", 100, 101, 10, 10)
        reconciler.clear()
        assert len(reconciler.records) == 0

    def test_stats_to_dict(self):
        stats = SlippageStats(total_records=5, avg_slippage_pct=0.15,
                              by_broker={"alpaca": 0.12})
        d = stats.to_dict()
        assert d["total_records"] == 5
        assert d["by_broker"]["alpaca"] == 0.12


# ── TrackedPosition ──────────────────────────────────────────────────


class TestTrackedPosition:

    def test_unrealized_pnl_long(self):
        pos = TrackedPosition(symbol="AAPL", qty=100, avg_entry_price=180.0,
                              current_price=190.0, side="long")
        assert pos.unrealized_pnl == 1000.0
        assert pos.unrealized_pnl_pct == pytest.approx(5.556, rel=0.01)

    def test_unrealized_pnl_short(self):
        pos = TrackedPosition(symbol="TSLA", qty=50, avg_entry_price=250.0,
                              current_price=240.0, side="short")
        assert pos.unrealized_pnl == 500.0  # short profit

    def test_market_value_and_cost(self):
        pos = TrackedPosition(symbol="GOOG", qty=20, avg_entry_price=100.0,
                              current_price=110.0)
        assert pos.market_value == 2200.0
        assert pos.cost_basis == 2000.0

    def test_hit_stop_loss_long(self):
        pos = TrackedPosition(symbol="X", qty=10, avg_entry_price=100.0,
                              current_price=90.0, side="long",
                              stop_loss_price=95.0)
        assert pos.hit_stop_loss is True

    def test_hit_stop_loss_not_triggered(self):
        pos = TrackedPosition(symbol="X", qty=10, avg_entry_price=100.0,
                              current_price=97.0, side="long",
                              stop_loss_price=95.0)
        assert pos.hit_stop_loss is False

    def test_hit_target_long(self):
        pos = TrackedPosition(symbol="X", qty=10, avg_entry_price=100.0,
                              current_price=115.0, side="long",
                              target_price=110.0)
        assert pos.hit_target is True

    def test_to_dict_roundtrip(self):
        pos = TrackedPosition(symbol="AAPL", qty=50, avg_entry_price=185.0,
                              current_price=190.0, side="long",
                              signal_type="fusion")
        d = pos.to_dict()
        pos2 = TrackedPosition.from_dict(d)
        assert pos2.symbol == pos.symbol
        assert pos2.qty == pos.qty
        assert pos2.avg_entry_price == pos.avg_entry_price


# ── PositionStore ────────────────────────────────────────────────────


class TestPositionStore:

    def test_open_position(self):
        store = PositionStore()
        pos = store.open_position("AAPL", 100, 185.0, "long", "fusion", "ord1")
        assert pos.symbol == "AAPL"
        assert pos.qty == 100
        assert store.position_count == 1

    def test_open_position_averaging(self):
        store = PositionStore()
        store.open_position("AAPL", 100, 180.0)
        store.open_position("AAPL", 100, 190.0)
        pos = store.get("AAPL")
        assert pos.qty == 200
        assert pos.avg_entry_price == 185.0

    def test_close_position(self):
        store = PositionStore()
        store.open_position("AAPL", 100, 180.0, "long")
        closed = store.close_position("AAPL", exit_price=190.0)
        assert closed is not None
        assert closed["realized_pnl"] == 1000.0
        assert store.position_count == 0

    def test_close_nonexistent(self):
        store = PositionStore()
        assert store.close_position("XYZ") is None

    def test_reduce_position(self):
        store = PositionStore()
        store.open_position("AAPL", 100, 180.0)
        result = store.reduce_position("AAPL", 40, exit_price=190.0)
        assert result is not None
        assert result["qty_sold"] == 40
        assert store.get("AAPL").qty == 60

    def test_reduce_to_zero_closes(self):
        store = PositionStore()
        store.open_position("AAPL", 50, 180.0)
        result = store.reduce_position("AAPL", 50, exit_price=190.0)
        assert result is not None
        assert store.position_count == 0

    def test_update_price(self):
        store = PositionStore()
        store.open_position("AAPL", 100, 180.0)
        store.update_price("AAPL", 195.0)
        assert store.get("AAPL").current_price == 195.0

    def test_update_prices_bulk(self):
        store = PositionStore()
        store.open_position("AAPL", 100, 180.0)
        store.open_position("GOOG", 50, 140.0)
        updated = store.update_prices({"AAPL": 190.0, "GOOG": 145.0, "XYZ": 50.0})
        assert updated == 2

    def test_portfolio_summary(self):
        store = PositionStore()
        store.open_position("AAPL", 100, 180.0, "long")
        store.update_price("AAPL", 190.0)
        store.open_position("GOOG", 50, 140.0, "long")
        store.update_price("GOOG", 145.0)
        summary = store.get_portfolio_summary()
        assert summary["position_count"] == 2
        assert summary["unrealized_pnl"] == 1250.0  # 1000 + 250

    def test_check_exits(self):
        store = PositionStore()
        store.open_position("AAPL", 100, 180.0, "long",
                            stop_loss_price=175.0, target_price=200.0)
        store.update_price("AAPL", 170.0)  # Below stop
        triggered = store.check_exits()
        assert "AAPL" in triggered

    def test_check_exits_target_hit(self):
        store = PositionStore()
        store.open_position("GOOG", 50, 140.0, "long",
                            stop_loss_price=130.0, target_price=160.0)
        store.update_price("GOOG", 165.0)
        triggered = store.check_exits()
        assert "GOOG" in triggered

    def test_json_roundtrip(self):
        store = PositionStore()
        store.open_position("AAPL", 100, 185.0, "long", "fusion")
        store.open_position("GOOG", 50, 140.0, "long", "social")
        json_str = store.to_json()
        store2 = PositionStore.from_json(json_str)
        assert store2.position_count == 2
        assert store2.get("AAPL").qty == 100

    def test_get_closed_trades(self):
        store = PositionStore()
        store.open_position("AAPL", 100, 180.0)
        store.close_position("AAPL", 190.0)
        closed = store.get_closed_trades()
        assert len(closed) == 1
        assert closed[0]["realized_pnl"] == 1000.0

    def test_get_all(self):
        store = PositionStore()
        store.open_position("AAPL", 100, 180.0)
        store.open_position("GOOG", 50, 140.0)
        positions = store.get_all()
        assert len(positions) == 2


# ── Module imports ───────────────────────────────────────────────────


class TestModuleImports:

    def test_all_exports(self):
        from src.trade_pipeline import __all__
        assert "SignalBridge" in __all__
        assert "PipelineExecutor" in __all__
        assert "ExecutionReconciler" in __all__
        assert "PositionStore" in __all__

    def test_import_star(self):
        from src.trade_pipeline import (
            SignalType, OrderSide, OrderType, PipelineOrder, SignalBridge,
            PipelineStatus, PipelineResult, PipelineConfig, PipelineExecutor,
            ReconciliationRecord, SlippageStats, ExecutionReconciler,
            TrackedPosition, PositionStore,
        )
        assert SignalType.FUSION.value == "fusion"
        assert PipelineStatus.EXECUTED.value == "executed"
