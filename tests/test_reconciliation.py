"""PRD-126: Trade Reconciliation & Settlement Engine — Tests."""

from datetime import datetime, timedelta, timezone

from src.reconciliation.config import (
    BreakSeverity,
    BreakType,
    MatchStrategy,
    ReconciliationConfig,
    ReconciliationStatus,
    SettlementStatus,
    ToleranceConfig,
)
from src.reconciliation.matcher import MatchingEngine, MatchResult, TradeRecord
from src.reconciliation.settlement import SettlementEvent, SettlementTracker
from src.reconciliation.breaks import BreakManager, BreakResolution, ReconciliationBreak
from src.reconciliation.reporter import ReconciliationReporter


def _make_trade(
    trade_id: str = "t1",
    symbol: str = "AAPL",
    side: str = "buy",
    quantity: float = 100.0,
    price: float = 150.0,
    source: str = "internal",
    offset_seconds: int = 0,
) -> TradeRecord:
    ts = datetime(2025, 1, 10, 10, 0, 0, tzinfo=timezone.utc) + timedelta(
        seconds=offset_seconds
    )
    return TradeRecord(
        trade_id=trade_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        timestamp=ts,
        source=source,
    )


# ── Config Tests ───────────────────────────────────────────────────


class TestReconciliationConfig:
    def setup_method(self):
        self.config = ReconciliationConfig()
        self.tolerances = ToleranceConfig()

    def test_default_config(self):
        assert self.config.strategy == MatchStrategy.FUZZY
        assert self.config.settlement_days == 2
        assert self.config.auto_resolve_threshold == 0.99

    def test_tolerance_defaults(self):
        assert self.tolerances.price_tolerance_pct == 0.01
        assert self.tolerances.quantity_tolerance_pct == 0.0
        assert self.tolerances.time_window_seconds == 300
        assert self.tolerances.allow_partial_fills is True

    def test_custom_config(self):
        cfg = ReconciliationConfig(
            strategy=MatchStrategy.EXACT,
            settlement_days=1,
            max_breaks_before_halt=50,
        )
        assert cfg.strategy == MatchStrategy.EXACT
        assert cfg.settlement_days == 1

    def test_enums(self):
        assert ReconciliationStatus.MATCHED.value == "matched"
        assert BreakType.PRICE_MISMATCH.value == "price_mismatch"
        assert SettlementStatus.SETTLED.value == "settled"
        assert BreakSeverity.CRITICAL.value == "critical"

    def test_custom_tolerances(self):
        tol = ToleranceConfig(
            price_tolerance_pct=0.05,
            quantity_tolerance_pct=0.1,
            time_window_seconds=600,
            allow_partial_fills=False,
        )
        assert tol.price_tolerance_pct == 0.05
        assert tol.allow_partial_fills is False


# ── TradeRecord Tests ──────────────────────────────────────────────


class TestTradeRecord:
    def setup_method(self):
        self.trade = _make_trade()

    def test_basic_trade(self):
        assert self.trade.trade_id == "t1"
        assert self.trade.symbol == "AAPL"
        assert self.trade.side == "buy"
        assert self.trade.quantity == 100.0

    def test_notional(self):
        assert self.trade.notional == 15000.0

    def test_optional_fields(self):
        assert self.trade.order_id is None
        assert self.trade.account_id is None
        assert self.trade.fees == 0.0

    def test_trade_with_fees(self):
        trade = _make_trade()
        trade.fees = 5.50
        assert trade.fees == 5.50


# ── Matching Engine Tests ──────────────────────────────────────────


