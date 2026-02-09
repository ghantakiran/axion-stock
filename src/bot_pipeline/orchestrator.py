"""Bot Pipeline Orchestrator — central coordinator for the trading bot.

Replaces direct TradeExecutor.process_signal() with a hardened pipeline
that integrates all PRD-162-170 enhancement modules:

Pipeline flow (PRD-171 hardened):
    Signal → PersistentKillSwitch → SignalGuard (fresh+dedup)
    → SignalRecorder → UnifiedRisk → InstrumentRouter
    → PositionSizer → OrderRouter (w/ retry) → OrderValidator
    → Position → Journal → SignalFeedback → DailyLossCheck

Key improvements over direct executor:
- Thread-safe (RLock around entire pipeline)
- Persistent kill switch (survives restarts)
- Signal freshness + deduplication guard (PRD-171)
- Order fill validation (no ghost positions)
- Full signal audit trail (PRD-162)
- Unified risk context (PRD-163, replaces basic RiskGate)
- Instrument routing: options/ETF/stock (PRD-171)
- Trade journal integration (PRD-171)
- Daily loss auto-kill (PRD-171)
- Capped execution history (PRD-171)
- Signal performance feedback (PRD-166)
"""

from __future__ import annotations

import collections
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.ema_signals.detector import TradeSignal
from src.trade_executor.executor import (
    AccountState,
    ExecutorConfig,
    Position,
    PositionSizer,
)
from src.trade_executor.router import Order, OrderResult, OrderRouter

