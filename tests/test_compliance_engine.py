"""Tests for PRD-99: Compliance Engine."""

from datetime import date, datetime, timedelta

import pytest

from src.compliance_engine.config import (
    SurveillanceType,
    AlertSeverity,
    BlackoutStatus,
    ExecutionQuality,
    ReportType,
    SurveillanceConfig,
    BlackoutConfig,
    BestExecutionConfig,
)
from src.compliance_engine.models import (
    SurveillanceAlert,
    TradePattern,
    BlackoutWindow,
    PreClearanceRequest,
    BestExecutionReport,
    ExecutionMetric,
    RegulatoryFiling,
    ComplianceSummary,
)
from src.compliance_engine.surveillance import SurveillanceEngine
from src.compliance_engine.blackout import BlackoutManager
from src.compliance_engine.best_execution import BestExecutionMonitor
from src.compliance_engine.reporting import RegulatoryReporter


# ── Config Tests ──────────────────────────────────────────────────────


class TestEnums:
    def test_surveillance_types(self):
        assert len(SurveillanceType) == 8
        assert SurveillanceType.WASH_TRADE.value == "wash_trade"
        assert SurveillanceType.SPOOFING.value == "spoofing"

    def test_alert_severity(self):
        assert len(AlertSeverity) == 4

    def test_blackout_status(self):
        assert len(BlackoutStatus) == 3

    def test_execution_quality(self):
        assert len(ExecutionQuality) == 5
        assert ExecutionQuality.EXCELLENT.value == "excellent"

    def test_report_types(self):
        assert len(ReportType) == 5


class TestConfigs:
    def test_surveillance_config(self):
        cfg = SurveillanceConfig()
        assert cfg.wash_trade_window == 300
        assert len(cfg.enabled_checks) == 8

    def test_blackout_config(self):
        cfg = BlackoutConfig()
        assert cfg.default_blackout_days_before == 14
        assert cfg.require_pre_clearance

    def test_best_execution_config(self):
        cfg = BestExecutionConfig()
        assert cfg.max_slippage_bps == 10.0
        assert cfg.excellent_threshold_bps == 2.0


# ── Model Tests ───────────────────────────────────────────────────────


class TestBlackoutWindow:
    def test_is_in_blackout(self):
        w = BlackoutWindow(
            window_id="W1", symbol="AAPL", reason="Earnings",
            start_date=date(2024, 1, 15), end_date=date(2024, 2, 1),
        )
        assert w.is_in_blackout(date(2024, 1, 20))
        assert not w.is_in_blackout(date(2024, 2, 5))

    def test_inactive_window(self):
        w = BlackoutWindow(
            window_id="W1", symbol="AAPL", reason="Earnings",
            start_date=date(2024, 1, 1), end_date=date(2024, 12, 31),
            is_active=False,
        )
        assert not w.is_in_blackout(date(2024, 6, 1))


class TestPreClearanceRequest:
    def test_pending(self):
        r = PreClearanceRequest(
            request_id="R1", requester_id="U1",
            symbol="AAPL", side="buy", quantity=100,
        )
        assert r.is_pending
        assert not r.is_valid

    def test_approved(self):
        r = PreClearanceRequest(
            request_id="R1", requester_id="U1",
            symbol="AAPL", side="buy", quantity=100,
            approved=True,
            valid_until=date.today() + timedelta(days=5),
        )
        assert not r.is_pending
        assert r.is_valid

    def test_expired(self):
        r = PreClearanceRequest(
            request_id="R1", requester_id="U1",
            symbol="AAPL", side="buy", quantity=100,
            approved=True,
            valid_until=date.today() - timedelta(days=1),
        )
        assert not r.is_valid


class TestComplianceSummary:
    def test_creation(self):
        s = ComplianceSummary(
            period="2024-Q1",
            surveillance_alerts=10,
            unresolved_alerts=3,
            overall_status="review_required",
        )
        assert s.surveillance_alerts == 10
        assert s.overall_status == "review_required"


# ── Surveillance Engine Tests ────────────────────────────────────────