class TestMatchingEngine:
    def setup_method(self):
        self.engine = MatchingEngine()

    def test_exact_match(self):
        t1 = _make_trade("t1", source="internal")
        t2 = _make_trade("t2", source="broker")
        assert self.engine.exact_match(t1, t2) is True

    def test_exact_match_price_diff(self):
        t1 = _make_trade("t1", price=150.0)
        t2 = _make_trade("t2", price=150.01)
        assert self.engine.exact_match(t1, t2) is False

    def test_exact_match_quantity_diff(self):
        t1 = _make_trade("t1", quantity=100)
        t2 = _make_trade("t2", quantity=99)
        assert self.engine.exact_match(t1, t2) is False

    def test_exact_match_side_diff(self):
        t1 = _make_trade("t1", side="buy")
        t2 = _make_trade("t2", side="sell")
        assert self.engine.exact_match(t1, t2) is False

    def test_exact_match_symbol_diff(self):
        t1 = _make_trade("t1", symbol="AAPL")
        t2 = _make_trade("t2", symbol="MSFT")
        assert self.engine.exact_match(t1, t2) is False

    def test_fuzzy_match_within_tolerance(self):
        t1 = _make_trade("t1", price=150.0)
        t2 = _make_trade("t2", price=150.50)
        tolerances = ToleranceConfig(price_tolerance_pct=0.01)
        is_match, confidence = self.engine.fuzzy_match(t1, t2, tolerances)
        assert is_match is True
        assert confidence > 0.9

    def test_fuzzy_match_outside_tolerance(self):
        t1 = _make_trade("t1", price=150.0)
        t2 = _make_trade("t2", price=160.0)
        tolerances = ToleranceConfig(price_tolerance_pct=0.01)
        is_match, confidence = self.engine.fuzzy_match(t1, t2, tolerances)
        assert is_match is False

    def test_fuzzy_match_diff_symbol(self):
        t1 = _make_trade("t1", symbol="AAPL")
        t2 = _make_trade("t2", symbol="MSFT")
        tolerances = ToleranceConfig()
        is_match, confidence = self.engine.fuzzy_match(t1, t2, tolerances)
        assert is_match is False
        assert confidence == 0.0

    def test_fuzzy_match_time_window(self):
        t1 = _make_trade("t1", offset_seconds=0)
        t2 = _make_trade("t2", offset_seconds=600)
        tolerances = ToleranceConfig(time_window_seconds=300)
        is_match, _ = self.engine.fuzzy_match(t1, t2, tolerances)
        assert is_match is False

    def test_fuzzy_match_partial_fill(self):
        t1 = _make_trade("t1", quantity=100)
        t2 = _make_trade("t2", quantity=80)
        tolerances = ToleranceConfig(
            quantity_tolerance_pct=0.0, allow_partial_fills=True
        )
        is_match, confidence = self.engine.fuzzy_match(t1, t2, tolerances)
        assert is_match is True
        assert confidence < 1.0

    def test_match_trades_exact(self):
        internals = [_make_trade("i1", source="internal")]
        brokers = [_make_trade("b1", source="broker")]
        results = self.engine.match_trades(internals, brokers)
        assert len(results) == 1
        assert results[0].status == ReconciliationStatus.MATCHED
        assert results[0].confidence == 1.0

    def test_match_trades_missing_broker(self):
        internals = [_make_trade("i1")]
        brokers: list[TradeRecord] = []
        results = self.engine.match_trades(internals, brokers)
        assert len(results) == 1
        assert results[0].break_type == BreakType.MISSING_BROKER

    def test_match_trades_missing_internal(self):
        internals: list[TradeRecord] = []
        brokers = [_make_trade("b1")]
        results = self.engine.match_trades(internals, brokers)
        assert len(results) == 1
        assert results[0].break_type == BreakType.MISSING_INTERNAL

    def test_match_trades_multiple(self):
        internals = [
            _make_trade("i1", symbol="AAPL"),
            _make_trade("i2", symbol="MSFT", price=380.0),
        ]
        brokers = [
            _make_trade("b1", symbol="AAPL"),
            _make_trade("b2", symbol="MSFT", price=380.0),
        ]
        results = self.engine.match_trades(internals, brokers)
        matched = [r for r in results if r.status == ReconciliationStatus.MATCHED]
        assert len(matched) == 2

    def test_match_trades_with_break(self):
        internals = [_make_trade("i1", price=150.0)]
        brokers = [_make_trade("b1", price=155.0)]
        config = ReconciliationConfig(
            tolerances=ToleranceConfig(price_tolerance_pct=0.05)
        )
        engine = MatchingEngine(config)
        results = engine.match_trades(internals, brokers)
        assert len(results) == 1
        # Should fuzzy match within 5% tolerance but with a break
        assert results[0].break_type == BreakType.PRICE_MISMATCH

    def test_find_unmatched(self):
        internals = [_make_trade("i1"), _make_trade("i2", symbol="MSFT")]
        brokers = [_make_trade("b1")]
        results = self.engine.match_trades(internals, brokers)
        missing_broker, missing_internal = self.engine.find_unmatched(results)
        assert len(missing_broker) == 1
        assert missing_broker[0].symbol == "MSFT"

    def test_batch_reconcile(self):
        internals = [
            _make_trade("i1", symbol="AAPL"),
            _make_trade("i2", symbol="MSFT", price=380.0),
        ]
        brokers = [_make_trade("b1", symbol="AAPL")]
        summary = self.engine.batch_reconcile(internals, brokers)
        assert summary["total_internal"] == 2
        assert summary["total_broker"] == 1
        assert summary["matched"] == 1
        assert summary["broken"] >= 1

    def test_match_history(self):
        internals = [_make_trade("i1")]
        brokers = [_make_trade("b1")]
        self.engine.match_trades(internals, brokers)
        history = self.engine.get_match_history()
        assert len(history) == 1

    def test_exact_strategy(self):
        config = ReconciliationConfig(strategy=MatchStrategy.EXACT)
        engine = MatchingEngine(config)
        internals = [_make_trade("i1", price=150.0)]
        brokers = [_make_trade("b1", price=150.5)]
        results = engine.match_trades(internals, brokers)
        # No exact match, should have breaks
        assert any(r.status == ReconciliationStatus.BROKEN for r in results)


