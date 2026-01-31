"""Tests for Position Calculator module (PRD-35)."""

import pytest

from src.position_calculator.config import (
    StopType,
    InstrumentType,
    SizingMethod,
    DrawdownAction,
    SizingConfig,
    KellyConfig,
    HeatConfig,
    DrawdownConfig,
    PositionCalculatorConfig,
    DEFAULT_CONFIG,
)
from src.position_calculator.models import (
    SizingInputs,
    SizingResult,
    PositionRisk,
    PortfolioHeat,
    DrawdownState,
    SizingRecord,
)
from src.position_calculator.sizing import PositionSizingEngine
from src.position_calculator.heat import HeatTracker
from src.position_calculator.drawdown import DrawdownMonitor


# =========================================================================
# Config Tests
# =========================================================================


class TestConfig:
    def test_stop_types(self):
        assert len(StopType) == 3
        assert StopType.FIXED.value == "fixed"
        assert StopType.ATR_BASED.value == "atr_based"
        assert StopType.PERCENT.value == "percent"

    def test_instrument_types(self):
        assert len(InstrumentType) == 3
        assert InstrumentType.STOCK.value == "stock"
        assert InstrumentType.OPTION.value == "option"
        assert InstrumentType.FUTURE.value == "future"

    def test_sizing_methods(self):
        assert len(SizingMethod) == 6

    def test_drawdown_actions(self):
        assert len(DrawdownAction) == 4

    def test_default_sizing_config(self):
        cfg = SizingConfig()
        assert cfg.default_risk_pct == 1.0
        assert cfg.max_risk_pct == 3.0
        assert cfg.max_position_pct == 15.0
        assert cfg.round_down is True

    def test_default_kelly_config(self):
        cfg = KellyConfig()
        assert cfg.kelly_fraction == 0.25
        assert cfg.min_win_rate == 0.40
        assert cfg.min_trades == 30

    def test_default_heat_config(self):
        cfg = HeatConfig()
        assert cfg.max_heat_pct == 6.0
        assert cfg.warn_heat_pct == 4.0

    def test_default_drawdown_config(self):
        cfg = DrawdownConfig()
        assert cfg.max_drawdown_pct == 10.0
        assert cfg.reduce_at_pct == 8.0
        assert cfg.block_at_pct == 10.0

    def test_top_level_config(self):
        cfg = PositionCalculatorConfig()
        assert isinstance(cfg.sizing, SizingConfig)
        assert isinstance(cfg.kelly, KellyConfig)
        assert isinstance(cfg.heat, HeatConfig)
        assert isinstance(cfg.drawdown, DrawdownConfig)

    def test_default_config_singleton(self):
        assert DEFAULT_CONFIG.sizing.default_risk_pct == 1.0


# =========================================================================
# Model Tests
# =========================================================================


