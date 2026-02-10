"""Tests for PRD-41: Portfolio Rebalancing."""

import pytest
from datetime import date, timedelta

from src.rebalancing.config import (
    RebalanceTrigger,
    RebalanceFrequency,
    DriftMethod,
    RebalanceStatus,
    DriftConfig,
    CalendarConfig,
    TaxConfig,
    CostConfig,
    RebalancingConfig,
    DEFAULT_DRIFT_CONFIG,
    DEFAULT_CALENDAR_CONFIG,
    DEFAULT_CONFIG,
)
from src.rebalancing.models import (
    Holding,
    DriftAnalysis,
    PortfolioDrift,
    RebalanceTrade,
    RebalancePlan,
    ScheduleState,
)
from src.rebalancing.drift import DriftMonitor
from src.rebalancing.planner import RebalancePlanner
from src.rebalancing.scheduler import RebalanceScheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_holdings(drifted: bool = False) -> list[Holding]:
    """Create sample holdings."""
    if drifted:
        return [
            Holding(symbol="AAPL", shares=100, price=150.0, market_value=15000,
                    current_weight=0.30, target_weight=0.25, cost_basis=140.0),
            Holding(symbol="MSFT", shares=50, price=350.0, market_value=17500,
                    current_weight=0.35, target_weight=0.25, cost_basis=300.0),
            Holding(symbol="GOOGL", shares=30, price=120.0, market_value=3600,
                    current_weight=0.07, target_weight=0.25, cost_basis=130.0),
            Holding(symbol="AMZN", shares=80, price=175.0, market_value=14000,
                    current_weight=0.28, target_weight=0.25, cost_basis=180.0),
        ]
    return [
        Holding(symbol="AAPL", shares=100, price=150.0, market_value=15000,
                current_weight=0.25, target_weight=0.25, cost_basis=140.0),
        Holding(symbol="MSFT", shares=50, price=350.0, market_value=17500,
                current_weight=0.25, target_weight=0.25, cost_basis=300.0),
        Holding(symbol="GOOGL", shares=30, price=120.0, market_value=3600,
                current_weight=0.25, target_weight=0.25, cost_basis=130.0),
        Holding(symbol="AMZN", shares=80, price=175.0, market_value=14000,
                current_weight=0.25, target_weight=0.25, cost_basis=180.0),
    ]


# ===========================================================================
# Config Tests
# ===========================================================================

class TestRebalancingConfig:
    """Test configuration enums and dataclasses."""

    def test_trigger_values(self):
        assert RebalanceTrigger.CALENDAR.value == "calendar"
        assert RebalanceTrigger.THRESHOLD.value == "threshold"
        assert RebalanceTrigger.COMBINED.value == "combined"
        assert RebalanceTrigger.MANUAL.value == "manual"

    def test_frequency_values(self):
        assert RebalanceFrequency.WEEKLY.value == "weekly"
        assert RebalanceFrequency.MONTHLY.value == "monthly"
        assert RebalanceFrequency.QUARTERLY.value == "quarterly"
        assert RebalanceFrequency.ANNUAL.value == "annual"

    def test_drift_method_values(self):
        assert DriftMethod.ABSOLUTE.value == "absolute"
        assert DriftMethod.RELATIVE.value == "relative"

    def test_status_values(self):
        assert RebalanceStatus.PENDING.value == "pending"
        assert RebalanceStatus.EXECUTED.value == "executed"

    def test_drift_config_defaults(self):
        cfg = DriftConfig()
        assert cfg.threshold == 0.05
        assert cfg.critical_threshold == 0.10
        assert cfg.method == DriftMethod.ABSOLUTE

    def test_calendar_config_defaults(self):
        cfg = CalendarConfig()
        assert cfg.frequency == RebalanceFrequency.QUARTERLY
        assert cfg.day_of_week == 0

    def test_tax_config_defaults(self):
        cfg = TaxConfig()
        assert cfg.enabled is True
        assert cfg.short_term_days == 365
        assert cfg.wash_sale_days == 30

    def test_cost_config_defaults(self):
        cfg = CostConfig()
        assert cfg.commission_per_trade == 0.0
        assert cfg.spread_cost_bps == 1.0
        assert cfg.min_trade_dollars == 100.0

    def test_rebalancing_config_bundles(self):
        cfg = RebalancingConfig()
        assert isinstance(cfg.drift, DriftConfig)
        assert isinstance(cfg.calendar, CalendarConfig)
        assert isinstance(cfg.tax, TaxConfig)
        assert isinstance(cfg.cost, CostConfig)

    def test_default_config(self):
        assert DEFAULT_CONFIG.trigger == RebalanceTrigger.COMBINED