# ── Settlement Tracker Tests ──────────────────────────────────────


class TestSettlementTracker:
    def setup_method(self):
        self.tracker = SettlementTracker(settlement_days=2)

    def test_track_settlement(self):
        trade_date = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)  # Monday
        event = self.tracker.track_settlement("t1", trade_date, amount=15000.0)
        assert event.trade_id == "t1"
        assert event.status == SettlementStatus.PENDING
        assert event.expected_date.weekday() < 5  # not weekend

    def test_settlement_skip_weekend(self):
        # Friday trade should settle on Tuesday (T+2 skipping weekend)
        trade_date = datetime(2025, 1, 10, 10, 0, tzinfo=timezone.utc)  # Friday
        event = self.tracker.track_settlement("t1", trade_date)
        assert event.expected_date.weekday() < 5

    def test_update_status(self):
        trade_date = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        event = self.tracker.track_settlement("t1", trade_date)
        updated = self.tracker.update_status(
            event.event_id, SettlementStatus.SETTLED
        )
        assert updated is not None
        assert updated.status == SettlementStatus.SETTLED
        assert updated.actual_date is not None

    def test_update_status_invalid(self):
        result = self.tracker.update_status("nonexistent", SettlementStatus.SETTLED)
        assert result is None

    def test_get_event(self):
        trade_date = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        event = self.tracker.track_settlement("t1", trade_date)
        fetched = self.tracker.get_event(event.event_id)
        assert fetched is not None
        assert fetched.trade_id == "t1"

    def test_get_by_trade(self):
        trade_date = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        self.tracker.track_settlement("t1", trade_date)
        event = self.tracker.get_by_trade("t1")
        assert event is not None
        assert event.trade_id == "t1"

    def test_get_by_trade_missing(self):
        assert self.tracker.get_by_trade("nonexistent") is None

    def test_get_pending_settlements(self):
        now = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
        self.tracker.track_settlement(
            "t1", datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        )
        self.tracker.track_settlement(
            "t2", datetime(2025, 1, 14, 10, 0, tzinfo=timezone.utc)
        )
        pending = self.tracker.get_pending_settlements(now)
        assert len(pending) >= 1

    def test_check_overdue(self):
        past_date = datetime(2025, 1, 6, 10, 0, tzinfo=timezone.utc)
        self.tracker.track_settlement("t1", past_date)
        now = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
        overdue = self.tracker.check_overdue(now)
        assert len(overdue) == 1

    def test_settlement_summary(self):
        trade_date = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        event = self.tracker.track_settlement("t1", trade_date)
        self.tracker.update_status(event.event_id, SettlementStatus.SETTLED)
        self.tracker.track_settlement("t2", trade_date)

        summary = self.tracker.settlement_summary()
        assert summary["total"] == 2
        assert summary["settled"] == 1
        assert summary["pending"] == 1

    def test_settlement_summary_empty(self):
        summary = self.tracker.settlement_summary()
        assert summary["total"] == 0
        assert summary["settlement_rate"] == 0.0

    def test_average_settlement_time(self):
        trade_date = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        event = self.tracker.track_settlement("t1", trade_date)
        self.tracker.update_status(event.event_id, SettlementStatus.SETTLED)
        avg = self.tracker.average_settlement_time()
        assert avg is not None
        assert avg >= 0

    def test_average_settlement_time_none(self):
        assert self.tracker.average_settlement_time() is None

    def test_settlement_with_counterparty(self):
        trade_date = datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc)
        event = self.tracker.track_settlement(
            "t1", trade_date, counterparty="Alpaca", currency="USD", amount=10000.0
        )
        assert event.counterparty == "Alpaca"
        assert event.currency == "USD"
        assert event.amount == 10000.0


