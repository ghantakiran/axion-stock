"""Multi-Broker Executor -- order execution with failover (PRD-146).

Executes orders through the OrderRouter's selected broker with automatic
failover to fallback brokers. Tracks per-broker rate limits and records
execution metrics.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import logging
import time
import uuid

from src.multi_broker.registry import BrokerInfo, BrokerRegistry, BrokerStatus
from src.multi_broker.router import OrderRouter, RouteDecision

logger = logging.getLogger(__name__)


# =====================================================================
# Dataclasses & Enums
# =====================================================================


class ExecutionStatus(str, Enum):
    """Status of an order execution."""
    FILLED = "filled"
    PARTIAL = "partial"
    REJECTED = "rejected"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


@dataclass
class ExecutionResult:
    """Result of executing an order through the multi-broker system.

    Attributes:
        order_id: Unique execution identifier.
        broker_name: Broker that executed (or attempted) the order.
        status: Execution status.
        fill_price: Filled price (0 if not filled).
        fill_qty: Filled quantity.
        fee: Actual or estimated fee.
        latency_ms: Execution latency in milliseconds.
        failover_used: Whether a fallback broker was used.
        failover_from: Original broker if failover occurred.
        route_decision: The routing decision that led to this execution.
        error_message: Error details if execution failed.
        timestamp: When execution completed.
    """
    order_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    broker_name: str = ""
    status: ExecutionStatus = ExecutionStatus.FAILED
    fill_price: float = 0.0
    fill_qty: float = 0.0
    fee: float = 0.0
    latency_ms: float = 0.0
    failover_used: bool = False
    failover_from: str = ""
    route_decision: Optional[RouteDecision] = None
    error_message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "broker_name": self.broker_name,
            "status": self.status.value,
            "fill_price": self.fill_price,
            "fill_qty": self.fill_qty,
            "fee": self.fee,
            "latency_ms": round(self.latency_ms, 2),
            "failover_used": self.failover_used,
            "failover_from": self.failover_from,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
        }


# =====================================================================
# Multi-Broker Executor
# =====================================================================


class MultiBrokerExecutor:
    """Executes orders across multiple brokers with failover.

    Uses the OrderRouter to determine the target broker, then executes
    through the broker's adapter. If execution fails, automatically
    attempts the next broker in the fallback chain.

    Tracks per-broker request counts for rate-limit awareness.

    Example:
        executor = MultiBrokerExecutor(registry, router)
        result = await executor.execute({"symbol": "AAPL", "side": "buy", "qty": 10})
        if result.status == ExecutionStatus.FILLED:
            print(f"Filled at {result.fill_price} via {result.broker_name}")
    """

    def __init__(
        self,
        registry: BrokerRegistry,
        router: OrderRouter,
        max_requests_per_minute: int = 100,
    ) -> None:
        self._registry = registry
        self._router = router
        self._max_rpm = max_requests_per_minute
        self._request_counts: dict[str, list[float]] = {}  # broker -> list of timestamps
        self._execution_history: list[ExecutionResult] = []

    @property
    def execution_history(self) -> list[ExecutionResult]:
        """Recent execution results."""
        return list(self._execution_history)

    async def execute(self, order: dict) -> ExecutionResult:
        """Execute a single order with failover.

        Args:
            order: Order dict with keys: symbol, asset_type, side, qty, order_type, etc.

        Returns:
            ExecutionResult with fill details or error information.
        """
        # Route the order
        decision = self._router.route(order)

        if not decision.broker_name:
            result = ExecutionResult(
                status=ExecutionStatus.FAILED,
                error_message=decision.reason,
                route_decision=decision,
            )
            self._execution_history.append(result)
            return result

        # Build execution chain: primary + fallbacks
        chain = [decision.broker_name] + decision.fallback_chain
        original_broker = decision.broker_name

        for i, broker_name in enumerate(chain):
            # Check rate limit
            if self._is_rate_limited(broker_name):
                logger.warning(f"Broker {broker_name} rate-limited, trying next")
                continue

            broker_info = self._registry.get(broker_name)
            if not broker_info or broker_info.status != BrokerStatus.CONNECTED:
                continue

            # Execute
            start_time = time.monotonic()
            try:
                result_data = await broker_info.adapter.place_order(order)
                elapsed_ms = (time.monotonic() - start_time) * 1000

                self._record_request(broker_name)

                # Parse result
                fill_price = 0.0
                fill_qty = 0.0
                fee = 0.0
                status = ExecutionStatus.FILLED

                if isinstance(result_data, dict):
                    fill_price = float(result_data.get("fill_price", result_data.get("filled_avg_price", result_data.get("price", 0))))
                    fill_qty = float(result_data.get("fill_qty", result_data.get("filled_quantity", result_data.get("qty", order.get("qty", 0)))))
                    fee = float(result_data.get("fee", 0))
                    raw_status = result_data.get("status", "FILLED")
                    if raw_status in ("FILLED", "filled"):
                        status = ExecutionStatus.FILLED
                    elif raw_status in ("PARTIAL", "partial", "partially_filled"):
                        status = ExecutionStatus.PARTIAL
                    elif raw_status in ("REJECTED", "rejected"):
                        status = ExecutionStatus.REJECTED
                    else:
                        status = ExecutionStatus.FILLED
                else:
                    # Non-dict result, assume fill at estimated price
                    fill_qty = float(order.get("qty", 0))

                is_failover = i > 0
                result = ExecutionResult(
                    broker_name=broker_name,
                    status=status,
                    fill_price=fill_price,
                    fill_qty=fill_qty,
                    fee=fee or decision.estimated_fee,
                    latency_ms=elapsed_ms,
                    failover_used=is_failover,
                    failover_from=original_broker if is_failover else "",
                    route_decision=decision,
                )
                self._execution_history.append(result)
                logger.info(f"Executed on {broker_name}: {status.value} (latency={elapsed_ms:.0f}ms)")
                return result

            except Exception as e:
                elapsed_ms = (time.monotonic() - start_time) * 1000
                logger.warning(f"Execution failed on {broker_name}: {e}")
                self._registry.update_status(broker_name, BrokerStatus.ERROR, str(e))
                continue

        # All brokers failed
        result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            error_message=f"All brokers in chain failed: {chain}",
            route_decision=decision,
        )
        self._execution_history.append(result)
        return result

    async def execute_batch(self, orders: list[dict]) -> list[ExecutionResult]:
        """Execute multiple orders sequentially.

        Args:
            orders: List of order dicts.

        Returns:
            List of ExecutionResult, one per order.
        """
        results = []
        for order in orders:
            result = await self.execute(order)
            results.append(result)
        return results

    def get_broker_request_counts(self) -> dict[str, int]:
        """Get the number of requests sent to each broker in the last minute."""
        now = time.monotonic()
        counts: dict[str, int] = {}
        for broker, timestamps in self._request_counts.items():
            # Only count requests within the last 60 seconds
            recent = [t for t in timestamps if (now - t) < 60]
            self._request_counts[broker] = recent
            counts[broker] = len(recent)
        return counts

    # -- Internal Helpers --------------------------------------------------

    def _is_rate_limited(self, broker_name: str) -> bool:
        """Check if a broker has exceeded its rate limit."""
        now = time.monotonic()
        timestamps = self._request_counts.get(broker_name, [])
        recent = [t for t in timestamps if (now - t) < 60]
        self._request_counts[broker_name] = recent
        return len(recent) >= self._max_rpm

    def _record_request(self, broker_name: str) -> None:
        """Record a request timestamp for rate limiting."""
        if broker_name not in self._request_counts:
            self._request_counts[broker_name] = []
        self._request_counts[broker_name].append(time.monotonic())
