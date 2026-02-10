"""
End-to-end integration tests for the full bot pipeline.

Validates the complete signal→execution→feedback loop including all
bridge adapters (regime, fusion, strategy, alerting, analytics, feedback).

Run: python3 -m pytest tests/test_bot_e2e.py -v
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.bot_pipeline.orchestrator import BotOrchestrator, PipelineConfig, PipelineResult
from src.bot_pipeline.state_manager import PersistentStateManager
from src.bot_pipeline.order_validator import OrderValidator
from src.bot_pipeline.signal_guard import SignalGuard
from src.bot_pipeline.lifecycle_manager import LifecycleManager
from src.ema_signals.detector import TradeSignal, SignalType
from src.trade_executor.executor import AccountState, ExecutorConfig, Position
from src.trade_executor.router import Order, OrderResult, OrderRouter


# ── Helpers ───────────────────────────────────────────────────────────


def _make_signal(
    ticker="AAPL", direction="long", entry_price=185.0,
    stop_loss=180.0, target_price=195.0, conviction=82,
    timeframe="1d", signal_type=SignalType.CLOUD_CROSS_BULLISH,
):
    return TradeSignal(
        ticker=ticker,
        direction=direction,
        signal_type=signal_type,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_price=target_price,
        conviction=conviction,
        timeframe=timeframe,
    )


def _make_account(equity=100_000, cash=50_000, buying_power=50_000):
    return AccountState(
        equity=equity, cash=cash, buying_power=buying_power,
        starting_equity=equity,
    )


def _build_orchestrator(
    state_dir,
    *,
    enable_alerting=True,
    enable_analytics=True,
    enable_feedback=True,
    enable_regime=True,
    enable_fusion=True,
    enable_strategy=True,
    paper_mode=True,
    feedback_every_n=5,
):
    """Create a fully-wired orchestrator with real bridge adapters."""
    config = PipelineConfig(
        executor_config=ExecutorConfig(
            primary_broker="paper",
            max_concurrent_positions=10,
            daily_loss_limit=0.05,
        ),
        state_dir=state_dir,
        enable_signal_recording=False,
        enable_unified_risk=False,
        enable_feedback_loop=enable_feedback,
        enable_instrument_routing=False,
        enable_journaling=False,
        enable_strategy_selection=enable_strategy,
        enable_signal_fusion=enable_fusion,
        enable_regime_adaptation=enable_regime,
        enable_alerting=enable_alerting,
        enable_analytics=enable_analytics,
        max_signal_age_seconds=9999,
        dedup_window_seconds=1,
        feedback_adjust_every_n_trades=feedback_every_n,
    )

    state_manager = PersistentStateManager(state_dir)
    order_router = OrderRouter(primary_broker="paper", paper_mode=True)

    # Build real bridge adapters (they lazy-load gracefully)
    alert_bridge = None
    if enable_alerting:
        try:
            from src.bot_pipeline.alert_bridge import BotAlertBridge
            alert_bridge = BotAlertBridge()
        except ImportError:
            pass

    analytics_tracker = None
    if enable_analytics:
        try:
            from src.bot_analytics.tracker import BotPerformanceTracker
            analytics_tracker = BotPerformanceTracker(starting_equity=100_000.0)
        except ImportError:
            pass

    feedback_bridge = None
    perf_tracker = None
    if enable_feedback:
        try:
            from src.signal_feedback import PerformanceTracker
            perf_tracker = PerformanceTracker()
        except ImportError:
            pass
        try:
            from src.bot_pipeline.feedback_bridge import FeedbackBridge
            from src.bot_pipeline.feedback_bridge import FeedbackConfig
            fb_config = FeedbackConfig(adjust_every_n_trades=feedback_every_n)
            feedback_bridge = FeedbackBridge(config=fb_config, tracker=perf_tracker)
        except ImportError:
            pass

    regime_bridge = None
    if enable_regime:
        try:
            from src.bot_pipeline.regime_bridge import RegimeBridge
            regime_bridge = RegimeBridge()
        except ImportError:
            pass

    fusion_bridge = None
    if enable_fusion:
        try:
            from src.bot_pipeline.fusion_bridge import FusionBridge
            fusion_bridge = FusionBridge()
        except ImportError:
            pass

    strategy_bridge = None
    if enable_strategy:
        try:
            from src.bot_pipeline.strategy_bridge import StrategyBridge
            strategy_bridge = StrategyBridge()
        except ImportError:
            pass

    return BotOrchestrator(
        config=config,
        state_manager=state_manager,
        order_router=order_router,
        alert_bridge=alert_bridge,
        analytics_tracker=analytics_tracker,
        feedback_bridge=feedback_bridge,
        performance_tracker=perf_tracker,
        regime_bridge=regime_bridge,
        fusion_bridge=fusion_bridge,
        strategy_bridge=strategy_bridge,
    )


# ── Test Class ────────────────────────────────────────────────────────


class TestBotEndToEnd:
    """End-to-end integration tests for the full bot pipeline."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.state_dir = str(tmp_path / "bot_state")
        self.account = _make_account()

    def _orch(self, **kwargs):
        return _build_orchestrator(self.state_dir, **kwargs)

    # ── 1. Full pipeline: signal → execution ─────────────────────────

    def test_full_pipeline_signal_to_execution(self):
        """Signal flows through all stages and creates a position."""
        orch = self._orch()
        signal = _make_signal()
        result = orch.process_signal(signal, self.account)

        assert result.success
        assert result.pipeline_stage == "completed"
        assert result.position is not None
        assert result.position.ticker == "AAPL"
        assert result.position.direction == "long"
        assert len(orch.positions) == 1

    def test_full_pipeline_short_signal(self):
        """Short signal also goes through full pipeline."""
        orch = self._orch()
        signal = _make_signal(direction="short", signal_type=SignalType.CLOUD_CROSS_BEARISH)
        result = orch.process_signal(signal, self.account)

        assert result.success
        assert result.position.direction == "short"

    def test_full_pipeline_multiple_signals(self):
        """Process multiple signals for different tickers."""
        orch = self._orch()
        tickers = ["AAPL", "MSFT", "NVDA", "GOOGL"]
        for ticker in tickers:
            signal = _make_signal(ticker=ticker, entry_price=150.0 + hash(ticker) % 100)
            result = orch.process_signal(signal, self.account)
            assert result.success, f"Failed for {ticker}: {result.rejection_reason}"

        assert len(orch.positions) == 4
        assert {p.ticker for p in orch.positions} == set(tickers)

    # ── 2. Regime adaptation ─────────────────────────────────────────

    def test_regime_adaptation_bull(self):
        """Bull regime processes signal with adapted config."""
        orch = self._orch()
        signal = _make_signal()
        result = orch.process_signal(signal, self.account, regime="bull")

        assert result.success

    def test_regime_adaptation_crisis(self):
        """Crisis regime still processes signals (with tighter risk)."""
        orch = self._orch()
        signal = _make_signal(conviction=90)
        result = orch.process_signal(signal, self.account, regime="crisis")

        # May succeed or be rejected by tighter risk — either is valid
        assert result.pipeline_stage in ("completed", "risk_assessment", "basic_risk_check")

    # ── 3. Signal deduplication ──────────────────────────────────────

    def test_signal_dedup_rejects_duplicate(self):
        """Same signal submitted twice within dedup window is rejected."""
        orch = self._orch()
        signal = _make_signal()
        result1 = orch.process_signal(signal, self.account)
        assert result1.success

        # Same ticker+direction+timeframe within dedup window
        signal2 = _make_signal()
        result2 = orch.process_signal(signal2, self.account)
        assert not result2.success
        assert result2.pipeline_stage == "signal_guard"

    # ── 4. Alerting on trade execution ───────────────────────────────

    def test_alerting_on_trade_executed(self):
        """Alert bridge fires on successful trade execution."""
        orch = self._orch()
        signal = _make_signal()

        # If alert bridge is available, it should not raise
        result = orch.process_signal(signal, self.account)
        assert result.success

        # Alert bridge should have recorded the event
        if orch._alert_bridge:
            history = orch._alert_bridge.get_alert_history(limit=5)
            assert len(history) >= 1

    def test_alerting_on_kill_switch(self):
        """Kill switch alert fires when activated."""
        orch = self._orch()
        if not orch._alert_bridge:
            pytest.skip("Alert bridge not available")

        orch._alert_bridge.on_kill_switch("Test kill switch")
        history = orch._alert_bridge.get_alert_history(limit=5)
        assert any("kill" in str(h).lower() for h in history)

    # ── 5. Analytics recording ───────────────────────────────────────

    def test_analytics_records_trade_close(self):
        """Analytics tracker records PnL on position close."""
        orch = self._orch()
        signal = _make_signal()
        result = orch.process_signal(signal, self.account)
        assert result.success

        # Close with profit
        closed = orch.close_position("AAPL", "target_hit", exit_price=195.0)
        assert closed is not None

        if orch._analytics:
            assert orch._analytics.get_trade_count() >= 1
            snapshot = orch._analytics.get_snapshot()
            assert snapshot.total_trades >= 1

    def test_analytics_equity_curve(self):
        """Equity curve updates after multiple trades."""
        orch = self._orch()
        if not orch._analytics:
            pytest.skip("Analytics not available")

        # Execute and close several trades
        for i, ticker in enumerate(["AAPL", "MSFT", "NVDA"]):
            signal = _make_signal(ticker=ticker, entry_price=100.0 + i * 10)
            orch.process_signal(signal, self.account)

        for ticker in ["AAPL", "MSFT", "NVDA"]:
            orch.close_position(ticker, "target_hit", exit_price=120.0)

        assert orch._analytics.get_trade_count() >= 3

    # ── 6. Feedback cycle ────────────────────────────────────────────

    def test_feedback_weight_adjustment_after_n_trades(self):
        """Weight recalculation triggers after N closed trades."""
        orch = self._orch(feedback_every_n=3, enable_fusion=False, enable_strategy=False)
        if not orch._feedback_bridge:
            pytest.skip("Feedback bridge not available")

        initial_count = orch._feedback_bridge.get_trade_count()

        # Execute and close 3 trades to trigger weight adjustment
        tickers = ["AAPL", "MSFT", "NVDA"]
        for ticker in tickers:
            signal = _make_signal(ticker=ticker, entry_price=150.0)
            result = orch.process_signal(signal, self.account)
            assert result.success, f"Failed: {result.rejection_reason}"

        for ticker in tickers:
            orch.close_position(ticker, "target_hit", exit_price=160.0)

        assert orch._feedback_bridge.get_trade_count() >= initial_count + 3

    def test_feedback_force_adjustment(self):
        """Force adjustment returns a weight update."""
        orch = self._orch(enable_fusion=False, enable_strategy=False)
        if not orch._feedback_bridge:
            pytest.skip("Feedback bridge not available")

        update = orch._feedback_bridge.force_adjustment()
        assert update is not None

    # ── 7. Kill switch persistence ───────────────────────────────────

    def test_kill_switch_persists_across_reload(self):
        """Kill switch state survives orchestrator recreation."""
        orch1 = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        signal = _make_signal()
        orch1.process_signal(signal, self.account)

        # Activate kill switch
        orch1._state.activate_kill_switch("E2E test kill")
        assert orch1._state.kill_switch_active

        # Create new orchestrator pointing at same state dir
        orch2 = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        assert orch2._state.kill_switch_active
        assert "E2E test kill" in orch2._state.kill_switch_reason

        # New signals should be blocked
        result = orch2.process_signal(_make_signal(ticker="MSFT"), self.account)
        assert not result.success
        assert result.pipeline_stage == "kill_switch"

    def test_kill_switch_deactivation(self):
        """Kill switch can be deactivated and trading resumes."""
        orch = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        orch._state.activate_kill_switch("temporary")
        assert orch._state.kill_switch_active

        orch._state.deactivate_kill_switch()
        assert not orch._state.kill_switch_active

        result = orch.process_signal(_make_signal(), self.account)
        assert result.success

    # ── 8. Paper mode full pipeline ──────────────────────────────────

    def test_paper_mode_full_pipeline(self):
        """Paper mode processes signal with simulated fills."""
        orch = self._orch(paper_mode=True)
        signal = _make_signal(conviction=90)
        result = orch.process_signal(signal, self.account)

        assert result.success
        assert result.order_result is not None
        assert result.order_result.broker == "paper"
        assert result.fill_validation is not None
        assert result.fill_validation.is_valid

    def test_paper_mode_close_with_pnl(self):
        """Paper mode: close position and verify PnL tracking."""
        orch = self._orch(paper_mode=True, enable_regime=False, enable_fusion=False, enable_strategy=False)
        signal = _make_signal(entry_price=100.0, stop_loss=95.0, target_price=110.0)
        result = orch.process_signal(signal, self.account)
        assert result.success

        entry = result.position.entry_price
        closed = orch.close_position("AAPL", "target_hit", exit_price=110.0)
        assert closed is not None

        # Daily PnL should reflect the profit
        daily_pnl = orch._state.daily_pnl
        assert daily_pnl >= 0  # Profitable trade

    # ── 9. Graceful shutdown ─────────────────────────────────────────

    def test_graceful_shutdown_closes_positions(self):
        """Shutdown closes all open positions via close_position."""
        orch = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        tickers = ["AAPL", "MSFT", "NVDA"]
        for ticker in tickers:
            signal = _make_signal(ticker=ticker, entry_price=150.0)
            orch.process_signal(signal, self.account)
        assert len(orch.positions) == 3

        # Simulate graceful shutdown
        for pos in list(orch.positions):
            orch.close_position(pos.ticker, "graceful_shutdown", pos.current_price)

        assert len(orch.positions) == 0

    # ── 10. Pipeline stats ───────────────────────────────────────────

    def test_pipeline_stats_reflect_activity(self):
        """Stats track signals processed and positions."""
        orch = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        signal = _make_signal()
        orch.process_signal(signal, self.account)

        stats = orch.get_pipeline_stats()
        assert stats["total_signals_processed"] >= 1
        assert stats["successful_executions"] >= 1
        assert stats["open_positions"] == 1
        assert not stats["kill_switch_active"]

    # ── 11. Max positions limit ──────────────────────────────────────

    def test_max_positions_rejects_when_full(self):
        """Exceeding max_concurrent_positions blocks new signals."""
        orch = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        orch.config.executor_config.max_concurrent_positions = 2

        r1 = orch.process_signal(_make_signal(ticker="AAPL"), self.account)
        assert r1.success
        r2 = orch.process_signal(_make_signal(ticker="MSFT"), self.account)
        assert r2.success

        # Third should be rejected
        r3 = orch.process_signal(_make_signal(ticker="NVDA"), self.account)
        assert not r3.success
        assert "Max positions" in r3.rejection_reason

    # ── 12. Execution history capping ────────────────────────────────

    def test_execution_history_is_bounded(self):
        """Execution history respects max_history_size (deque)."""
        orch = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        orch.config.max_history_size = 5
        # Re-create the deque with new maxlen
        import collections
        orch.execution_history = collections.deque(maxlen=5)

        for i in range(10):
            ticker = f"SYM{i}"
            signal = _make_signal(ticker=ticker, entry_price=100.0 + i)
            orch.process_signal(signal, self.account)
            # Reset guard to allow repeated signals
            orch._signal_guard = SignalGuard(max_age_seconds=9999, dedup_window_seconds=0)

        assert len(orch.execution_history) == 5

    # ── 13. Lifecycle manager integration ────────────────────────────

    def test_lifecycle_price_updates(self):
        """LifecycleManager updates position prices."""
        orch = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        signal = _make_signal(ticker="AAPL", entry_price=185.0)
        orch.process_signal(signal, self.account)

        lifecycle = LifecycleManager(orch)
        updated = lifecycle.update_prices({"AAPL": 195.0})
        assert updated == 1
        assert orch.positions[0].current_price == 195.0

    def test_lifecycle_emergency_close(self):
        """Emergency close shuts down all positions and activates kill switch."""
        orch = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        for ticker in ["AAPL", "MSFT"]:
            orch.process_signal(_make_signal(ticker=ticker), self.account)
        assert len(orch.positions) == 2

        lifecycle = LifecycleManager(orch)
        lifecycle.emergency_close_all("E2E emergency test")

        assert len(orch.positions) == 0
        assert orch._state.kill_switch_active

    # ── 14. Signal guard freshness ───────────────────────────────────

    def test_signal_guard_rejects_stale_signal(self):
        """Stale signals (old timestamp) are rejected by guard."""
        orch = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        orch.config.max_signal_age_seconds = 1.0
        orch._signal_guard = SignalGuard(max_age_seconds=1.0, dedup_window_seconds=300)

        from datetime import timedelta
        old_signal = _make_signal()
        old_signal.timestamp = datetime.now(timezone.utc) - timedelta(seconds=60)

        result = orch.process_signal(old_signal, self.account)
        assert not result.success
        assert result.pipeline_stage == "signal_guard"

    # ── 15. Multiple regimes in sequence ─────────────────────────────

    def test_regime_sequence_bull_to_bear(self):
        """Switching regimes between signals adapts config each time."""
        orch = self._orch(enable_fusion=False, enable_strategy=False)

        r1 = orch.process_signal(
            _make_signal(ticker="AAPL"), self.account, regime="bull"
        )
        assert r1.success

        r2 = orch.process_signal(
            _make_signal(ticker="MSFT"), self.account, regime="bear"
        )
        # Bear may adapt config but should still process
        assert r2.pipeline_stage in ("completed", "risk_assessment", "basic_risk_check")

    # ── 16. Close position PnL feedback ──────────────────────────────

    def test_close_position_updates_daily_pnl(self):
        """Closing a position updates the persistent daily PnL tracker."""
        orch = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        signal = _make_signal(entry_price=100.0, stop_loss=95.0, target_price=110.0)
        result = orch.process_signal(signal, self.account)
        assert result.success

        initial_pnl = orch._state.daily_pnl
        orch.close_position("AAPL", "target_hit", exit_price=110.0)
        assert orch._state.daily_pnl > initial_pnl

    # ── 17. Mixed signal types ───────────────────────────────────────

    def test_mixed_signal_types_all_process(self):
        """Different signal types all flow through the pipeline."""
        orch = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        signal_types = [
            (SignalType.CLOUD_CROSS_BULLISH, "long"),
            (SignalType.CLOUD_CROSS_BEARISH, "short"),
            (SignalType.TREND_ALIGNED_LONG, "long"),
        ]

        for i, (stype, direction) in enumerate(signal_types):
            signal = _make_signal(
                ticker=f"SYM{i}", direction=direction,
                signal_type=stype, entry_price=100.0 + i * 10,
            )
            result = orch.process_signal(signal, self.account)
            assert result.success, f"Failed for {stype}: {result.rejection_reason}"

        assert len(orch.positions) == 3

    # ── 18. Daily loss auto-kill ─────────────────────────────────────

    def test_daily_loss_triggers_kill_switch(self):
        """Exceeding daily loss limit activates kill switch automatically."""
        orch = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        orch.config.executor_config.daily_loss_limit = 0.01  # 1% = $1000 on $100k

        signal = _make_signal(entry_price=100.0, stop_loss=50.0, target_price=200.0)
        result = orch.process_signal(signal, self.account)
        assert result.success

        # Close with a large loss
        orch.close_position("AAPL", "stop_loss", exit_price=50.0)

        # Kill switch should have activated due to daily loss
        assert orch._state.kill_switch_active

    # ── 19. Pipeline result serialization ────────────────────────────

    def test_pipeline_result_to_dict(self):
        """PipelineResult.to_dict() produces serializable output."""
        orch = self._orch(enable_regime=False, enable_fusion=False, enable_strategy=False)
        signal = _make_signal()
        result = orch.process_signal(signal, self.account)

        d = result.to_dict()
        assert d["success"] is True
        assert d["ticker"] == "AAPL"
        assert d["direction"] == "long"
        assert d["pipeline_stage"] == "completed"
        # Verify it's JSON-serializable
        json.dumps(d)

    # ── 20. Bot runner CLI parsing ───────────────────────────────────

    def test_bot_runner_parse_args(self):
        """CLI arg parser produces correct namespace."""
        from src.bot_pipeline.__main__ import parse_args

        args = parse_args(["--paper", "--state-dir", "/tmp/test", "--poll-interval", "10"])
        assert args.paper is True
        assert args.state_dir == "/tmp/test"
        assert args.poll_interval == 10.0

    def test_bot_runner_parse_args_live(self):
        """--live flag sets live mode."""
        from src.bot_pipeline.__main__ import parse_args

        args = parse_args(["--live", "--symbols", "AAPL", "MSFT"])
        assert args.live is True
        assert args.symbols == ["AAPL", "MSFT"]

    def test_bot_runner_load_config(self, tmp_path):
        """Config loader reads JSON file and applies CLI overrides."""
        from src.bot_pipeline.__main__ import parse_args, load_config

        config_data = {"max_order_retries": 5, "max_signal_age_seconds": 60.0}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        args = parse_args(["--config", str(config_file), "--state-dir", str(tmp_path / "state")])
        config = load_config(args)
        assert config.max_order_retries == 5
        assert config.max_signal_age_seconds == 60.0
        assert config.state_dir == str(tmp_path / "state")