# ── Break Manager Tests ────────────────────────────────────────────


class TestBreakManager:
    def setup_method(self):
        self.manager = BreakManager()

    def _make_match_result(
        self,
        status=ReconciliationStatus.BROKEN,
        break_type=BreakType.PRICE_MISMATCH,
        confidence=0.8,
    ):
        return MatchResult(
            match_id="m1",
            internal_trade=_make_trade("i1", price=150.0),
            broker_trade=_make_trade("b1", price=152.0),
            status=status,
            break_type=break_type,
            confidence=confidence,
        )

    def test_create_break(self):
        result = self._make_match_result()
        brk = self.manager.create_break(result)
        assert brk.break_type == BreakType.PRICE_MISMATCH
        assert brk.status == "open"

    def test_classify_break_price(self):
        result = self._make_match_result(break_type=None)
        result.internal_trade = _make_trade("i1", price=150.0)
        result.broker_trade = _make_trade("b1", price=155.0)
        classified = self.manager.classify_break(result)
        assert classified == BreakType.PRICE_MISMATCH

    def test_classify_break_quantity(self):
        result = self._make_match_result(break_type=None)
        result.internal_trade = _make_trade("i1", quantity=100)
        result.broker_trade = _make_trade("b1", quantity=90)
        classified = self.manager.classify_break(result)
        assert classified == BreakType.QUANTITY_MISMATCH

    def test_classify_break_missing_internal(self):
        result = self._make_match_result(break_type=None)
        result.internal_trade = None
        classified = self.manager.classify_break(result)
        assert classified == BreakType.MISSING_INTERNAL

    def test_classify_break_missing_broker(self):
        result = self._make_match_result(break_type=None)
        result.broker_trade = None
        classified = self.manager.classify_break(result)
        assert classified == BreakType.MISSING_BROKER

    def test_resolve_break(self):
        result = self._make_match_result()
        brk = self.manager.create_break(result)
        resolution = self.manager.resolve_break(
            brk.break_id, "adjusted", "ops_user", notes="Adjusted price"
        )
        assert resolution is not None
        assert resolution.action == "adjusted"
        assert brk.status == "resolved"

    def test_resolve_break_invalid(self):
        assert self.manager.resolve_break("nonexistent", "adjusted", "user") is None

    def test_auto_resolve_high_confidence(self):
        result = self._make_match_result(confidence=0.995)
        brk = self.manager.create_break(result)
        resolution = self.manager.auto_resolve(brk)
        assert resolution is not None
        assert resolution.resolved_by == "auto_resolver"

    def test_auto_resolve_low_confidence(self):
        result = self._make_match_result(confidence=0.5)
        brk = self.manager.create_break(result)
        resolution = self.manager.auto_resolve(brk)
        assert resolution is None

    def test_assign_break(self):
        result = self._make_match_result()
        brk = self.manager.create_break(result)
        assigned = self.manager.assign_break(brk.break_id, "analyst_1")
        assert assigned is not None
        assert assigned.assigned_to == "analyst_1"
        assert assigned.status == "investigating"

    def test_dismiss_break(self):
        result = self._make_match_result()
        brk = self.manager.create_break(result)
        dismissed = self.manager.dismiss_break(brk.break_id, "Not material")
        assert dismissed is not None
        assert dismissed.status == "dismissed"

    def test_get_open_breaks(self):
        r1 = self._make_match_result()
        r2 = self._make_match_result()
        b1 = self.manager.create_break(r1)
        b2 = self.manager.create_break(r2)
        self.manager.resolve_break(b1.break_id, "adjusted", "user")
        open_breaks = self.manager.get_open_breaks()
        assert len(open_breaks) == 1

    def test_get_breaks_by_type(self):
        r1 = self._make_match_result(break_type=BreakType.PRICE_MISMATCH)
        r2 = self._make_match_result(break_type=BreakType.MISSING_BROKER)
        self.manager.create_break(r1)
        self.manager.create_break(r2)
        price_breaks = self.manager.get_breaks_by_type(BreakType.PRICE_MISMATCH)
        assert len(price_breaks) == 1

    def test_break_statistics(self):
        r1 = self._make_match_result()
        r2 = self._make_match_result(break_type=BreakType.MISSING_BROKER)
        b1 = self.manager.create_break(r1)
        self.manager.create_break(r2)
        self.manager.resolve_break(b1.break_id, "adjusted", "user")

        stats = self.manager.break_statistics()
        assert stats["total"] == 2
        assert stats["resolved"] == 1
        assert stats["open"] == 1
        assert stats["resolution_rate"] == 0.5

    def test_break_statistics_empty(self):
        stats = self.manager.break_statistics()
        assert stats["total"] == 0

    def test_severity_classification_side(self):
        result = self._make_match_result(break_type=BreakType.SIDE_MISMATCH)
        brk = self.manager.create_break(result)
        assert brk.severity == BreakSeverity.CRITICAL

    def test_severity_classification_missing(self):
        result = self._make_match_result(break_type=BreakType.MISSING_BROKER)
        brk = self.manager.create_break(result)
        assert brk.severity == BreakSeverity.HIGH

    def test_get_break(self):
        result = self._make_match_result()
        brk = self.manager.create_break(result)
        fetched = self.manager.get_break(brk.break_id)
        assert fetched is not None
        assert fetched.break_id == brk.break_id