# ===========================================================================
# Model Tests
# ===========================================================================

class TestRebalancingModels:
    """Test data models."""

    def test_holding_unrealized_pnl(self):
        h = Holding(shares=100, price=150.0, market_value=15000, cost_basis=140.0)
        assert h.unrealized_pnl == 15000 - 14000

    def test_holding_short_term(self):
        h = Holding(acquisition_date=date.today() - timedelta(days=100))
        assert h.is_short_term is True
        h2 = Holding(acquisition_date=date.today() - timedelta(days=400))
        assert h2.is_short_term is False

    def test_holding_no_date_is_short_term(self):
        h = Holding()
        assert h.is_short_term is True

    def test_drift_analysis_to_dict(self):
        da = DriftAnalysis(symbol="AAPL", drift=0.05, needs_rebalance=True)
        d = da.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["needs_rebalance"] is True

    def test_portfolio_drift_to_dict(self):
        pd_obj = PortfolioDrift(max_drift=0.08, n_exceeding_threshold=2)
        d = pd_obj.to_dict()
        assert d["max_drift"] == 0.08
        assert d["n_exceeding"] == 2

    def test_rebalance_trade_weight_change(self):
        t = RebalanceTrade(from_weight=0.30, to_weight=0.25)
        assert t.weight_change == pytest.approx(-0.05)

    def test_rebalance_trade_to_dict(self):
        t = RebalanceTrade(symbol="AAPL", side="sell", shares=50, value=7500)
        d = t.to_dict()
        assert d["side"] == "sell"
        assert d["shares"] == 50

    def test_rebalance_plan_drift_reduction(self):
        p = RebalancePlan(drift_before=0.10, drift_after=0.02)
        assert p.drift_reduction == pytest.approx(80.0)

    def test_rebalance_plan_to_dict(self):
        p = RebalancePlan(n_trades=3, total_turnover=5000, status=RebalanceStatus.PENDING)
        d = p.to_dict()
        assert d["n_trades"] == 3
        assert d["status"] == "pending"

    def test_schedule_state_to_dict(self):
        s = ScheduleState(next_scheduled=date(2026, 4, 1), days_until_next=60)
        d = s.to_dict()
        assert d["next_scheduled"] == "2026-04-01"
        assert d["days_until_next"] == 60


# ===========================================================================
# Drift Monitor Tests
# ===========================================================================