class TestSurveillanceEngine:
    def test_detect_wash_trade(self):
        engine = SurveillanceEngine()
        trades = [
            {"symbol": "AAPL", "side": "buy", "price": 175.0, "timestamp": 1000},
            {"symbol": "AAPL", "side": "sell", "price": 175.0, "timestamp": 1100},
        ]
        alerts = engine.scan_trades(trades, "ACC-001")
        wash = [a for a in alerts if a.alert_type == "wash_trade"]
        assert len(wash) > 0
        assert wash[0].severity == "high"

    def test_no_wash_trade_different_prices(self):
        engine = SurveillanceEngine()
        trades = [
            {"symbol": "AAPL", "side": "buy", "price": 175.0, "timestamp": 1000},
            {"symbol": "AAPL", "side": "sell", "price": 180.0, "timestamp": 1100},
        ]
        alerts = engine.scan_trades(trades, "ACC-001")
        wash = [a for a in alerts if a.alert_type == "wash_trade"]
        assert len(wash) == 0

    def test_detect_layering(self):
        engine = SurveillanceEngine(SurveillanceConfig(layering_threshold=3))
        trades = [
            {"symbol": "AAPL", "side": "buy"} for _ in range(5)
        ]
        alerts = engine.scan_trades(trades, "ACC-001")
        layering = [a for a in alerts if a.alert_type == "layering"]
        assert len(layering) > 0

    def test_detect_spoofing(self):
        engine = SurveillanceEngine()
        trades = [
            {"symbol": "MSFT", "status": "cancelled"} for _ in range(9)
        ] + [
            {"symbol": "MSFT", "status": "filled"},
        ]
        alerts = engine.scan_trades(trades, "ACC-001")
        spoof = [a for a in alerts if a.alert_type == "spoofing"]
        assert len(spoof) > 0
        assert spoof[0].severity == "critical"

    def test_detect_excessive_trading(self):
        engine = SurveillanceEngine(SurveillanceConfig(excessive_trading_limit=5))
        trades = [{"symbol": f"SYM{i}", "side": "buy"} for i in range(10)]
        alerts = engine.scan_trades(trades, "ACC-001")
        excessive = [a for a in alerts if a.alert_type == "excessive_trading"]
        assert len(excessive) > 0

    def test_detect_marking_close(self):
        engine = SurveillanceEngine()
        trades = [
            {"symbol": "AAPL", "side": "buy", "quantity": 5000, "minutes_to_close": 3},
        ]
        alerts = engine.scan_trades(trades, "ACC-001")
        marking = [a for a in alerts if a.alert_type == "marking_close"]
        assert len(marking) > 0

    def test_no_marking_close_small_order(self):
        engine = SurveillanceEngine()
        trades = [
            {"symbol": "AAPL", "side": "buy", "quantity": 50, "minutes_to_close": 3},
        ]
        alerts = engine.scan_trades(trades)
        marking = [a for a in alerts if a.alert_type == "marking_close"]
        assert len(marking) == 0

    def test_resolve_alert(self):
        engine = SurveillanceEngine()
        trades = [
            {"symbol": "AAPL", "side": "buy", "price": 175.0, "timestamp": 1000},
            {"symbol": "AAPL", "side": "sell", "price": 175.0, "timestamp": 1100},
        ]
        alerts = engine.scan_trades(trades)
        assert len(alerts) > 0

        resolved = engine.resolve_alert(alerts[0].alert_id, "compliance_officer")
        assert resolved
        assert alerts[0].is_resolved

    def test_get_alerts_filtered(self):
        engine = SurveillanceEngine(SurveillanceConfig(layering_threshold=2))
        trade_list = [
            {"symbol": "AAPL", "side": "buy", "price": 175.0, "timestamp": 1000},
            {"symbol": "AAPL", "side": "sell", "price": 175.0, "timestamp": 1100},
            {"symbol": "MSFT", "side": "buy"},
            {"symbol": "MSFT", "side": "buy"},
            {"symbol": "MSFT", "side": "buy"},
        ]
        engine.scan_trades(trade_list)

        all_alerts = engine.get_alerts()
        assert len(all_alerts) > 0

        high = engine.get_alerts(severity="high")
        assert all(a.severity == "high" for a in high)

    def test_alert_count(self):
        engine = SurveillanceEngine()
        trades = [
            {"symbol": "AAPL", "side": "buy", "price": 175.0, "timestamp": 1000},
            {"symbol": "AAPL", "side": "sell", "price": 175.0, "timestamp": 1100},
        ]
        engine.scan_trades(trades)
        counts = engine.get_alert_count()
        assert isinstance(counts, dict)


# ── Blackout Manager Tests ───────────────────────────────────────────