class TestModels:
    def test_sizing_inputs_risk_per_share(self):
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=150.0,
            stop_price=145.0,
        )
        assert inputs.risk_per_share == 5.0
        assert inputs.is_long is True
        assert inputs.risk_dollars == 1000.0  # 1% of 100k

    def test_sizing_inputs_short(self):
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=150.0,
            stop_price=155.0,
        )
        assert inputs.is_long is False
        assert inputs.risk_per_share == 5.0

    def test_sizing_inputs_dollar_override(self):
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=150.0,
            stop_price=145.0,
            risk_per_trade_dollars=500.0,
        )
        assert inputs.risk_dollars == 500.0

    def test_sizing_result_validity(self):
        result = SizingResult(position_size=100, risk_amount=500)
        assert result.is_valid is True

        result2 = SizingResult(position_size=0)
        assert result2.is_valid is False

        result3 = SizingResult(position_size=100, exceeds_portfolio_heat=True)
        assert result3.is_valid is False

    def test_position_risk_properties(self):
        pos = PositionRisk(
            symbol="AAPL",
            qty=100,
            entry_price=150.0,
            stop_price=145.0,
            current_price=152.0,
        )
        assert pos.risk_per_unit == 7.0   # |152 - 145|
        assert pos.initial_risk_per_unit == 5.0  # |150 - 145|
        assert pos.risk_dollars == 700.0   # 7 * 100
        assert pos.initial_risk_dollars == 500.0  # 5 * 100
        assert pos.market_value == 15_200.0
        assert pos.unrealized_pnl == 200.0
        assert pos.is_long is True

    def test_position_risk_option(self):
        pos = PositionRisk(
            symbol="AAPL 150C",
            qty=5,
            entry_price=3.50,
            stop_price=2.00,
            current_price=4.00,
            instrument_type=InstrumentType.OPTION,
            contract_multiplier=100,
        )
        assert pos.risk_dollars == 5 * 100 * abs(4.0 - 2.0)  # 1000
        assert pos.market_value == 5 * 100 * 4.0  # 2000

    def test_portfolio_heat_default(self):
        heat = PortfolioHeat()
        assert heat.total_heat_pct == 0.0
        assert heat.exceeds_limit is False

    def test_drawdown_state_days(self):
        state = DrawdownState(drawdown_pct=0)
        assert state.days_in_drawdown == 0

    def test_sizing_record(self):
        rec = SizingRecord(symbol="AAPL", position_size=200)
        assert len(rec.record_id) == 16
        assert rec.symbol == "AAPL"


# =========================================================================
# Sizing Engine Tests
# =========================================================================