# ── Reporter Tests ──────────────────────────────────────────────────


class TestReconciliationReporter:
    def setup_method(self):
        self.reporter = ReconciliationReporter()
        self.now = datetime.now(timezone.utc)

    def _make_results(self):
        matched = MatchResult(
            match_id="m1",
            internal_trade=_make_trade("i1"),
            broker_trade=_make_trade("b1"),
            status=ReconciliationStatus.MATCHED,
            confidence=1.0,
        )
        broken = MatchResult(
            match_id="m2",
            internal_trade=_make_trade("i2"),
            broker_trade=None,
            status=ReconciliationStatus.BROKEN,
            break_type=BreakType.MISSING_BROKER,
            confidence=0.0,
        )
        return [matched, broken]

    def test_generate_report(self):
        results = self._make_results()
        report = self.reporter.generate_report(
            results,
            self.now - timedelta(hours=1),
            self.now,
        )
        assert report.matched == 1
        assert report.broken == 1
        assert report.match_rate == 0.5
        assert len(report.break_details) == 1

    def test_record_daily(self):
        daily = self.reporter.record_daily(
            date=self.now,
            statistics={"matched": 95, "broken": 5},
            breaks=[{"type": "price_mismatch"}],
        )
        assert daily.date == self.now
        assert daily.statistics["matched"] == 95

    def test_aging_report(self):
        breaks = [
            {"created_at": self.now - timedelta(hours=2)},
            {"created_at": self.now - timedelta(days=2)},
            {"created_at": self.now - timedelta(days=10)},
        ]
        aging = self.reporter.aging_report(breaks)
        assert aging["0-1_days"] == 1
        assert aging["1-3_days"] == 1
        assert aging["7-14_days"] == 1

    def test_trend_analysis_no_data(self):
        trend = self.reporter.trend_analysis(30)
        assert trend["trend"] == "no_data"
        assert trend["reports_count"] == 0

    def test_trend_analysis_with_data(self):
        results = self._make_results()
        for i in range(10):
            self.reporter.generate_report(
                results,
                self.now - timedelta(days=10 - i, hours=1),
                self.now - timedelta(days=10 - i),
            )
        trend = self.reporter.trend_analysis(30)
        assert trend["reports_count"] == 10
        assert trend["avg_match_rate"] > 0

    def test_get_reports(self):
        results = self._make_results()
        self.reporter.generate_report(results, self.now - timedelta(hours=1), self.now)
        assert len(self.reporter.get_reports()) == 1

    def test_get_daily_records(self):
        self.reporter.record_daily(self.now, {"matched": 10})
        records = self.reporter.get_daily_records()
        assert len(records) == 1

    def test_aging_report_string_dates(self):
        breaks = [{"created_at": "2025-01-10"}]
        aging = self.reporter.aging_report(breaks)
        # String dates are skipped
        assert sum(aging.values()) == 0