from src.bot_pipeline.order_validator import FillValidation, OrderValidator
from src.bot_pipeline.signal_guard import SignalGuard
from src.bot_pipeline.state_manager import PersistentStateManager

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the bot pipeline orchestrator.

    Attributes:
        executor_config: Base executor settings (risk params, broker).
        enable_signal_recording: Record signals via PRD-162.
        enable_unified_risk: Use unified risk context vs basic gate.
        enable_feedback_loop: Track signal source performance.
        max_order_retries: Retry attempts for broker order submission.
        retry_backoff_base: Base seconds for exponential retry backoff.
        state_dir: Directory for persistent state files.
    """

    executor_config: ExecutorConfig = field(default_factory=ExecutorConfig)
    enable_signal_recording: bool = True
    enable_unified_risk: bool = True
    enable_feedback_loop: bool = True
    max_order_retries: int = 3
    retry_backoff_base: float = 1.0
    state_dir: str = ".bot_state"

    # PRD-171: Signal guards
    max_signal_age_seconds: float = 120.0
    dedup_window_seconds: float = 300.0

    # PRD-171: Lifecycle
    enable_instrument_routing: bool = True
    enable_journaling: bool = True
    max_history_size: int = 10_000

    # PRD-171: Auto-kill on daily loss
    auto_kill_on_daily_loss: bool = True


@dataclass
class PipelineResult:
    """Result of processing a signal through the full pipeline.

    Extends ExecutionResult with audit trail IDs and validation details.

    Attributes:
        success: Whether a position was created.
        signal: The input trade signal.
        position: Created Position (None if rejected).
        order_result: Broker order result (None if rejected before ordering).
        fill_validation: Fill validation details.
        rejection_reason: Why the signal was rejected (None if success).
        signal_id: Audit trail signal ID (PRD-162).
        decision_id: Audit trail risk decision ID.
        execution_id: Audit trail execution ID.
        risk_assessment: Unified risk assessment dict.
        pipeline_stage: Where in the pipeline the signal ended up.
    """

    success: bool
    signal: TradeSignal
    position: Optional[Position] = None
    order_result: Optional[OrderResult] = None
    fill_validation: Optional[FillValidation] = None
    rejection_reason: Optional[str] = None
    signal_id: Optional[str] = None
    decision_id: Optional[str] = None
    execution_id: Optional[str] = None
    risk_assessment: Optional[dict] = None
    pipeline_stage: str = "completed"

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "ticker": self.signal.ticker,
            "direction": self.signal.direction,
            "conviction": self.signal.conviction,
            "pipeline_stage": self.pipeline_stage,
            "rejection_reason": self.rejection_reason,
            "signal_id": self.signal_id,
            "decision_id": self.decision_id,
            "execution_id": self.execution_id,
            "order_id": self.order_result.order_id if self.order_result else None,
        }


class BotOrchestrator:
    """Central pipeline coordinator wiring all bot modules together.

    Thread-safe, validated, auditable signal processing pipeline.

    Args:
        config: PipelineConfig with all settings.
        state_manager: Persistent state (created if not provided).
        order_router: Order router (created in paper mode if not provided).
        order_validator: Fill validator (created with defaults if not provided).
        signal_recorder: PRD-162 signal recorder (lazy-loaded if enabled).
        risk_context: PRD-163 unified risk context (lazy-loaded if enabled).
        performance_tracker: PRD-166 feedback tracker (lazy-loaded if enabled).

    Example:
        orchestrator = BotOrchestrator()
        result = orchestrator.process_signal(signal, account)
        if result.success:
            print(f"Position created: {result.position.ticker}")
        else:
            print(f"Rejected at {result.pipeline_stage}: {result.rejection_reason}")
    """

    def __init__(
        self,
        config: PipelineConfig | None = None,
        state_manager: PersistentStateManager | None = None,
        order_router: OrderRouter | None = None,
        order_validator: OrderValidator | None = None,
        signal_recorder: Any = None,
        risk_context: Any = None,
        performance_tracker: Any = None,
        signal_guard: SignalGuard | None = None,
        journal: Any = None,
        instrument_router: Any = None,
        etf_sizer: Any = None,
    ) -> None:
        self.config = config or PipelineConfig()
        self._lock = threading.RLock()

        # Core components
        self._state = state_manager or PersistentStateManager(self.config.state_dir)
        self._sizer = PositionSizer(self.config.executor_config)
        self._router = order_router or OrderRouter(
            primary_broker=self.config.executor_config.primary_broker,
            paper_mode=True,
        )
        self._validator = order_validator or OrderValidator()

        # PRD-171: Signal guard (freshness + dedup)
        self._signal_guard = signal_guard or SignalGuard(
            max_age_seconds=self.config.max_signal_age_seconds,
            dedup_window_seconds=self.config.dedup_window_seconds,
        )

        # PRD-171: Trade journal
        self._journal = journal
        if self._journal is None and self.config.enable_journaling:
            self._journal = self._lazy_load_journal()

        # PRD-171: Instrument routing
        self._instrument_router = instrument_router
        self._etf_sizer = etf_sizer
        if self._instrument_router is None and self.config.enable_instrument_routing:
            self._instrument_router = self._lazy_load_instrument_router()
            self._etf_sizer = self._lazy_load_etf_sizer()

        # Position store (thread-safe via _lock)
        self.positions: list[Position] = []
        self.execution_history: collections.deque[PipelineResult] = collections.deque(
            maxlen=self.config.max_history_size,
        )

        # PRD-162: Signal persistence (optional)
        self._recorder = signal_recorder
        if self._recorder is None and self.config.enable_signal_recording:
            self._recorder = self._lazy_load_recorder()

        # PRD-163: Unified risk (optional)
        self._risk_context = risk_context
        if self._risk_context is None and self.config.enable_unified_risk:
            self._risk_context = self._lazy_load_risk_context()

        # PRD-166: Feedback loop (optional)
        self._perf_tracker = performance_tracker
        if self._perf_tracker is None and self.config.enable_feedback_loop:
            self._perf_tracker = self._lazy_load_tracker()

    def process_signal(
        self,
        signal: TradeSignal,
        account: AccountState,
        regime: str = "sideways",
        returns_by_ticker: dict[str, list[float]] | None = None,
    ) -> PipelineResult:
        """Thread-safe, fully validated signal processing pipeline.

        Pipeline stages:
        1. Kill switch check (persistent)
        2. Record incoming signal (PRD-162)
        3. Unified risk assessment (PRD-163)
        4. Position sizing
        5. Order submission (with retry)
        6. Fill validation
        7. Position creation (only after validated fill)
        8. Record execution (PRD-162)
        9. Update feedback tracker (PRD-166)

        Args:
            signal: Trade signal from EMA detector or other source.
            account: Current account state.
            regime: Current market regime for risk adjustment.
            returns_by_ticker: Historical returns for correlation/VaR.

        Returns:
            PipelineResult with full audit trail.
        """
        with self._lock:
            signal_id = None
            decision_id = None

            # ── Stage 1: Persistent kill switch ──────────────────
            if self._state.kill_switch_active:
                return PipelineResult(
                    success=False,
                    signal=signal,
                    rejection_reason=f"Kill switch active: {self._state.kill_switch_reason}",
                    pipeline_stage="kill_switch",
                )

            # ── Stage 1.5: Signal guard (PRD-171) ────────────────
            guard_reason = self._signal_guard.check(signal)
            if guard_reason:
                return PipelineResult(
                    success=False,
                    signal=signal,
                    rejection_reason=guard_reason,
                    pipeline_stage="signal_guard",
                )

            # Update state timestamps
            self._state.record_signal_time()

            # ── Stage 2: Record signal (PRD-162) ────────────────
            if self._recorder:
                try:
                    signal_id = self._recorder.record_signal(
                        source=signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type),
                        ticker=signal.ticker,
                        direction=signal.direction,
                        strength=float(signal.conviction),
                        confidence=signal.conviction / 100.0,
                    )
                except Exception as e:
                    logger.warning("Signal recording failed (non-fatal): %s", e)

            # ── Stage 3: Risk assessment ─────────────────────────
            risk_dict = None
            if self._risk_context:
                try:
                    positions_as_dicts = [
                        {"symbol": p.ticker, "market_value": p.shares * p.current_price,
                         "side": p.direction}
                        for p in self.positions
                    ]
                    assessment = self._risk_context.assess(
                        ticker=signal.ticker,
                        direction=signal.direction,
                        positions=positions_as_dicts,
                        returns_by_ticker=returns_by_ticker,
                        regime=regime,
                        kill_switch_active=self._state.kill_switch_active,
                        circuit_breaker_status=self._state.circuit_breaker_status,
                    )
                    risk_dict = assessment.to_dict()

                    # Record risk decision (PRD-162)
                    if self._recorder and signal_id:
                        try:
                            decision_id = self._recorder.record_risk_decision(
                                signal_id=signal_id,
                                approved=assessment.approved,
                                rejection_reason=assessment.rejection_reason,
                                checks_run=assessment.checks_run,
                            )
                        except Exception as e:
                            logger.warning("Risk decision recording failed: %s", e)

                    if not assessment.approved:
                        return PipelineResult(
                            success=False,
                            signal=signal,
                            rejection_reason=assessment.rejection_reason,
                            signal_id=signal_id,
                            decision_id=decision_id,
                            risk_assessment=risk_dict,
                            pipeline_stage="risk_assessment",
                        )
                except Exception as e:
                    logger.error("Unified risk assessment failed: %s", e)
                    return PipelineResult(
                        success=False,
                        signal=signal,
                        rejection_reason=f"Risk assessment error: {e}",
                        signal_id=signal_id,
                        pipeline_stage="risk_assessment_error",
                    )
            else:
                # Fallback: basic position count check
                if len(self.positions) >= self.config.executor_config.max_concurrent_positions:
                    return PipelineResult(
                        success=False,
                        signal=signal,
                        rejection_reason=f"Max positions reached: {len(self.positions)}",
                        signal_id=signal_id,
                        pipeline_stage="basic_risk_check",
                    )

            # ── Stage 3.5: Instrument routing (PRD-171) ─────────
            trade_type = self._classify_trade_type(signal.timeframe)
            instrument_decision = None
            order_ticker = signal.ticker
            position_instrument_type = "stock"
            position_leverage = 1.0

            if self._instrument_router:
                try:
                    instrument_decision = self._instrument_router.route(
                        signal, trade_type=trade_type,
                    )
                    order_ticker = instrument_decision.ticker
                    position_instrument_type = instrument_decision.instrument_type
                    position_leverage = instrument_decision.leverage
                except Exception as e:
                    logger.warning("Instrument routing failed (fallback to stock): %s", e)

            # ── Stage 4: Position sizing ─────────────────────────
            if (
                self._etf_sizer
                and instrument_decision
                and instrument_decision.instrument_type == "leveraged_etf"
            ):
                try:
                    from src.trade_executor.instrument_router import ETFSelection
                    etf_sel = ETFSelection(
                        ticker=instrument_decision.ticker,
                        leverage=instrument_decision.leverage,
                        tracks=instrument_decision.etf_metadata.get("tracks", "") if instrument_decision.etf_metadata else "",
                        is_inverse=instrument_decision.is_inverse,
                    )
                    size = self._etf_sizer.calculate(signal, etf_sel, account)
                except Exception as e:
                    logger.warning("ETF sizing failed (fallback to standard): %s", e)
                    size = self._sizer.calculate(signal, account)
            else:
                size = self._sizer.calculate(signal, account)

            # ── Stage 5: Order submission ────────────────────────
            order = Order(
                ticker=order_ticker,
                side="buy" if signal.direction == "long" else "sell",
                qty=size.shares,
                order_type=size.order_type,
                limit_price=signal.entry_price if size.order_type == "limit" else None,
                stop_price=signal.stop_loss if size.order_type == "stop" else None,
                time_in_force=self.config.executor_config.default_time_in_force,
                signal_id=signal_id or str(id(signal)),
                metadata={"entry_price": signal.entry_price},
            )

            order_result = self._submit_with_retry(order)

            # ── Stage 6: Fill validation ─────────────────────────
            validation = self._validator.validate_fill(
                order_result=order_result,
                expected_qty=size.shares,
                expected_price=signal.entry_price,
            )

            if not validation.is_valid:
                return PipelineResult(
                    success=False,
                    signal=signal,
                    order_result=order_result,
                    fill_validation=validation,
                    rejection_reason=f"Fill validation failed: {validation.reason}",
                    signal_id=signal_id,
                    decision_id=decision_id,
                    risk_assessment=risk_dict,
                    pipeline_stage="fill_validation",
                )

            # ── Stage 7: Position creation ───────────────────────
            position = Position(
                ticker=order_ticker,
                direction=signal.direction,
                entry_price=validation.fill_price,
                current_price=validation.fill_price,
                shares=validation.adjusted_qty,
                stop_loss=signal.stop_loss,
                target_price=signal.target_price,
                entry_time=datetime.now(timezone.utc),
                signal_id=signal_id or str(id(signal)),
                trade_type=trade_type,
                instrument_type=position_instrument_type,
                leverage=position_leverage,
            )
            self.positions.append(position)

            # ── Stage 8: Record execution (PRD-162) ──────────────
            execution_id = None
            if self._recorder and signal_id:
                try:
                    execution_id = self._recorder.record_execution(
                        signal_id=signal_id,
                        ticker=signal.ticker,
                        direction=signal.direction,
                        quantity=float(validation.adjusted_qty),
                        fill_price=validation.fill_price,
                        decision_id=decision_id,
                        order_type=size.order_type,
                        requested_price=signal.entry_price,
                        broker=order_result.broker,
                        status=order_result.status,
                    )
                except Exception as e:
                    logger.warning("Execution recording failed: %s", e)

            # ── Stage 8.5: Journal entry (PRD-171) ────────────────
            if self._journal:
                try:
                    self._journal.record_entry(signal, order_result, position)
                except Exception as e:
                    logger.warning("Journal entry recording failed: %s", e)

            # Update state timestamps
            self._state.record_trade_time()

            result = PipelineResult(
                success=True,
                signal=signal,
                position=position,
                order_result=order_result,
                fill_validation=validation,
                signal_id=signal_id,
                decision_id=decision_id,
                execution_id=execution_id,
                risk_assessment=risk_dict,
                pipeline_stage="completed",
            )
            self.execution_history.append(result)
            return result

    def close_position(
        self, ticker: str, exit_reason: str, exit_price: float = 0.0,
    ) -> Optional[Position]:
        """Close a position and update feedback tracking.

        Args:
            ticker: Symbol to close.
            exit_reason: Why the position is being closed.
            exit_price: Exit price (uses current_price if 0).

        Returns:
            The closed Position, or None if not found.
        """
        with self._lock:
            for i, pos in enumerate(self.positions):
                if pos.ticker == ticker:
                    closed = self.positions.pop(i)
                    price = exit_price or closed.current_price
                    mult = 1 if closed.direction == "long" else -1
                    pnl = mult * (price - closed.entry_price) * closed.shares
                    pnl_pct = mult * (price - closed.entry_price) / closed.entry_price if closed.entry_price > 0 else 0

                    # Update persistent state
                    self._state.record_trade_pnl(pnl)

                    # Check kill switch triggers
                    self._check_kill_switch_triggers()

                    # PRD-171: Daily loss auto-kill
                    self._check_daily_loss_limit()

                    # PRD-171: Journal exit recording
                    if self._journal:
                        try:
                            self._journal.record_exit(
                                position=closed,
                                exit_reason=exit_reason,
                                exit_price=price,
                            )
                        except Exception as e:
                            logger.warning("Journal exit recording failed: %s", e)

                    # Update feedback tracker (PRD-166)
                    if self._perf_tracker:
                        try:
                            signal_source = getattr(closed, "_signal_source", "ema_cloud")
                            self._perf_tracker.record_outcome(
                                source=signal_source,
                                pnl=pnl,
                                conviction=50.0,
                            )
                        except Exception as e:
                            logger.warning("Feedback tracking failed: %s", e)

                    logger.info(
                        "Closed %s %s: P&L $%.2f (%.2f%%) — %s",
                        closed.direction, closed.ticker, pnl, pnl_pct * 100, exit_reason,
                    )
                    return closed
            return None

    def get_pipeline_stats(self) -> dict[str, Any]:
        """Get pipeline health statistics."""
        with self._lock:
            total = len(self.execution_history)
            successes = sum(1 for r in self.execution_history if r.success)
            stats = {
                "total_signals_processed": total,
                "successful_executions": successes,
                "rejection_rate": (total - successes) / max(total, 1) * 100,
                "open_positions": len(self.positions),
                "kill_switch_active": self._state.kill_switch_active,
                "circuit_breaker_status": self._state.circuit_breaker_status,
                "daily_pnl": self._state.daily_pnl,
                "daily_trades": self._state.daily_trade_count,
                "history_size": total,
                "history_max_size": self.config.max_history_size,
            }
            if self._signal_guard:
                stats["signal_guard"] = self._signal_guard.get_stats()
            return stats

    # ── Internal ─────────────────────────────────────────────────────

    def _submit_with_retry(self, order: Order) -> OrderResult:
        """Submit order with exponential backoff retry."""
        import time as _time

        last_error = None
        for attempt in range(self.config.max_order_retries):
            try:
                result = self._router.submit_order(order)
                if result.status != "rejected" or attempt == self.config.max_order_retries - 1:
                    return result
                last_error = result.rejection_reason
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Order attempt %d/%d failed: %s",
                    attempt + 1, self.config.max_order_retries, e,
                )

            # Exponential backoff
            if attempt < self.config.max_order_retries - 1:
                backoff = self.config.retry_backoff_base * (2 ** attempt)
                _time.sleep(backoff)

        # All retries exhausted
        return OrderResult(
            order_id="RETRY-EXHAUSTED",
            status="rejected",
            filled_qty=0,
            filled_price=0.0,
            broker="none",
            rejection_reason=f"All {self.config.max_order_retries} attempts failed: {last_error}",
        )

    def _check_daily_loss_limit(self) -> None:
        """Activate kill switch if daily P&L exceeds daily_loss_limit.

        Uses the equity estimate and the configured daily_loss_limit fraction.
        """
        if not self.config.auto_kill_on_daily_loss:
            return
        cfg = self.config.executor_config
        equity = self._get_equity_estimate()
        max_loss = cfg.daily_loss_limit * equity
        daily_pnl = self._state.daily_pnl
        if daily_pnl < 0 and abs(daily_pnl) >= max_loss:
            self._state.activate_kill_switch(
                f"Daily loss limit hit: ${daily_pnl:.2f} exceeds "
                f"-${max_loss:.2f} ({cfg.daily_loss_limit:.0%} of ${equity:.0f})"
            )

    def _check_kill_switch_triggers(self) -> None:
        """Check if kill switch should be activated based on persistent state."""
        cfg = self.config.executor_config

        # Consecutive losses
        losses = self._state.get_consecutive_losses()
        if len(losses) >= cfg.consecutive_loss_threshold:
            recent = losses[-cfg.consecutive_loss_threshold:]
            if all(abs(loss) >= cfg.consecutive_loss_pct * self._get_equity_estimate() for loss in recent):
                self._state.activate_kill_switch(
                    f"{cfg.consecutive_loss_threshold} consecutive losses"
                )

    def _get_equity_estimate(self) -> float:
        """Estimate equity from positions (fallback)."""
        return sum(p.shares * p.current_price for p in self.positions) or 100_000.0

    @staticmethod
    def _classify_trade_type(timeframe: str) -> str:
        if timeframe in ("1m", "5m"):
            return "scalp"
        elif timeframe in ("10m",):
            return "day"
        return "swing"

    @staticmethod
    def _lazy_load_recorder():
        try:
            from src.signal_persistence import SignalRecorder
            return SignalRecorder()
        except ImportError:
            logger.info("signal_persistence not available — recording disabled")
            return None

    @staticmethod
    def _lazy_load_risk_context():
        try:
            from src.unified_risk import RiskContext
            return RiskContext()
        except ImportError:
            logger.info("unified_risk not available — using basic checks")
            return None

    @staticmethod
    def _lazy_load_tracker():
        try:
            from src.signal_feedback import PerformanceTracker
            return PerformanceTracker()
        except ImportError:
            logger.info("signal_feedback not available — tracking disabled")
            return None

    @staticmethod
    def _lazy_load_journal():
        try:
            from src.trade_executor.journal import TradeJournalWriter
            return TradeJournalWriter()
        except ImportError:
            logger.info("TradeJournalWriter not available — journaling disabled")
            return None

    @staticmethod
    def _lazy_load_instrument_router():
        try:
            from src.trade_executor.instrument_router import InstrumentRouter
            return InstrumentRouter()
        except ImportError:
            logger.info("InstrumentRouter not available — routing disabled")
            return None

    @staticmethod
    def _lazy_load_etf_sizer():
        try:
            from src.trade_executor.etf_sizer import LeveragedETFSizer
            from src.trade_executor.executor import ExecutorConfig
            return LeveragedETFSizer(ExecutorConfig())
        except ImportError:
            logger.info("LeveragedETFSizer not available — ETF sizing disabled")
            return None