class TestPositionSizingEngine:
    def test_fixed_risk_basic(self):
        engine = PositionSizingEngine()
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=50.0,
            stop_price=45.0,
        )
        result = engine.calculate(inputs)

        # Risk = 1% of 100k = $1000, risk/share = $5 => 200 shares
        # Position value = 200 * $50 = $10k = 10% < 15% max
        assert result.position_size == 200
        assert result.risk_amount == 1000.0
        assert result.risk_pct == pytest.approx(1.0)
        assert result.sizing_method == SizingMethod.FIXED_RISK

    def test_fixed_risk_short(self):
        engine = PositionSizingEngine()
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=25.0,
            stop_price=30.0,
            risk_per_trade_pct=2.0,
        )
        result = engine.calculate(inputs)

        # Risk = 2% of 100k = $2000, risk/share = $5 => 400 shares
        # Position value = 400 * $25 = $10k = 10% < 15% max
        assert result.position_size == 400
        assert result.risk_amount == 2000.0

    def test_fixed_risk_with_target(self):
        engine = PositionSizingEngine()
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=150.0,
            stop_price=145.0,
            target_price=165.0,
        )
        result = engine.calculate(inputs)

        # R:R = (165-150)/(150-145) = 15/5 = 3.0
        assert result.risk_reward_ratio == pytest.approx(3.0)

    def test_max_position_cap(self):
        engine = PositionSizingEngine(SizingConfig(
            default_risk_pct=10.0,
            max_risk_pct=10.0,
            max_position_pct=5.0,
        ))
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=10.0,
            stop_price=9.0,
        )
        result = engine.calculate(inputs)

        # 10% risk => 10000/1 = 10000 shares => $100k position
        # But max position = 5% = $5000 => 500 shares
        assert result.position_size == 500
        assert result.exceeds_max_position is True

    def test_zero_risk_per_share(self):
        engine = PositionSizingEngine()
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=150.0,
            stop_price=150.0,  # Same as entry
        )
        result = engine.calculate(inputs)
        assert result.position_size == 0
        assert len(result.warnings) > 0

    def test_negative_entry(self):
        engine = PositionSizingEngine()
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=-10.0,
            stop_price=-15.0,
        )
        result = engine.calculate(inputs)
        assert result.position_size == 0

    def test_dollar_risk_override(self):
        engine = PositionSizingEngine()
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=100.0,
            stop_price=95.0,
            risk_per_trade_dollars=250.0,
        )
        result = engine.calculate(inputs)

        # $250 risk / $5 per share = 50 shares
        assert result.position_size == 50
        assert result.risk_amount == 250.0

    def test_option_sizing(self):
        engine = PositionSizingEngine()
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=5.00,
            stop_price=3.00,
            instrument_type=InstrumentType.OPTION,
            contract_multiplier=100,
        )
        result = engine.calculate(inputs)

        # Risk = 1% of 100k = $1000
        # risk/contract = $2 * 100 = $200
        # => 5 contracts
        assert result.position_size == 5
        assert result.risk_amount == 1000.0

    def test_kelly_sizing(self):
        engine = PositionSizingEngine()
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=100.0,
            stop_price=95.0,
        )
        result = engine.calculate(
            inputs,
            method=SizingMethod.KELLY,
            win_rate=0.55,
            avg_win=0.08,
            avg_loss=0.04,
        )
        assert result.position_size > 0
        assert result.sizing_method == SizingMethod.KELLY

    def test_kelly_no_edge(self):
        engine = PositionSizingEngine()
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=100.0,
            stop_price=95.0,
        )
        result = engine.calculate(
            inputs,
            method=SizingMethod.KELLY,
            win_rate=0.30,  # Low win rate
            avg_win=0.04,
            avg_loss=0.08,  # Losses bigger than wins
        )
        # Should fall back to fixed risk
        assert result.position_size > 0
        assert len(result.warnings) > 0

    def test_kelly_missing_params(self):
        engine = PositionSizingEngine()
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=100.0,
            stop_price=95.0,
        )
        result = engine.calculate(inputs, method=SizingMethod.KELLY)
        # Falls back to fixed risk
        assert result.position_size > 0

    def test_half_kelly(self):
        engine = PositionSizingEngine()
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=100.0,
            stop_price=95.0,
        )
        full = engine.calculate(
            inputs,
            method=SizingMethod.KELLY,
            win_rate=0.60,
            avg_win=0.10,
            avg_loss=0.05,
        )
        half = engine.calculate(
            inputs,
            method=SizingMethod.HALF_KELLY,
            win_rate=0.60,
            avg_win=0.10,
            avg_loss=0.05,
        )
        # Half Kelly should be larger than quarter Kelly default
        assert half.position_size >= full.position_size

    def test_drawdown_adjustment(self):
        engine = PositionSizingEngine()
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=100.0,
            stop_price=95.0,
        )

        full = engine.calculate(inputs, drawdown_multiplier=1.0)
        reduced = engine.calculate(inputs, drawdown_multiplier=0.5)

        assert reduced.position_size <= full.position_size
        assert reduced.drawdown_adjusted is True

    def test_heat_warning(self):
        engine = PositionSizingEngine()
        inputs = SizingInputs(
            account_value=100_000,
            entry_price=100.0,
            stop_price=95.0,
        )
        result = engine.calculate(
            inputs,
            current_heat_pct=5.5,
            heat_limit_pct=6.0,
        )
        assert result.exceeds_portfolio_heat is True

    def test_compute_stop_percent(self):
        engine = PositionSizingEngine()
        stop = engine.compute_stop_price(100.0, "percent", is_long=True, percent=3.0)
        assert stop == 97.0

        stop_short = engine.compute_stop_price(100.0, "percent", is_long=False, percent=3.0)
        assert stop_short == 103.0

    def test_compute_stop_atr(self):
        engine = PositionSizingEngine()
        stop = engine.compute_stop_price(
            100.0, "atr_based", is_long=True, atr_value=2.5, atr_multiplier=2.0
        )
        assert stop == 95.0

    def test_compute_stop_fixed(self):
        engine = PositionSizingEngine()
        stop = engine.compute_stop_price(100.0, "fixed", fixed_stop=92.50)
        assert stop == 92.50


# =========================================================================
# Heat Tracker Tests
# =========================================================================