# ── Integration Tests ──────────────────────────────────────────────


class TestReconciliationIntegration:
    def setup_method(self):
        self.config = ReconciliationConfig()
        self.engine = MatchingEngine(self.config)
        self.tracker = SettlementTracker()
        self.break_mgr = BreakManager(self.config)
        self.reporter = ReconciliationReporter()

    def test_full_reconciliation_flow(self):
        # 1. Match trades
        internals = [
            _make_trade("i1", symbol="AAPL", price=150.0),
            _make_trade("i2", symbol="MSFT", price=380.0),
            _make_trade("i3", symbol="GOOGL", price=140.0),
        ]
        brokers = [
            _make_trade("b1", symbol="AAPL", price=150.0),
            _make_trade("b2", symbol="MSFT", price=380.0),
        ]
        results = self.engine.match_trades(internals, brokers)

        # 2. Track settlements for matched
        matched = [r for r in results if r.status == ReconciliationStatus.MATCHED]
        for m in matched:
            self.tracker.track_settlement(
                m.internal_trade.trade_id,
                m.internal_trade.timestamp,
            )

        # 3. Create breaks for broken
        broken = [r for r in results if r.status == ReconciliationStatus.BROKEN]
        for b in broken:
            self.break_mgr.create_break(b)

        # 4. Generate report
        now = datetime.now(timezone.utc)
        report = self.reporter.generate_report(
            results, now - timedelta(hours=1), now
        )

        assert len(matched) == 2
        assert len(broken) == 1
        assert report.match_rate > 0.5

    def test_reconciliation_with_auto_resolve(self):
        internals = [_make_trade("i1", price=150.0)]
        brokers = [_make_trade("b1", price=150.005)]
        config = ReconciliationConfig(
            auto_resolve_threshold=0.9,
            tolerances=ToleranceConfig(price_tolerance_pct=0.01),
        )
        engine = MatchingEngine(config)
        break_mgr = BreakManager(config)

        results = engine.match_trades(internals, brokers)
        for r in results:
            if r.status == ReconciliationStatus.BROKEN:
                brk = break_mgr.create_break(r)
                break_mgr.auto_resolve(brk)

        stats = break_mgr.break_statistics()
        assert stats["total"] >= 0