class TestBlackoutManager:
    def test_create_blackout(self):
        mgr = BlackoutManager()
        w = mgr.create_blackout("AAPL", "Earnings", date(2024, 1, 15), date(2024, 2, 1))
        assert w.symbol == "AAPL"
        assert w.is_active

    def test_create_earnings_blackout(self):
        mgr = BlackoutManager(BlackoutConfig(
            default_blackout_days_before=14,
            default_blackout_days_after=2,
        ))
        w = mgr.create_earnings_blackout("AAPL", date(2024, 1, 25))
        assert w.start_date == date(2024, 1, 11)
        assert w.end_date == date(2024, 1, 27)

    def test_check_blackout(self):
        mgr = BlackoutManager()
        mgr.create_blackout("AAPL", "Earnings", date(2024, 1, 15), date(2024, 2, 1))
        assert mgr.check_blackout("AAPL", date(2024, 1, 20))
        assert not mgr.check_blackout("AAPL", date(2024, 3, 1))
        assert not mgr.check_blackout("MSFT", date(2024, 1, 20))

    def test_person_specific_blackout(self):
        mgr = BlackoutManager()
        mgr.create_blackout(
            "AAPL", "Insider", date(2024, 1, 1), date(2024, 12, 31),
            affected_persons=["insider_1", "insider_2"],
        )
        assert mgr.check_blackout("AAPL", date(2024, 6, 1), person_id="insider_1")
        assert not mgr.check_blackout("AAPL", date(2024, 6, 1), person_id="outsider")

    def test_deactivate_blackout(self):
        mgr = BlackoutManager()
        w = mgr.create_blackout("AAPL", "Test", date(2024, 1, 1), date(2024, 12, 31))
        assert mgr.check_blackout("AAPL", date(2024, 6, 1))
        mgr.deactivate_blackout(w.window_id)
        assert not mgr.check_blackout("AAPL", date(2024, 6, 1))

    def test_pre_clearance_workflow(self):
        mgr = BlackoutManager()
        req = mgr.submit_pre_clearance("U1", "AAPL", "buy", 100, 17500)
        assert req.is_pending

        approved = mgr.approve_pre_clearance(req.request_id, "compliance_officer")
        assert approved
        assert req.is_valid
        assert req.valid_until is not None

    def test_deny_pre_clearance(self):
        mgr = BlackoutManager()
        req = mgr.submit_pre_clearance("U1", "AAPL", "buy", 100)
        denied = mgr.deny_pre_clearance(req.request_id, "officer")
        assert denied
        assert req.approved is False

    def test_pending_requests(self):
        mgr = BlackoutManager()
        mgr.submit_pre_clearance("U1", "AAPL", "buy", 100)
        mgr.submit_pre_clearance("U2", "MSFT", "sell", 200)
        assert len(mgr.get_pending_requests()) == 2

    def test_can_trade_no_blackout(self):
        mgr = BlackoutManager()
        result = mgr.can_trade("AAPL", "U1")
        assert result["allowed"]

    def test_can_trade_in_blackout(self):
        mgr = BlackoutManager()
        mgr.create_blackout("AAPL", "Test", date.today() - timedelta(days=1), date.today() + timedelta(days=1))
        result = mgr.can_trade("AAPL", "U1", 50_000)
        assert not result["allowed"]

    def test_can_trade_below_threshold(self):
        mgr = BlackoutManager(BlackoutConfig(max_trade_value_without_clearance=10_000))
        mgr.create_blackout("AAPL", "Test", date.today() - timedelta(days=1), date.today() + timedelta(days=1))
        result = mgr.can_trade("AAPL", "U1", 5_000)
        assert result["allowed"]

    def test_active_blackouts(self):
        mgr = BlackoutManager()
        mgr.create_blackout("AAPL", "Earnings", date(2024, 1, 1), date(2024, 1, 31))
        mgr.create_blackout("MSFT", "Earnings", date(2024, 1, 15), date(2024, 2, 15))
        active = mgr.get_active_blackouts(date(2024, 1, 20))
        assert len(active) == 2


# ── Best Execution Monitor Tests ─────────────────────────────────────