class TestHeatTracker:
    def test_empty_heat(self):
        tracker = HeatTracker()
        heat = tracker.compute_heat(100_000)
        assert heat.total_heat_pct == 0.0
        assert heat.n_positions == 0
        assert heat.exceeds_limit is False

    def test_single_position_heat(self):
        tracker = HeatTracker()
        tracker.add_position(PositionRisk(
            symbol="AAPL",
            qty=100,
            entry_price=150.0,
            stop_price=145.0,
            current_price=152.0,
        ))
        heat = tracker.compute_heat(100_000)

        # Risk = |152 - 145| * 100 = $700
        # Heat = 700/100000 * 100 = 0.7%
        assert heat.total_heat_pct == 0.7
        assert heat.total_heat_dollars == 700.0
        assert heat.n_positions == 1
        assert "AAPL" in heat.position_heats

    def test_multiple_positions(self):
        tracker = HeatTracker()
        tracker.add_position(PositionRisk(
            symbol="AAPL", qty=100, entry_price=150.0,
            stop_price=145.0, current_price=152.0,
        ))
        tracker.add_position(PositionRisk(
            symbol="MSFT", qty=50, entry_price=400.0,
            stop_price=390.0, current_price=405.0,
        ))
        heat = tracker.compute_heat(100_000)

        # AAPL: |152-145| * 100 = $700
        # MSFT: |405-390| * 50 = $750
        # Total = $1450 => 1.45%
        assert heat.total_heat_pct == 1.45
        assert heat.n_positions == 2

    def test_heat_exceeds_limit(self):
        tracker = HeatTracker(HeatConfig(max_heat_pct=1.0))
        tracker.add_position(PositionRisk(
            symbol="AAPL", qty=200, entry_price=150.0,
            stop_price=145.0, current_price=152.0,
        ))
        heat = tracker.compute_heat(100_000)

        # $1400 risk => 1.4% > 1.0% limit
        assert heat.exceeds_limit is True

    def test_heat_warning(self):
        tracker = HeatTracker(HeatConfig(max_heat_pct=6.0, warn_heat_pct=1.0))
        tracker.add_position(PositionRisk(
            symbol="AAPL", qty=200, entry_price=150.0,
            stop_price=145.0, current_price=152.0,
        ))
        heat = tracker.compute_heat(100_000)
        assert heat.at_warning is True
        assert heat.exceeds_limit is False

    def test_remove_position(self):
        tracker = HeatTracker()
        tracker.add_position(PositionRisk(
            symbol="AAPL", qty=100, entry_price=150.0,
            stop_price=145.0, current_price=152.0,
        ))
        assert tracker.n_positions == 1

        tracker.remove_position("AAPL")
        assert tracker.n_positions == 0

        heat = tracker.compute_heat(100_000)
        assert heat.total_heat_pct == 0.0

    def test_update_price(self):
        tracker = HeatTracker()
        tracker.add_position(PositionRisk(
            symbol="AAPL", qty=100, entry_price=150.0,
            stop_price=145.0, current_price=150.0,
        ))

        # Initially: risk = |150-145| * 100 = $500
        heat_before = tracker.compute_heat(100_000)
        assert heat_before.total_heat_pct == 0.5

        # Price moves away from stop
        tracker.update_price("AAPL", 160.0)
        heat_after = tracker.compute_heat(100_000)
        # Now: risk = |160-145| * 100 = $1500
        assert heat_after.total_heat_pct == 1.5

    def test_can_add_risk(self):
        tracker = HeatTracker(HeatConfig(max_heat_pct=2.0))
        tracker.add_position(PositionRisk(
            symbol="AAPL", qty=100, entry_price=150.0,
            stop_price=145.0, current_price=152.0,
        ))

        # Current heat: $700 = 0.7%
        assert tracker.can_add_risk(100_000, 1000.0)  # +1% => 1.7% < 2%
        assert not tracker.can_add_risk(100_000, 2000.0)  # +2% => 2.7% > 2%

    def test_max_additional_risk(self):
        tracker = HeatTracker(HeatConfig(max_heat_pct=2.0))
        tracker.add_position(PositionRisk(
            symbol="AAPL", qty=100, entry_price=150.0,
            stop_price=145.0, current_price=152.0,
        ))
        max_risk = tracker.max_additional_risk(100_000)
        # Available: 2.0 - 0.7 = 1.3% => $1300
        assert max_risk == pytest.approx(1300.0)

    def test_initial_risk_mode(self):
        tracker = HeatTracker(HeatConfig(include_unrealized=False))
        tracker.add_position(PositionRisk(
            symbol="AAPL", qty=100, entry_price=150.0,
            stop_price=145.0, current_price=180.0,
        ))
        heat = tracker.compute_heat(100_000)
        # Uses initial risk: |150-145| * 100 = $500 => 0.5%
        assert heat.total_heat_pct == 0.5

    def test_clear(self):
        tracker = HeatTracker()
        tracker.add_position(PositionRisk(
            symbol="AAPL", qty=100, entry_price=150.0,
            stop_price=145.0, current_price=152.0,
        ))
        tracker.clear()
        assert tracker.n_positions == 0