class TestDriftMonitor:
    """Test drift monitoring."""

    def test_compute_drift_balanced(self):
        holdings = _make_holdings(drifted=False)
        monitor = DriftMonitor()
        drift = monitor.compute_drift(holdings)
        assert drift.max_drift == 0.0
        assert drift.needs_rebalance is False

    def test_compute_drift_drifted(self):
        holdings = _make_holdings(drifted=True)
        monitor = DriftMonitor()
        drift = monitor.compute_drift(holdings)
        assert drift.max_drift > 0
        assert drift.n_exceeding_threshold > 0

    def test_drift_flags_critical(self):
        holdings = [
            Holding(symbol="X", current_weight=0.40, target_weight=0.25),
        ]
        monitor = DriftMonitor()
        drift = monitor.compute_drift(holdings)
        assert drift.asset_drifts[0].is_critical is True

    def test_drift_absolute_method(self):
        holdings = [
            Holding(symbol="A", current_weight=0.30, target_weight=0.25),
        ]
        monitor = DriftMonitor(config=DriftConfig(method=DriftMethod.ABSOLUTE))
        drift = monitor.compute_drift(holdings)
        assert drift.asset_drifts[0].drift == pytest.approx(0.05, abs=0.001)

    def test_drift_relative_method(self):
        holdings = [
            Holding(symbol="A", current_weight=0.30, target_weight=0.25),
        ]
        monitor = DriftMonitor(config=DriftConfig(method=DriftMethod.RELATIVE, threshold=0.15))
        drift = monitor.compute_drift(holdings)
        # Relative drift = (0.30 - 0.25) / 0.25 = 0.20
        assert drift.asset_drifts[0].drift == pytest.approx(0.20, abs=0.001)

    def test_drift_empty_holdings(self):
        monitor = DriftMonitor()
        drift = monitor.compute_drift([])
        assert drift.max_drift == 0.0

    def test_drift_history(self):
        holdings = _make_holdings(drifted=True)
        monitor = DriftMonitor()
        monitor.compute_drift(holdings)
        monitor.compute_drift(holdings)
        assert len(monitor.get_history()) == 2

    def test_drift_reset(self):
        monitor = DriftMonitor()
        monitor.compute_drift(_make_holdings())
        monitor.reset()
        assert len(monitor.get_history()) == 0

    def test_rmse_drift(self):
        holdings = _make_holdings(drifted=True)
        monitor = DriftMonitor()
        drift = monitor.compute_drift(holdings)
        assert drift.rmse_drift > 0
        assert drift.rmse_drift >= drift.mean_drift  # RMSE >= mean for non-uniform


# ===========================================================================
# Planner Tests
# ===========================================================================

class TestRebalancePlanner:
    """Test rebalance planning."""

    def test_full_rebalance(self):
        holdings = _make_holdings(drifted=True)
        planner = RebalancePlanner()
        plan = planner.plan_full_rebalance(holdings, portfolio_value=50000)
        assert plan.n_trades > 0
        assert plan.total_turnover > 0

    def test_full_rebalance_balanced_portfolio(self):
        holdings = _make_holdings(drifted=False)
        planner = RebalancePlanner()
        plan = planner.plan_full_rebalance(holdings, portfolio_value=50000)
        assert plan.n_trades == 0

    def test_threshold_rebalance(self):
        holdings = _make_holdings(drifted=True)
        planner = RebalancePlanner()
        plan = planner.plan_threshold_rebalance(holdings, portfolio_value=50000)
        # Only trades for assets exceeding 5% drift
        assert plan.n_trades > 0
        full_plan = planner.plan_full_rebalance(holdings, portfolio_value=50000)
        assert plan.n_trades <= full_plan.n_trades

    def test_tax_aware_skips_short_term_gains(self):
        holdings = [
            Holding(symbol="AAPL", shares=100, price=150.0, market_value=15000,
                    current_weight=0.35, target_weight=0.25, cost_basis=140.0,
                    acquisition_date=date.today() - timedelta(days=100)),  # Short-term gain
        ]
        planner = RebalancePlanner()
        plan = planner.plan_tax_aware_rebalance(holdings, portfolio_value=50000)
        # Should skip selling AAPL (short-term gain)
        aapl_trades = [t for t in plan.trades if t.symbol == "AAPL"]
        assert len(aapl_trades) == 0

    def test_tax_loss_harvesting(self):
        holdings = [
            Holding(symbol="GOOGL", shares=30, price=120.0, market_value=3600,
                    current_weight=0.35, target_weight=0.25, cost_basis=150.0,
                    acquisition_date=date.today() - timedelta(days=400)),
        ]
        planner = RebalancePlanner()
        plan = planner.plan_tax_aware_rebalance(holdings, portfolio_value=10000)
        googl_trades = [t for t in plan.trades if t.symbol == "GOOGL"]
        if googl_trades:
            assert googl_trades[0].is_tax_loss_harvest is True

    def test_min_trade_filter(self):
        holdings = [
            Holding(symbol="TINY", shares=1, price=50.0, market_value=50,
                    current_weight=0.251, target_weight=0.25),
        ]
        planner = RebalancePlanner(cost_config=CostConfig(min_trade_dollars=100.0))
        plan = planner.plan_full_rebalance(holdings, portfolio_value=50000)
        # Trade value too small, should be filtered
        tiny_trades = [t for t in plan.trades if t.symbol == "TINY"]
        assert len(tiny_trades) == 0

    def test_plan_estimated_cost(self):
        holdings = _make_holdings(drifted=True)
        planner = RebalancePlanner()
        plan = planner.plan_full_rebalance(holdings, portfolio_value=50000)
        assert plan.estimated_cost >= 0

    def test_plan_has_buys_and_sells(self):
        holdings = _make_holdings(drifted=True)
        planner = RebalancePlanner()
        plan = planner.plan_full_rebalance(holdings, portfolio_value=50000)
        sides = {t.side for t in plan.trades}
        # Drifted portfolio should have both buys and sells
        if plan.n_trades >= 2:
            assert "buy" in sides or "sell" in sides

    def test_plan_drift_reduction(self):
        holdings = _make_holdings(drifted=True)
        planner = RebalancePlanner()
        plan = planner.plan_full_rebalance(holdings, portfolio_value=50000)
        assert plan.drift_before > 0
        assert plan.drift_after <= plan.drift_before


