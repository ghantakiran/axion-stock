"""Pipeline Executor — validates, risk-checks, and routes orders.

Implements the 5-stage pipeline:
  validate → risk_check → route → execute → record

Each stage can reject the order, producing a PipelineResult with status
and detailed rejection reasons for audit.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from src.trade_pipeline.bridge import OrderSide, OrderType, PipelineOrder, SignalType

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Enums & Config
# ═══════════════════════════════════════════════════════════════════════


class PipelineStatus(str, Enum):
    """Status of a pipeline execution."""

    PENDING = "pending"
    VALIDATED = "validated"
    RISK_APPROVED = "risk_approved"
    ROUTED = "routed"
    EXECUTED = "executed"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass
class PipelineConfig:
    """Configuration for the pipeline executor.

    Attributes:
        min_confidence: Minimum signal confidence (0-1) to accept.
        max_position_pct: Maximum single position as % of equity.
        max_positions: Maximum concurrent open positions.
        daily_loss_limit_pct: Max daily loss as % of equity before halt.
        min_order_value: Minimum order dollar value.
        max_order_value: Maximum order dollar value.
        paper_mode: If True, simulate execution instead of routing to broker.
        require_stop_loss: Whether a stop loss is required.
        blocked_symbols: Symbols not allowed for trading.
    """

    min_confidence: float = 0.3
    max_position_pct: float = 15.0
    max_positions: int = 20
    daily_loss_limit_pct: float = 5.0
    min_order_value: float = 100.0
    max_order_value: float = 500_000.0
    paper_mode: bool = True
    require_stop_loss: bool = False
    blocked_symbols: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# Pipeline Result
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class PipelineResult:
    """Result of processing an order through the pipeline.

    Attributes:
        result_id: Unique result identifier.
        order: The PipelineOrder that was processed.
        status: Final pipeline status.
        rejection_reason: Why the order was rejected (if applicable).
        broker_name: Which broker executed (if applicable).
        fill_price: Execution fill price.
        fill_qty: Executed quantity.
        fee: Execution fee.
        latency_ms: Total pipeline processing time.
        stages_passed: List of stages the order passed through.
        created_at: When this result was created.
    """

    result_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    order: Optional[PipelineOrder] = None
    status: PipelineStatus = PipelineStatus.PENDING
    rejection_reason: str = ""
    broker_name: str = ""
    fill_price: float = 0.0
    fill_qty: float = 0.0
    fee: float = 0.0
    latency_ms: float = 0.0
    stages_passed: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "order_id": self.order.order_id if self.order else "",
            "symbol": self.order.symbol if self.order else "",
            "side": self.order.side.value if self.order else "",
            "status": self.status.value,
            "rejection_reason": self.rejection_reason,
            "broker_name": self.broker_name,
            "fill_price": self.fill_price,
            "fill_qty": self.fill_qty,
            "fee": self.fee,
            "latency_ms": round(self.latency_ms, 2),
            "stages_passed": self.stages_passed,
            "created_at": self.created_at.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════
# Pipeline Executor
# ═══════════════════════════════════════════════════════════════════════


class PipelineExecutor:
    """Validates, risk-checks, and executes PipelineOrders.

    The executor processes orders through 5 sequential stages:
      1. **Validate**: Check symbol, qty, order type, confidence.
      2. **Risk check**: Position limits, daily loss, blocked symbols.
      3. **Route**: Select broker via routing logic (or paper mode).
      4. **Execute**: Submit to broker (or simulate in paper mode).
      5. **Record**: Log result for reconciliation.

    In paper mode, stages 3-4 are simulated: the order is "filled"
    at the current estimated price with no actual broker call.

    Args:
        config: PipelineConfig with risk limits and execution settings.
        account_equity: Current account equity for position sizing validation.

    Example:
        executor = PipelineExecutor(PipelineConfig(paper_mode=True))
        result = executor.process(order)
        if result.status == PipelineStatus.EXECUTED:
            print(f"Filled {result.fill_qty} @ {result.fill_price}")
    """

    def __init__(
        self,
        config: PipelineConfig | None = None,
        account_equity: float = 100_000.0,
    ) -> None:
        self.config = config or PipelineConfig()
        self._equity = account_equity
        self._open_positions: dict[str, float] = {}  # symbol → qty
        self._daily_pnl: float = 0.0
        self._results: list[PipelineResult] = []

    @property
    def account_equity(self) -> float:
        return self._equity

    @account_equity.setter
    def account_equity(self, value: float) -> None:
        self._equity = max(0.0, value)

    @property
    def open_position_count(self) -> int:
        return len(self._open_positions)

    @property
    def results(self) -> list[PipelineResult]:
        return list(self._results)

    def reset_daily(self) -> None:
        """Reset daily P&L tracker (call at start of trading day)."""
        self._daily_pnl = 0.0

    def record_pnl(self, pnl: float) -> None:
        """Record realized P&L for daily loss tracking."""
        self._daily_pnl += pnl

    def set_positions(self, positions: dict[str, float]) -> None:
        """Set current open positions (symbol → qty)."""
        self._open_positions = dict(positions)

    # ── Main processing pipeline ────────────────────────────────────

    def process(self, order: PipelineOrder) -> PipelineResult:
        """Process a single order through the full pipeline.

        Args:
            order: PipelineOrder to process.

        Returns:
            PipelineResult with status and fill details.
        """
        start = time.monotonic()
        result = PipelineResult(order=order)

        # Stage 1: Validate
        rejection = self._validate(order)
        if rejection:
            result.status = PipelineStatus.REJECTED
            result.rejection_reason = rejection
            result.stages_passed = ["validate:rejected"]
            result.latency_ms = (time.monotonic() - start) * 1000
            self._results.append(result)
            return result
        result.stages_passed.append("validate:passed")
        result.status = PipelineStatus.VALIDATED

        # Stage 2: Risk check
        rejection = self._risk_check(order)
        if rejection:
            result.status = PipelineStatus.REJECTED
            result.rejection_reason = rejection
            result.stages_passed.append("risk_check:rejected")
            result.latency_ms = (time.monotonic() - start) * 1000
            self._results.append(result)
            return result
        result.stages_passed.append("risk_check:passed")
        result.status = PipelineStatus.RISK_APPROVED

        # Stage 3-4: Route & Execute
        if self.config.paper_mode:
            # Paper mode: simulate fill
            result.broker_name = "paper"
            result.fill_price = order.limit_price or 100.0
            result.fill_qty = order.qty
            result.fee = 0.0
            result.stages_passed.append("route:paper")
            result.stages_passed.append("execute:simulated")
            result.status = PipelineStatus.EXECUTED
        else:
            # Live mode: would call MultiBrokerExecutor here
            # For now, mark as routed (actual broker integration
            # is done by passing a broker_executor to process_live())
            result.broker_name = "pending"
            result.stages_passed.append("route:live")
            result.stages_passed.append("execute:pending")
            result.status = PipelineStatus.ROUTED

        # Stage 5: Record
        result.stages_passed.append("record:logged")
        result.latency_ms = (time.monotonic() - start) * 1000

        # Update position tracking
        if result.status == PipelineStatus.EXECUTED:
            if order.side == OrderSide.BUY:
                current = self._open_positions.get(order.symbol, 0.0)
                self._open_positions[order.symbol] = current + result.fill_qty
            elif order.side == OrderSide.SELL:
                current = self._open_positions.get(order.symbol, 0.0)
                new_qty = current - result.fill_qty
                if new_qty <= 0:
                    self._open_positions.pop(order.symbol, None)
                else:
                    self._open_positions[order.symbol] = new_qty

        self._results.append(result)
        return result

    def process_batch(self, orders: list[PipelineOrder]) -> list[PipelineResult]:
        """Process multiple orders sequentially.

        Args:
            orders: List of PipelineOrders.

        Returns:
            List of PipelineResult, one per order.
        """
        return [self.process(order) for order in orders]

    # ── Validation stages ───────────────────────────────────────────

    def _validate(self, order: PipelineOrder) -> str:
        """Stage 1: Validate order fields.

        Returns empty string if valid, rejection reason otherwise.
        """
        if not order.symbol:
            return "Missing symbol"
        if not order.symbol.replace("-", "").replace(".", "").isalnum():
            return f"Invalid symbol: {order.symbol}"
        if order.qty <= 0:
            return f"Invalid quantity: {order.qty}"
        if order.confidence < self.config.min_confidence:
            return f"Confidence {order.confidence:.2f} below minimum {self.config.min_confidence}"
        if order.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and order.limit_price is None:
            return "Limit order requires limit_price"
        if order.order_type in (OrderType.STOP, OrderType.STOP_LIMIT) and order.stop_price is None:
            return "Stop order requires stop_price"

        return ""

    def _risk_check(self, order: PipelineOrder) -> str:
        """Stage 2: Risk checks against portfolio limits.

        Returns empty string if approved, rejection reason otherwise.
        """
        # Blocked symbols
        if order.symbol in self.config.blocked_symbols:
            return f"Symbol {order.symbol} is blocked"

        # Max positions (only for new entries)
        if order.side == OrderSide.BUY and order.symbol not in self._open_positions:
            if self.open_position_count >= self.config.max_positions:
                return f"Max positions ({self.config.max_positions}) reached"

        # Position size limit
        if order.position_size_pct > self.config.max_position_pct:
            return f"Position size {order.position_size_pct:.1f}% exceeds max {self.config.max_position_pct}%"

        # Daily loss limit
        daily_loss_pct = abs(self._daily_pnl) / max(self._equity, 1.0) * 100.0
        if self._daily_pnl < 0 and daily_loss_pct >= self.config.daily_loss_limit_pct:
            return f"Daily loss limit reached ({daily_loss_pct:.1f}% >= {self.config.daily_loss_limit_pct}%)"

        # Order value bounds
        est_price = order.limit_price or 100.0
        order_value = order.qty * est_price
        if order_value < self.config.min_order_value:
            return f"Order value ${order_value:.0f} below minimum ${self.config.min_order_value:.0f}"
        if order_value > self.config.max_order_value:
            return f"Order value ${order_value:.0f} exceeds maximum ${self.config.max_order_value:.0f}"

        return ""

    # ── Query methods ───────────────────────────────────────────────

    def get_results(self, limit: int = 50) -> list[PipelineResult]:
        """Return recent pipeline results, newest first."""
        return list(reversed(self._results[-limit:]))

    def get_rejection_summary(self) -> dict[str, int]:
        """Count rejections by reason."""
        summary: dict[str, int] = {}
        for r in self._results:
            if r.status == PipelineStatus.REJECTED:
                reason = r.rejection_reason or "unknown"
                summary[reason] = summary.get(reason, 0) + 1
        return summary

    def get_execution_stats(self) -> dict[str, Any]:
        """Compute execution statistics across all results."""
        total = len(self._results)
        executed = sum(1 for r in self._results if r.status == PipelineStatus.EXECUTED)
        rejected = sum(1 for r in self._results if r.status == PipelineStatus.REJECTED)
        failed = sum(1 for r in self._results if r.status == PipelineStatus.FAILED)
        latencies = [r.latency_ms for r in self._results if r.latency_ms > 0]

        return {
            "total_processed": total,
            "executed": executed,
            "rejected": rejected,
            "failed": failed,
            "execution_rate": executed / max(total, 1),
            "avg_latency_ms": sum(latencies) / max(len(latencies), 1),
            "daily_pnl": self._daily_pnl,
        }