# =========================================================================
# Drawdown Monitor Tests
# =========================================================================


class TestDrawdownMonitor:
    def test_no_drawdown(self):
        monitor = DrawdownMonitor()
        state = monitor.update(100_000)
        assert state.drawdown_pct == 0.0
        assert state.size_multiplier == 1.0
        assert state.blocked is False

    def test_new_high(self):
        monitor = DrawdownMonitor()
        monitor.update(100_000)
        state = monitor.update(105_000)
        assert state.peak_value == 105_000
        assert state.drawdown_pct == 0.0

    def test_drawdown_calculation(self):
        monitor = DrawdownMonitor()
        monitor.update(100_000)
        state = monitor.update(95_000)

        assert state.peak_value == 100_000
        assert state.current_value == 95_000
        assert state.drawdown_pct == 5.0
        assert state.drawdown_dollars == 5_000.0

    def test_warning_threshold(self):
        monitor = DrawdownMonitor(DrawdownConfig(warn_drawdown_pct=5.0))
        monitor.update(100_000)
        state = monitor.update(94_000)

        assert state.at_warning is True
        assert state.drawdown_pct == 6.0

    def test_reduce_at_threshold(self):
        monitor = DrawdownMonitor(DrawdownConfig(
            reduce_at_pct=5.0,
            size_reduction_factor=0.5,
        ))
        monitor.update(100_000)

        # Above threshold
        state = monitor.update(94_000)  # 6% drawdown
        assert state.at_reduce is True
        assert state.size_multiplier == 0.5

    def test_block_at_limit(self):
        monitor = DrawdownMonitor(DrawdownConfig(
            block_at_pct=10.0,
            drawdown_action=DrawdownAction.REDUCE_SIZE,
        ))
        monitor.update(100_000)
        state = monitor.update(89_000)  # 11% drawdown

        assert state.blocked is True
        assert state.size_multiplier == 0.0
        assert state.at_limit is True

    def test_recovery(self):
        monitor = DrawdownMonitor()
        monitor.update(100_000)
        monitor.update(92_000)  # Drawdown

        state = monitor.update(100_000)  # Recover
        assert state.drawdown_pct == 0.0
        assert state.size_multiplier == 1.0
        assert state.blocked is False

    def test_new_peak_after_drawdown(self):
        monitor = DrawdownMonitor()
        monitor.update(100_000)
        monitor.update(95_000)
        state = monitor.update(110_000)

        assert state.peak_value == 110_000
        assert state.drawdown_pct == 0.0

    def test_is_blocked(self):
        monitor = DrawdownMonitor(DrawdownConfig(block_at_pct=5.0))
        monitor.update(100_000)
        monitor.update(94_000)
        assert monitor.is_blocked()

    def test_get_size_multiplier(self):
        monitor = DrawdownMonitor(DrawdownConfig(
            reduce_at_pct=5.0,
            block_at_pct=10.0,
            size_reduction_factor=0.5,
        ))
        monitor.update(100_000)

        # No drawdown
        assert monitor.get_size_multiplier() == 1.0

        # In reduce zone
        monitor.update(94_000)
        assert monitor.get_size_multiplier() == 0.5

        # Blocked
        monitor.update(89_000)
        assert monitor.get_size_multiplier() == 0.0

    def test_reset(self):
        monitor = DrawdownMonitor()
        monitor.update(100_000)
        monitor.update(90_000)

        monitor.reset(50_000)
        assert monitor.peak_value == 50_000
        assert monitor.current_value == 50_000

    def test_alert_only_action(self):
        monitor = DrawdownMonitor(DrawdownConfig(
            drawdown_action=DrawdownAction.ALERT_ONLY,
            reduce_at_pct=5.0,
            block_at_pct=10.0,
        ))
        monitor.update(100_000)
        state = monitor.update(85_000)  # 15% drawdown

        # Alert only: should not reduce or block
        assert state.size_multiplier == 1.0
        assert state.blocked is False
        assert state.at_limit is True