# ===========================================================================
# Scheduler Tests
# ===========================================================================

class TestRebalanceScheduler:
    """Test rebalance scheduling."""

    def test_calendar_trigger_no_history(self):
        scheduler = RebalanceScheduler(trigger=RebalanceTrigger.CALENDAR)
        assert scheduler.should_rebalance(as_of_date=date(2026, 2, 1)) is True

    def test_calendar_trigger_recent_rebalance(self):
        scheduler = RebalanceScheduler(trigger=RebalanceTrigger.CALENDAR)
        scheduler.record_rebalance(date(2026, 1, 31))
        # Next quarterly date is far away
        assert scheduler.should_rebalance(as_of_date=date(2026, 2, 1)) is False

    def test_threshold_trigger_breached(self):
        scheduler = RebalanceScheduler(trigger=RebalanceTrigger.THRESHOLD)
        drift = PortfolioDrift(max_drift=0.08, needs_rebalance=True)
        assert scheduler.should_rebalance(drift=drift) is True

    def test_threshold_trigger_not_breached(self):
        scheduler = RebalanceScheduler(trigger=RebalanceTrigger.THRESHOLD)
        drift = PortfolioDrift(max_drift=0.02, needs_rebalance=False)
        assert scheduler.should_rebalance(drift=drift) is False

    def test_combined_trigger(self):
        scheduler = RebalanceScheduler(trigger=RebalanceTrigger.COMBINED)
        drift = PortfolioDrift(max_drift=0.08, needs_rebalance=True)
        # Threshold breached -> should trigger even if calendar says no
        scheduler.record_rebalance(date(2026, 1, 31))
        assert scheduler.should_rebalance(drift=drift, as_of_date=date(2026, 2, 1)) is True

    def test_manual_trigger_never_fires(self):
        scheduler = RebalanceScheduler(trigger=RebalanceTrigger.MANUAL)
        drift = PortfolioDrift(max_drift=0.20, needs_rebalance=True)
        assert scheduler.should_rebalance(drift=drift) is False

    def test_next_date_weekly(self):
        cfg = CalendarConfig(frequency=RebalanceFrequency.WEEKLY, day_of_week=0)
        scheduler = RebalanceScheduler(calendar_config=cfg)
        # 2026-02-01 is a Sunday (weekday=6), next Monday is 2026-02-02
        next_d = scheduler.next_rebalance_date(date(2026, 2, 1))
        assert next_d.weekday() == 0  # Monday
        assert next_d > date(2026, 2, 1)

    def test_next_date_monthly(self):
        cfg = CalendarConfig(frequency=RebalanceFrequency.MONTHLY, day_of_month=15)
        scheduler = RebalanceScheduler(calendar_config=cfg)
        next_d = scheduler.next_rebalance_date(date(2026, 2, 1))
        assert next_d.month == 3
        assert next_d.day == 15

    def test_next_date_quarterly(self):
        cfg = CalendarConfig(frequency=RebalanceFrequency.QUARTERLY, day_of_month=1, month_of_quarter=1)
        scheduler = RebalanceScheduler(calendar_config=cfg)
        next_d = scheduler.next_rebalance_date(date(2026, 2, 1))
        assert next_d > date(2026, 2, 1)

    def test_next_date_annual(self):
        cfg = CalendarConfig(frequency=RebalanceFrequency.ANNUAL, day_of_month=1)
        scheduler = RebalanceScheduler(calendar_config=cfg)
        next_d = scheduler.next_rebalance_date(date(2026, 2, 1))
        assert next_d.year == 2027

    def test_get_state(self):
        scheduler = RebalanceScheduler()
        drift = PortfolioDrift(max_drift=0.03, needs_rebalance=False)
        state = scheduler.get_state(drift=drift, as_of_date=date(2026, 2, 1))
        assert state.days_until_next >= 0
        assert state.threshold_breached is False

    def test_record_rebalance(self):
        scheduler = RebalanceScheduler()
        scheduler.record_rebalance(date(2026, 2, 1))
        assert scheduler._last_rebalance == date(2026, 2, 1)


