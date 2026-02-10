"""Tests for Advanced Risk Management (PRD-150)."""

import time
import pytest
from datetime import datetime, date, timezone, timedelta

from src.risk_manager.portfolio_risk import (
    PortfolioRiskConfig, PortfolioRiskMonitor, RiskLevel, RiskSnapshot, SECTOR_MAP,
)
from src.risk_manager.circuit_breaker import (
    CircuitBreakerConfig, CircuitBreakerState, CircuitBreakerStatus, TradingCircuitBreaker,
)
from src.risk_manager.kill_switch import (
    EnhancedKillSwitch, KillSwitchConfig, KillSwitchEvent, KillSwitchState,
)
from src.risk_manager.market_hours import (
    MarketCalendarConfig, MarketHoursEnforcer, MarketSession, MARKET_HOLIDAYS,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_positions(symbols_sides_values):
    """Create position dicts from (symbol, side, market_value) tuples."""
    return [
        {"symbol": s, "side": side, "market_value": mv, "qty": 100, "current_price": mv / 100}
        for s, side, mv in symbols_sides_values
    ]


# ── PortfolioRiskConfig ─────────────────────────────────────────────


class TestPortfolioRiskConfig:

    def test_defaults(self):
        cfg = PortfolioRiskConfig()
        assert cfg.max_gross_leverage == 2.0
        assert cfg.max_sector_pct == 30.0
        assert cfg.base_position_size_pct == 5.0

    def test_custom(self):
        cfg = PortfolioRiskConfig(max_gross_leverage=3.0, vix_critical_threshold=40.0)
        assert cfg.max_gross_leverage == 3.0
        assert cfg.vix_critical_threshold == 40.0


# ── SECTOR_MAP ───────────────────────────────────────────────────────


class TestSectorMap:

    def test_known_symbols(self):
        assert SECTOR_MAP["AAPL"] == "technology"
        assert SECTOR_MAP["JPM"] == "financials"
        assert SECTOR_MAP["XOM"] == "energy"
        assert SECTOR_MAP["BTC-USD"] == "crypto"

    def test_unknown_defaults_to_other(self):
        assert SECTOR_MAP.get("UNKNOWN_TICKER", "other") == "other"


# ── PortfolioRiskMonitor ────────────────────────────────────────────


class TestPortfolioRiskMonitor:

    def test_empty_portfolio(self):
        monitor = PortfolioRiskMonitor(equity=100_000)
        snapshot = monitor.assess([])
        assert snapshot.risk_level == RiskLevel.LOW
        assert snapshot.gross_leverage == 0.0
        assert len(snapshot.warnings) == 0

    def test_balanced_portfolio(self):
        # Spread evenly across 4 sectors so no sector exceeds 30%
        positions = _make_positions([
            ("AAPL", "long", 6_000),   # technology  ~25%
            ("JPM", "long", 6_000),    # financials  ~25%
            ("XOM", "long", 6_000),    # energy      ~25%
            ("JNJ", "long", 6_000),    # healthcare  ~25%
        ])
        monitor = PortfolioRiskMonitor(equity=100_000)
        snapshot = monitor.assess(positions)
        assert snapshot.gross_leverage < 1.0
        assert snapshot.risk_level == RiskLevel.LOW

    def test_high_leverage_warning(self):
        positions = _make_positions([
            ("AAPL", "long", 120_000),
            ("GOOG", "long", 100_000),
        ])
        monitor = PortfolioRiskMonitor(equity=100_000)
        snapshot = monitor.assess(positions)
        assert snapshot.gross_leverage > 2.0
        assert any("Gross leverage" in w for w in snapshot.warnings)

    def test_sector_concentration_warning(self):
        # All tech
        positions = _make_positions([
            ("AAPL", "long", 15_000),
            ("GOOG", "long", 15_000),
            ("META", "long", 15_000),
        ])
        monitor = PortfolioRiskMonitor(equity=100_000)
        snapshot = monitor.assess(positions)
        tech_pct = snapshot.sector_concentrations.get("technology", 0)
        assert tech_pct == 100.0  # All positions are tech

    def test_largest_position_warning(self):
        positions = _make_positions([
            ("AAPL", "long", 20_000),  # 20% > 15% limit
        ])
        monitor = PortfolioRiskMonitor(equity=100_000)
        snapshot = monitor.assess(positions)
        assert snapshot.largest_position_pct == 20.0
        assert any("Largest position" in w for w in snapshot.warnings)

    def test_vix_normal_sizing(self):
        monitor = PortfolioRiskMonitor()
        size = monitor.get_dynamic_size(vix=20.0)
        assert size == 5.0  # Base size

    def test_vix_low_sizing(self):
        monitor = PortfolioRiskMonitor()
        size = monitor.get_dynamic_size(vix=12.0)
        assert size == 6.0  # 1.2x base

    def test_vix_high_sizing(self):
        monitor = PortfolioRiskMonitor()
        size = monitor.get_dynamic_size(vix=30.0)
        assert size == 2.5  # 0.5x base

    def test_vix_critical_halt(self):
        monitor = PortfolioRiskMonitor()
        size = monitor.get_dynamic_size(vix=40.0)
        assert size == 0.0  # No new entries

    def test_approve_new_trade(self):
        monitor = PortfolioRiskMonitor(equity=100_000)
        approved, reason = monitor.approve_new_trade("AAPL", 5_000, "long", [])
        assert approved is True
        assert reason == "approved"

    def test_reject_oversized_trade(self):
        monitor = PortfolioRiskMonitor(equity=100_000)
        approved, reason = monitor.approve_new_trade("AAPL", 20_000, "long", [])
        assert approved is False
        assert "exceeds" in reason

    def test_reject_sector_concentration(self):
        positions = _make_positions([
            ("GOOG", "long", 25_000),
        ])
        monitor = PortfolioRiskMonitor(equity=100_000)
        approved, reason = monitor.approve_new_trade("AAPL", 10_000, "long", positions)
        # AAPL + GOOG = 35% tech > 30% limit
        assert approved is False
        assert "sector" in reason.lower()

    def test_snapshot_to_dict(self):
        snapshot = RiskSnapshot(risk_level=RiskLevel.ELEVATED, gross_leverage=1.5)
        d = snapshot.to_dict()
        assert d["risk_level"] == "elevated"
        assert d["gross_leverage"] == 1.5

    def test_history_tracking(self):
        monitor = PortfolioRiskMonitor(equity=100_000)
        monitor.assess([])
        monitor.assess([])
        assert len(monitor.get_history()) == 2

    def test_equity_setter(self):
        monitor = PortfolioRiskMonitor(equity=50_000)
        monitor.equity = 75_000
        assert monitor.equity == 75_000


# ── CircuitBreakerConfig ────────────────────────────────────────────


class TestCircuitBreakerConfig:

    def test_defaults(self):
        cfg = CircuitBreakerConfig()
        assert cfg.max_consecutive_losses == 3
        assert cfg.cooldown_seconds == 300
        assert cfg.half_open_size_multiplier == 0.5


# ── TradingCircuitBreaker ───────────────────────────────────────────


class TestTradingCircuitBreaker:

    def test_initial_state_closed(self):
        cb = TradingCircuitBreaker()
        assert cb.status == CircuitBreakerStatus.CLOSED
        assert cb.is_trading_allowed is True

    def test_trip_on_consecutive_losses(self):
        cb = TradingCircuitBreaker(CircuitBreakerConfig(max_consecutive_losses=3))
        cb.record_result(-100)
        cb.record_result(-100)
        assert cb.status == CircuitBreakerStatus.CLOSED
        cb.record_result(-100)  # 3rd loss
        assert cb.status == CircuitBreakerStatus.OPEN
        assert cb.is_trading_allowed is False

    def test_win_resets_consecutive(self):
        cb = TradingCircuitBreaker(CircuitBreakerConfig(max_consecutive_losses=3))
        cb.record_result(-100)
        cb.record_result(-100)
        cb.record_result(200)  # Win breaks the streak
        cb.record_result(-100)  # Start over
        assert cb.status == CircuitBreakerStatus.CLOSED

    def test_trip_on_daily_drawdown(self):
        cb = TradingCircuitBreaker(
            CircuitBreakerConfig(max_daily_drawdown_pct=5.0, max_consecutive_losses=100),
            equity=100_000,
        )
        cb.record_result(-3_000)
        assert cb.status == CircuitBreakerStatus.CLOSED
        cb.record_result(-2_500)  # Total -5500 = 5.5%
        assert cb.status == CircuitBreakerStatus.OPEN

    def test_cooldown_transitions_to_half_open(self):
        cb = TradingCircuitBreaker(CircuitBreakerConfig(
            max_consecutive_losses=1, cooldown_seconds=0  # Instant cooldown
        ))
        cb.record_result(-100)
        assert cb.state.status == CircuitBreakerStatus.OPEN
        # With 0 cooldown, next check should transition to HALF_OPEN
        assert cb.status == CircuitBreakerStatus.HALF_OPEN

    def test_half_open_win_resets(self):
        cb = TradingCircuitBreaker(CircuitBreakerConfig(
            max_consecutive_losses=1, cooldown_seconds=0, auto_reset_on_win=True,
        ))
        cb.record_result(-100)  # Trip
        _ = cb.status  # Trigger cooldown check → HALF_OPEN
        cb.record_result(50)  # Win in half-open
        assert cb.status == CircuitBreakerStatus.CLOSED

    def test_half_open_loss_retrips(self):
        cb = TradingCircuitBreaker(CircuitBreakerConfig(
            max_consecutive_losses=1, cooldown_seconds=0,
        ))
        cb.record_result(-100)  # Trip
        _ = cb.status  # → HALF_OPEN
        cb.record_result(-100)  # Loss in half-open → re-trip
        assert cb.state.status == CircuitBreakerStatus.OPEN

    def test_size_multiplier(self):
        cb = TradingCircuitBreaker(CircuitBreakerConfig(
            max_consecutive_losses=1, cooldown_seconds=0, half_open_size_multiplier=0.25,
        ))
        assert cb.get_size_multiplier() == 1.0  # CLOSED
        cb.record_result(-100)  # Trip → OPEN → HALF_OPEN (0 cooldown)
        assert cb.get_size_multiplier() == 0.25  # HALF_OPEN

    def test_manual_reset(self):
        cb = TradingCircuitBreaker(CircuitBreakerConfig(max_consecutive_losses=1))
        cb.record_result(-100)  # Trip
        cb.reset()
        assert cb.status == CircuitBreakerStatus.CLOSED

    def test_reset_daily(self):
        cb = TradingCircuitBreaker(CircuitBreakerConfig(max_consecutive_losses=1))
        cb.record_result(-100)  # Trip
        cb.reset_daily()
        assert cb.status == CircuitBreakerStatus.CLOSED
        assert cb.state.daily_losses == 0
        assert cb.state.daily_pnl == 0.0

    def test_trip_count(self):
        cb = TradingCircuitBreaker(CircuitBreakerConfig(
            max_consecutive_losses=1, cooldown_seconds=0, auto_reset_on_win=True,
        ))
        cb.record_result(-100)  # Trip 1
        _ = cb.status  # → HALF_OPEN
        cb.record_result(100)  # Reset
        cb.record_result(-100)  # Trip 2
        assert cb.state.trip_count == 2

    def test_state_to_dict(self):
        state = CircuitBreakerState(
            status=CircuitBreakerStatus.OPEN,
            consecutive_losses=3,
            trip_reason="3 consecutive losses",
        )
        d = state.to_dict()
        assert d["status"] == "open"
        assert d["consecutive_losses"] == 3


# ── KillSwitchConfig ────────────────────────────────────────────────


class TestKillSwitchConfig:

    def test_defaults(self):
        cfg = KillSwitchConfig()
        assert cfg.equity_floor == 25_000.0
        assert cfg.max_daily_drawdown_pct == 10.0
        assert cfg.require_manual_reset is True


# ── EnhancedKillSwitch ──────────────────────────────────────────────


class TestEnhancedKillSwitch:

    def test_initial_state_disarmed(self):
        ks = EnhancedKillSwitch()
        assert ks.state == KillSwitchState.DISARMED
        assert ks.is_triggered is False

    def test_arm_and_disarm(self):
        ks = EnhancedKillSwitch()
        ks.arm()
        assert ks.is_armed is True
        ks.disarm()
        assert ks.state == KillSwitchState.DISARMED

    def test_manual_trigger(self):
        ks = EnhancedKillSwitch()
        ks.arm()
        event = ks.trigger("Manual halt", "manual", 90_000, -5_000)
        assert ks.is_triggered is True
        assert ks.trigger_reason == "Manual halt"
        assert event.action == "triggered"

    def test_auto_trigger_equity_floor(self):
        ks = EnhancedKillSwitch(KillSwitchConfig(equity_floor=25_000))
        ks.arm()
        triggered = ks.check_conditions(equity=24_000, daily_pnl=-6_000)
        assert triggered is True
        assert ks.is_triggered is True
        assert "floor" in ks.trigger_reason.lower()

    def test_auto_trigger_daily_drawdown(self):
        ks = EnhancedKillSwitch(
            KillSwitchConfig(max_daily_drawdown_pct=10.0),
            initial_equity=100_000,
        )
        ks.arm()
        triggered = ks.check_conditions(equity=88_000, daily_pnl=-12_000)
        assert triggered is True
        assert "drawdown" in ks.trigger_reason.lower()

    def test_no_trigger_when_within_limits(self):
        ks = EnhancedKillSwitch(initial_equity=100_000)
        ks.arm()
        triggered = ks.check_conditions(equity=95_000, daily_pnl=-2_000)
        assert triggered is False
        assert ks.is_armed is True

    def test_no_trigger_when_disarmed(self):
        ks = EnhancedKillSwitch()
        # Not armed
        triggered = ks.check_conditions(equity=1_000)
        assert triggered is False

    def test_consecutive_errors_trigger(self):
        ks = EnhancedKillSwitch(KillSwitchConfig(max_consecutive_errors=3))
        ks.arm()
        ks.record_error()
        ks.record_error()
        assert ks.is_triggered is False
        triggered = ks.record_error()  # 3rd error
        assert triggered is True
        assert ks.is_triggered is True

    def test_success_resets_error_count(self):
        ks = EnhancedKillSwitch(KillSwitchConfig(max_consecutive_errors=3))
        ks.arm()
        ks.record_error()
        ks.record_error()
        ks.record_success()  # Reset
        ks.record_error()
        assert ks.is_triggered is False

    def test_disarm_after_trigger(self):
        ks = EnhancedKillSwitch()
        ks.arm()
        ks.trigger("test")
        ks.disarm()
        assert ks.state == KillSwitchState.DISARMED

    def test_event_history(self):
        ks = EnhancedKillSwitch()
        ks.arm()
        ks.trigger("test")
        ks.disarm()
        history = ks.get_history()
        assert len(history) == 3  # arm, trigger, disarm

    def test_event_to_dict(self):
        event = KillSwitchEvent(action="triggered", reason="test",
                                equity_at_event=90_000)
        d = event.to_dict()
        assert d["action"] == "triggered"
        assert d["equity_at_event"] == 90_000


# ── MarketCalendarConfig ────────────────────────────────────────────


class TestMarketCalendarConfig:

    def test_defaults(self):
        cfg = MarketCalendarConfig()
        assert cfg.allow_premarket is False
        assert cfg.allow_afterhours is False
        assert cfg.timezone_offset_hours == -5


# ── MARKET_HOLIDAYS ─────────────────────────────────────────────────


class TestMarketHolidays:

    def test_christmas_2025(self):
        assert date(2025, 12, 25) in MARKET_HOLIDAYS

    def test_thanksgiving_2026(self):
        assert date(2026, 11, 26) in MARKET_HOLIDAYS

    def test_regular_day_not_holiday(self):
        assert date(2025, 3, 15) not in MARKET_HOLIDAYS


# ── MarketHoursEnforcer ─────────────────────────────────────────────


class TestMarketHoursEnforcer:

    def _make_et_dt(self, hour, minute=0, day=3, month=2, year=2026):
        """Create a UTC datetime that maps to given ET time.
        ET offset = -5, so UTC = ET + 5.
        """
        return datetime(year, month, day, hour + 5, minute, tzinfo=timezone.utc)

    def test_regular_session(self):
        enforcer = MarketHoursEnforcer()
        # Tuesday 2026-02-03 at 10:30 ET = 15:30 UTC
        dt = self._make_et_dt(10, 30, day=3, month=2, year=2026)
        assert enforcer.get_session(dt) == MarketSession.REGULAR

    def test_pre_market_session(self):
        enforcer = MarketHoursEnforcer()
        # 7:00 AM ET
        dt = self._make_et_dt(7, 0, day=3, month=2, year=2026)
        assert enforcer.get_session(dt) == MarketSession.PRE_MARKET

    def test_after_hours_session(self):
        enforcer = MarketHoursEnforcer()
        # 5:00 PM ET
        dt = self._make_et_dt(17, 0, day=3, month=2, year=2026)
        assert enforcer.get_session(dt) == MarketSession.AFTER_HOURS

    def test_closed_overnight(self):
        enforcer = MarketHoursEnforcer()
        # 2:00 AM ET
        dt = self._make_et_dt(2, 0, day=3, month=2, year=2026)
        assert enforcer.get_session(dt) == MarketSession.CLOSED

    def test_closed_weekend(self):
        enforcer = MarketHoursEnforcer()
        # Saturday 2026-02-07 at 10:30 ET
        dt = self._make_et_dt(10, 30, day=7, month=2, year=2026)
        assert enforcer.get_session(dt) == MarketSession.CLOSED

    def test_closed_holiday(self):
        enforcer = MarketHoursEnforcer()
        # Christmas 2025 at 10:30 ET
        dt = self._make_et_dt(10, 30, day=25, month=12, year=2025)
        assert enforcer.get_session(dt) == MarketSession.CLOSED

    def test_trading_allowed_regular(self):
        enforcer = MarketHoursEnforcer()
        dt = self._make_et_dt(11, 0, day=3, month=2, year=2026)
        assert enforcer.is_trading_allowed(dt) is True

    def test_trading_blocked_premarket(self):
        enforcer = MarketHoursEnforcer()
        dt = self._make_et_dt(7, 0, day=3, month=2, year=2026)
        assert enforcer.is_trading_allowed(dt) is False

    def test_trading_allowed_premarket_when_enabled(self):
        cfg = MarketCalendarConfig(allow_premarket=True)
        enforcer = MarketHoursEnforcer(cfg)
        dt = self._make_et_dt(7, 0, day=3, month=2, year=2026)
        assert enforcer.is_trading_allowed(dt) is True

    def test_crypto_always_allowed(self):
        enforcer = MarketHoursEnforcer()
        # Saturday at 2 AM ET — stocks closed, crypto open
        dt = self._make_et_dt(2, 0, day=7, month=2, year=2026)
        assert enforcer.is_trading_allowed(dt, asset_type="crypto") is True

    def test_is_holiday(self):
        enforcer = MarketHoursEnforcer()
        dt = datetime(2025, 12, 25, 15, 0, tzinfo=timezone.utc)
        assert enforcer.is_holiday(dt) is True

    def test_is_early_close(self):
        enforcer = MarketHoursEnforcer()
        dt = datetime(2025, 12, 24, 15, 0, tzinfo=timezone.utc)
        assert enforcer.is_early_close(dt) is True

    def test_session_info(self):
        enforcer = MarketHoursEnforcer()
        dt = self._make_et_dt(11, 0, day=3, month=2, year=2026)
        info = enforcer.get_session_info(dt)
        assert info["session"] == "regular"
        assert info["is_open"] is True
        assert info["is_regular"] is True

    def test_next_open(self):
        enforcer = MarketHoursEnforcer()
        # Saturday at 10:00 ET
        dt = self._make_et_dt(10, 0, day=7, month=2, year=2026)
        next_open = enforcer.next_open(dt)
        assert next_open > dt
        # Should be Monday
        et_open = next_open + timedelta(hours=-5)
        assert et_open.weekday() == 0  # Monday

    def test_time_until_close_regular(self):
        enforcer = MarketHoursEnforcer()
        # 2:00 PM ET (2 hours before 4:00 PM close)
        dt = self._make_et_dt(14, 0, day=3, month=2, year=2026)
        minutes = enforcer.time_until_close(dt)
        assert minutes is not None
        assert minutes == pytest.approx(120.0, abs=1)

    def test_time_until_close_when_closed(self):
        enforcer = MarketHoursEnforcer()
        # Saturday
        dt = self._make_et_dt(10, 0, day=7, month=2, year=2026)
        assert enforcer.time_until_close(dt) is None


# ── Module imports ───────────────────────────────────────────────────


class TestRiskManagerModuleImports:

    def test_all_exports(self):
        from src.risk_manager import __all__
        assert "PortfolioRiskMonitor" in __all__
        assert "TradingCircuitBreaker" in __all__
        assert "EnhancedKillSwitch" in __all__
        assert "MarketHoursEnforcer" in __all__

    def test_import_star(self):
        from src.risk_manager import (
            PortfolioRiskConfig, PortfolioRiskMonitor, RiskLevel, RiskSnapshot, SECTOR_MAP,
            CircuitBreakerConfig, CircuitBreakerState, CircuitBreakerStatus, TradingCircuitBreaker,
            EnhancedKillSwitch, KillSwitchConfig, KillSwitchEvent, KillSwitchState,
            MarketCalendarConfig, MarketHoursEnforcer, MarketSession, MARKET_HOLIDAYS,
        )
        assert RiskLevel.LOW.value == "low"
        assert CircuitBreakerStatus.CLOSED.value == "closed"
        assert KillSwitchState.ARMED.value == "armed"
        assert MarketSession.REGULAR.value == "regular"