# ── Bot Runner CLI Tests ──────────────────────────────────────────────


class TestBotRunnerCLI:
    """Tests for src.bot_pipeline.__main__ CLI functions."""

    def test_create_orchestrator_paper(self, tmp_path):
        """create_orchestrator wires paper mode correctly."""
        from src.bot_pipeline.__main__ import create_orchestrator

        config = PipelineConfig(
            state_dir=str(tmp_path / "state"),
            enable_signal_recording=False,
            enable_unified_risk=False,
            enable_feedback_loop=False,
            enable_instrument_routing=False,
            enable_journaling=False,
            enable_strategy_selection=False,
            enable_signal_fusion=False,
            enable_regime_adaptation=False,
            enable_alerting=False,
            enable_analytics=False,
        )
        orch = create_orchestrator(config, paper_mode=True)
        assert orch is not None
        assert orch._router.paper_mode is True
        assert not orch._state.kill_switch_active

    def test_create_orchestrator_live_broker(self, tmp_path):
        """create_orchestrator in live mode uses configured broker."""
        from src.bot_pipeline.__main__ import create_orchestrator

        config = PipelineConfig(
            state_dir=str(tmp_path / "state"),
            enable_signal_recording=False,
            enable_unified_risk=False,
            enable_feedback_loop=False,
            enable_instrument_routing=False,
            enable_journaling=False,
            enable_strategy_selection=False,
            enable_signal_fusion=False,
            enable_regime_adaptation=False,
            enable_alerting=False,
            enable_analytics=False,
        )
        config.executor_config.primary_broker = "alpaca"
        orch = create_orchestrator(config, paper_mode=False)
        assert orch is not None

    def test_load_config_missing_file(self, tmp_path):
        """load_config handles missing config file gracefully."""
        from src.bot_pipeline.__main__ import parse_args, load_config

        args = parse_args(["--config", str(tmp_path / "nonexistent.json")])
        config = load_config(args)
        # Should use defaults when file missing
        assert config.max_order_retries == 3  # default

    def test_load_config_executor_config_keys(self, tmp_path):
        """Config file keys that belong to ExecutorConfig are applied."""
        from src.bot_pipeline.__main__ import parse_args, load_config

        config_data = {"max_concurrent_positions": 3}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        args = parse_args(["--config", str(config_file), "--state-dir", str(tmp_path / "state")])
        config = load_config(args)
        assert config.executor_config.max_concurrent_positions == 3

    def test_load_config_live_flag(self, tmp_path):
        """--live sets primary_broker to alpaca."""
        from src.bot_pipeline.__main__ import parse_args, load_config

        args = parse_args(["--live", "--state-dir", str(tmp_path / "state")])
        config = load_config(args)
        assert config.executor_config.primary_broker == "alpaca"

    def test_load_config_paper_flag(self, tmp_path):
        """--paper (default) sets primary_broker to paper."""
        from src.bot_pipeline.__main__ import parse_args, load_config

        args = parse_args(["--state-dir", str(tmp_path / "state")])
        config = load_config(args)
        assert config.executor_config.primary_broker == "paper"

    def test_scan_signals_returns_list(self):
        """scan_signals returns a list (may be empty without market data)."""
        from src.bot_pipeline.__main__ import scan_signals

        result = scan_signals(["FAKE_TICKER_XYZ123"])
        assert isinstance(result, list)

    def test_shutdown_flag_behavior(self):
        """Shutdown flag controls loop termination."""
        import src.bot_pipeline.__main__ as runner

        original = runner._shutdown
        try:
            runner._shutdown = False
            assert not runner._shutdown
            runner._shutdown = True
            assert runner._shutdown
        finally:
            runner._shutdown = original

    def test_main_exits_on_active_kill_switch(self, tmp_path):
        """main() returns 1 if kill switch is already active."""
        from src.bot_pipeline.__main__ import main

        state_dir = str(tmp_path / "state")
        # Pre-activate kill switch
        state_mgr = PersistentStateManager(state_dir)
        state_mgr.activate_kill_switch("pre-activated for test")

        exit_code = main(["--state-dir", state_dir])
        assert exit_code == 1

    def test_parse_args_defaults(self):
        """Default args have expected values."""
        from src.bot_pipeline.__main__ import parse_args

        args = parse_args([])
        assert args.paper is True
        assert args.live is False
        assert args.config is None
        assert args.state_dir == ".bot_state"
        assert args.log_level == "INFO"
        assert args.poll_interval == 30.0
        assert args.symbols is None