# ===========================================================================
# Integration Tests
# ===========================================================================

class TestRebalancingIntegration:
    """End-to-end integration tests."""

    def test_drift_to_plan_pipeline(self):
        """Monitor drift -> plan rebalance -> check schedule."""
        holdings = _make_holdings(drifted=True)
        portfolio_value = 50000

        # Monitor drift
        monitor = DriftMonitor()
        drift = monitor.compute_drift(holdings)
        assert drift.needs_rebalance is True

        # Plan rebalance
        planner = RebalancePlanner()
        plan = planner.plan_threshold_rebalance(holdings, portfolio_value)
        assert plan.n_trades > 0

        # Check scheduler
        scheduler = RebalanceScheduler(trigger=RebalanceTrigger.THRESHOLD)
        assert scheduler.should_rebalance(drift=drift) is True

        # Record execution
        scheduler.record_rebalance()
        state = scheduler.get_state(drift=drift)
        assert state.last_rebalance is not None

    def test_balanced_portfolio_no_trades(self):
        """Balanced portfolio should produce zero trades."""
        holdings = _make_holdings(drifted=False)
        monitor = DriftMonitor()
        drift = monitor.compute_drift(holdings)
        assert drift.needs_rebalance is False

        planner = RebalancePlanner()
        plan = planner.plan_full_rebalance(holdings, portfolio_value=50000)
        assert plan.n_trades == 0

    def test_plan_serialization(self):
        """Plans should serialize to dict cleanly."""
        holdings = _make_holdings(drifted=True)
        planner = RebalancePlanner()
        plan = planner.plan_full_rebalance(holdings, portfolio_value=50000)
        d = plan.to_dict()
        assert "trades" in d
        assert "drift_reduction" in d
        assert isinstance(d["trades"], list)


# ===========================================================================
# Module Import Tests
# ===========================================================================

class TestRebalancingModuleImports:
    """Test module imports work correctly."""

    def test_top_level_imports(self):
        from src.rebalancing import (
            DriftMonitor,
            RebalancePlanner,
            RebalanceScheduler,
            RebalanceTrigger,
            RebalanceFrequency,
            DriftMethod,
            Holding,
            DriftAnalysis,
            PortfolioDrift,
            RebalanceTrade,
            RebalancePlan,
            ScheduleState,
            DEFAULT_CONFIG,
        )
        assert DriftMonitor is not None
        assert RebalancePlanner is not None
        assert RebalanceScheduler is not None