class TestBestExecutionMonitor:
    def test_record_execution(self):
        mon = BestExecutionMonitor()
        m = mon.record_execution("O1", "AAPL", "buy", 100, 176.0, 175.50, 175.0, "NYSE")
        assert m.slippage_bps > 0  # Fill above benchmark
        assert m.price_improvement_bps > 0  # Fill below limit

    def test_excellent_execution(self):
        mon = BestExecutionMonitor()
        m = mon.record_execution("O1", "AAPL", "buy", 100, 176.0, 175.01, 175.0, "NYSE")
        assert m.quality == "excellent"

    def test_poor_execution(self):
        mon = BestExecutionMonitor()
        m = mon.record_execution("O1", "AAPL", "buy", 100, 180.0, 178.0, 175.0, "NYSE")
        assert m.quality in ("poor", "failed")

    def test_sell_side_slippage(self):
        mon = BestExecutionMonitor()
        m = mon.record_execution("O1", "AAPL", "sell", 100, 174.0, 174.50, 175.0, "NYSE")
        assert m.slippage_bps > 0  # Fill below benchmark for sell

    def test_generate_report(self):
        mon = BestExecutionMonitor()
        today = date.today()

        for i in range(10):
            mon.record_execution(
                f"O{i}", "AAPL", "buy", 100,
                176.0, 175.0 + i * 0.1, 175.0, f"VENUE{i % 3}",
            )

        report = mon.generate_report(today - timedelta(days=1), today + timedelta(days=1))
        assert report.total_orders == 10
        assert report.avg_slippage_bps >= 0
        assert len(report.by_venue) > 0
        assert report.overall_quality in ("excellent", "good", "acceptable", "poor", "failed")

    def test_empty_report(self):
        mon = BestExecutionMonitor()
        report = mon.generate_report(date(2024, 1, 1), date(2024, 1, 31))
        assert report.total_orders == 0

    def test_poor_executions(self):
        mon = BestExecutionMonitor()
        mon.record_execution("O1", "AAPL", "buy", 100, 200.0, 185.0, 175.0, "NYSE")
        mon.record_execution("O2", "MSFT", "buy", 100, 380.0, 380.1, 380.0, "NASDAQ")
        poor = mon.get_poor_executions()
        assert len(poor) >= 1

    def test_venue_ranking(self):
        mon = BestExecutionMonitor()
        for i in range(5):
            mon.record_execution(f"O{i}", "AAPL", "buy", 100, 176.0, 175.5, 175.0, "NYSE")
        for i in range(5):
            mon.record_execution(f"P{i}", "AAPL", "buy", 100, 176.0, 175.1, 175.0, "IEX")

        ranking = mon.get_venue_ranking()
        assert len(ranking) == 2
        # IEX should rank better (lower slippage)
        assert ranking[0]["venue"] == "IEX"


# ── Regulatory Reporter Tests ────────────────────────────────────────


class TestRegulatoryReporter:
    def test_daily_compliance_report(self):
        reporter = RegulatoryReporter()
        alerts = [
            SurveillanceAlert("A1", "wash_trade", "high", "AAPL"),
            SurveillanceAlert("A2", "spoofing", "critical", "MSFT"),
        ]
        filing = reporter.generate_daily_compliance(date.today(), alerts)
        assert filing.report_type == "daily_compliance"
        assert filing.content["total_alerts"] == 2
        assert filing.content["status"] == "non_compliant"  # Has critical

    def test_compliant_report(self):
        reporter = RegulatoryReporter()
        filing = reporter.generate_daily_compliance(date.today(), [])
        assert filing.content["status"] == "compliant"

    def test_surveillance_summary(self):
        reporter = RegulatoryReporter()
        alerts = [
            SurveillanceAlert("A1", "wash_trade", "high", "AAPL"),
            SurveillanceAlert("A2", "layering", "medium", "MSFT", is_resolved=True),
        ]
        filing = reporter.generate_surveillance_summary(
            date(2024, 1, 1), date(2024, 1, 31), alerts,
        )
        assert filing.content["total_alerts"] == 2
        assert filing.content["resolved"] == 1
        assert filing.content["resolution_rate"] == 0.5

    def test_best_execution_filing(self):
        reporter = RegulatoryReporter()
        report = BestExecutionReport(
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            total_orders=100,
            avg_slippage_bps=3.5,
            overall_quality="good",
        )
        filing = reporter.generate_best_execution_filing(report)
        assert filing.report_type == "best_execution"
        assert filing.content["avg_slippage_bps"] == 3.5

    def test_compliance_summary(self):
        reporter = RegulatoryReporter()
        alerts = [
            SurveillanceAlert("A1", "wash_trade", "high", "AAPL"),
        ]
        summary = reporter.generate_compliance_summary(
            "2024-Q1", alerts, blackout_violations=0,
        )
        assert summary.surveillance_alerts == 1
        assert summary.overall_status == "compliant"

    def test_non_compliant_summary(self):
        reporter = RegulatoryReporter()
        alerts = [
            SurveillanceAlert("A1", "spoofing", "critical", "AAPL"),
        ]
        summary = reporter.generate_compliance_summary(
            "2024-Q1", alerts, blackout_violations=1,
        )
        assert summary.overall_status == "non_compliant"

    def test_mark_filed(self):
        reporter = RegulatoryReporter()
        filing = reporter.generate_daily_compliance(date.today(), [])
        assert not filing.filed

        reporter.mark_filed(filing.filing_id)
        assert filing.filed
        assert filing.filed_at is not None

    def test_get_filings(self):
        reporter = RegulatoryReporter()
        reporter.generate_daily_compliance(date.today(), [])
        reporter.generate_surveillance_summary(date(2024, 1, 1), date(2024, 1, 31), [])

        all_filings = reporter.get_filings()
        assert len(all_filings) == 2

        daily = reporter.get_filings(report_type="daily_compliance")
        assert len(daily) == 1

        unfiled = reporter.get_filings(unfiled_only=True)
        assert len(unfiled) == 2