# =========================================================================
# Integration Tests
# =========================================================================


class TestIntegration:
    def test_sizing_with_heat_check(self):
        """Full workflow: size a trade, check heat, apply drawdown."""
        engine = PositionSizingEngine()
        tracker = HeatTracker()
        monitor = DrawdownMonitor()

        # Set up account
        account = 100_000
        monitor.update(account)

        # Existing position
        tracker.add_position(PositionRisk(
            symbol="AAPL", qty=100, entry_price=150.0,
            stop_price=145.0, current_price=152.0,
        ))

        # Calculate new trade
        heat = tracker.compute_heat(account)
        dd_state = monitor.get_state()

        inputs = SizingInputs(
            account_value=account,
            entry_price=50.0,
            stop_price=48.0,
            symbol="TSLA",
        )
        result = engine.calculate(
            inputs,
            current_heat_pct=heat.total_heat_pct,
            heat_limit_pct=heat.heat_limit_pct,
            drawdown_multiplier=dd_state.size_multiplier,
        )

        assert result.position_size > 0
        assert result.is_valid

    def test_sizing_blocked_by_drawdown(self):
        """Drawdown blocks new trades."""
        engine = PositionSizingEngine()
        monitor = DrawdownMonitor(DrawdownConfig(block_at_pct=5.0))

        monitor.update(100_000)
        monitor.update(94_000)  # 6% drawdown, blocked

        inputs = SizingInputs(
            account_value=94_000,
            entry_price=100.0,
            stop_price=95.0,
        )
        result = engine.calculate(
            inputs,
            drawdown_multiplier=monitor.get_size_multiplier(),
        )

        assert result.position_size == 0
        assert result.drawdown_adjusted is True

    def test_full_multi_asset_workflow(self):
        """Size stock, option, and future positions."""
        engine = PositionSizingEngine()

        # Stock
        stock_result = engine.calculate(SizingInputs(
            account_value=100_000,
            entry_price=50.0,
            stop_price=45.0,
            instrument_type=InstrumentType.STOCK,
        ))
        assert stock_result.position_size == 200

        # Option (100 multiplier)
        option_result = engine.calculate(SizingInputs(
            account_value=100_000,
            entry_price=5.00,
            stop_price=3.00,
            instrument_type=InstrumentType.OPTION,
            contract_multiplier=100,
        ))
        assert option_result.position_size == 5

        # Future (50 multiplier)
        future_result = engine.calculate(SizingInputs(
            account_value=100_000,
            entry_price=200.0,
            stop_price=180.0,
            instrument_type=InstrumentType.FUTURE,
            contract_multiplier=50,
        ))
        # Risk = $1000, risk/contract = 20*50 = $1000 => 1 contract
        # Position value = 1 * 200 * 50 = $10k = 10% < 15%
        assert future_result.position_size == 1


# =========================================================================
# Module Import Test
# =========================================================================


class TestModuleImports:
    def test_top_level_imports(self):
        from src.position_calculator import (
            PositionSizingEngine,
            HeatTracker,
            DrawdownMonitor,
            SizingInputs,
            SizingResult,
            PositionRisk,
            PortfolioHeat,
            DrawdownState,
            StopType,
            InstrumentType,
            SizingMethod,
        )
        assert PositionSizingEngine is not None
        assert HeatTracker is not None
        assert DrawdownMonitor is not None