# ── Integration Tests ─────────────────────────────────────────────────


class TestIntegration:
    def test_full_compliance_workflow(self):
        """End-to-end: surveillance -> blackout -> execution -> reporting."""
        # 1. Surveillance
        engine = SurveillanceEngine()
        trades = [
            {"symbol": "AAPL", "side": "buy", "price": 175.0, "timestamp": 1000},
            {"symbol": "AAPL", "side": "sell", "price": 175.0, "timestamp": 1100},
            {"symbol": "MSFT", "side": "buy"},
            {"symbol": "MSFT", "side": "buy"},
            {"symbol": "MSFT", "side": "buy"},
            {"symbol": "MSFT", "side": "buy"},
            {"symbol": "MSFT", "side": "buy"},
        ]
        alerts = engine.scan_trades(trades, "ACC-001")
        assert len(alerts) > 0

        # 2. Blackout check
        blackout_mgr = BlackoutManager()
        blackout_mgr.create_earnings_blackout("AAPL", date.today() + timedelta(days=7))
        result = blackout_mgr.can_trade("AAPL", "insider_1", 50_000)
        # May or may not be in blackout depending on date

        # 3. Best execution
        monitor = BestExecutionMonitor()
        for i in range(5):
            monitor.record_execution(
                f"O{i}", "AAPL", "buy", 100,
                176.0, 175.0 + i * 0.2, 175.0, "NYSE",
            )
        today = date.today()
        report = monitor.generate_report(today - timedelta(days=1), today + timedelta(days=1))

        # 4. Regulatory reporting
        reporter = RegulatoryReporter()
        filing = reporter.generate_daily_compliance(
            today, alerts, best_exec=report,
        )
        assert filing.content["total_alerts"] == len(alerts)

        summary = reporter.generate_compliance_summary(
            "today", alerts, best_exec=report,
        )
        assert summary.surveillance_alerts > 0

    def test_pre_clearance_workflow(self):
        """Pre-clearance: submit -> approve -> trade check."""
        mgr = BlackoutManager()
        mgr.create_blackout("AAPL", "Earnings",
                            date.today() - timedelta(days=1),
                            date.today() + timedelta(days=10))

        # Submit pre-clearance
        req = mgr.submit_pre_clearance("trader_1", "AAPL", "buy", 100, 17500)
        assert req.is_pending

        # Initially blocked
        result = mgr.can_trade("AAPL", "trader_1", 17500)
        assert not result["allowed"]

        # Approve
        mgr.approve_pre_clearance(req.request_id, "compliance")

        # Now allowed
        result = mgr.can_trade("AAPL", "trader_1", 17500)
        assert result["allowed"]


# ── Module Import Test ────────────────────────────────────────────────


class TestModuleImports:
    def test_import_all(self):
        import src.compliance_engine as ce
        assert hasattr(ce, "SurveillanceEngine")
        assert hasattr(ce, "BlackoutManager")
        assert hasattr(ce, "BestExecutionMonitor")
        assert hasattr(ce, "RegulatoryReporter")
        assert hasattr(ce, "SurveillanceType")
        assert hasattr(ce, "AlertSeverity")
        assert hasattr(ce, "ComplianceSummary")
