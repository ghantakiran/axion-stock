"""Execution Reconciler — tracks fill quality and slippage.

Compares PipelineOrder expectations (target price, target qty)
against actual fills from the broker. Produces reconciliation
records and aggregated slippage statistics for quality monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import uuid


# ═══════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ReconciliationRecord:
    """A single reconciliation comparing expected vs actual fill.

    Attributes:
        record_id: Unique reconciliation record ID.
        order_id: Pipeline order ID.
        symbol: Ticker symbol.
        expected_price: Price the signal expected (limit_price or market estimate).
        actual_price: Actual fill price from broker.
        expected_qty: Requested quantity.
        actual_qty: Filled quantity.
        slippage_pct: Price slippage as percentage (positive = worse than expected).
        fill_ratio: Actual qty / expected qty.
        broker_name: Which broker executed.
        latency_ms: Execution latency.
        timestamp: When this record was created.
    """

    record_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    order_id: str = ""
    symbol: str = ""
    expected_price: float = 0.0
    actual_price: float = 0.0
    expected_qty: float = 0.0
    actual_qty: float = 0.0
    slippage_pct: float = 0.0
    fill_ratio: float = 1.0
    broker_name: str = ""
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "expected_price": self.expected_price,
            "actual_price": self.actual_price,
            "expected_qty": self.expected_qty,
            "actual_qty": self.actual_qty,
            "slippage_pct": round(self.slippage_pct, 4),
            "fill_ratio": round(self.fill_ratio, 4),
            "broker_name": self.broker_name,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SlippageStats:
    """Aggregated slippage statistics across multiple fills.

    Attributes:
        total_records: Number of reconciliation records.
        avg_slippage_pct: Mean slippage percentage.
        max_slippage_pct: Worst slippage observed.
        min_slippage_pct: Best slippage (can be negative = better than expected).
        avg_fill_ratio: Average fill ratio.
        full_fill_rate: Percentage of orders fully filled.
        avg_latency_ms: Mean execution latency.
        by_broker: Per-broker avg slippage.
    """

    total_records: int = 0
    avg_slippage_pct: float = 0.0
    max_slippage_pct: float = 0.0
    min_slippage_pct: float = 0.0
    avg_fill_ratio: float = 1.0
    full_fill_rate: float = 1.0
    avg_latency_ms: float = 0.0
    by_broker: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_records": self.total_records,
            "avg_slippage_pct": round(self.avg_slippage_pct, 4),
            "max_slippage_pct": round(self.max_slippage_pct, 4),
            "min_slippage_pct": round(self.min_slippage_pct, 4),
            "avg_fill_ratio": round(self.avg_fill_ratio, 4),
            "full_fill_rate": round(self.full_fill_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "by_broker": {k: round(v, 4) for k, v in self.by_broker.items()},
        }


# ═══════════════════════════════════════════════════════════════════════
# Execution Reconciler
# ═══════════════════════════════════════════════════════════════════════


class ExecutionReconciler:
    """Tracks execution quality by comparing expected vs actual fills.

    After each trade, call reconcile() with the PipelineOrder and
    the actual fill details. The reconciler computes slippage and
    fill ratio, stores the record, and provides aggregate statistics.

    Example:
        reconciler = ExecutionReconciler()
        record = reconciler.reconcile(
            order_id="abc123",
            symbol="AAPL",
            expected_price=185.50,
            actual_price=185.65,
            expected_qty=100,
            actual_qty=100,
            broker_name="alpaca",
            latency_ms=45.2,
        )
        stats = reconciler.get_stats()
        print(f"Avg slippage: {stats.avg_slippage_pct:.2%}")
    """

    def __init__(self) -> None:
        self._records: list[ReconciliationRecord] = []

    @property
    def records(self) -> list[ReconciliationRecord]:
        return list(self._records)

    def reconcile(
        self,
        order_id: str,
        symbol: str,
        expected_price: float,
        actual_price: float,
        expected_qty: float,
        actual_qty: float,
        broker_name: str = "",
        latency_ms: float = 0.0,
    ) -> ReconciliationRecord:
        """Reconcile a single execution.

        Args:
            order_id: Pipeline order ID.
            symbol: Ticker symbol.
            expected_price: Price the order targeted.
            actual_price: Actual fill price.
            expected_qty: Requested quantity.
            actual_qty: Filled quantity.
            broker_name: Broker that executed.
            latency_ms: Execution latency.

        Returns:
            ReconciliationRecord with slippage calculations.
        """
        # Slippage: positive = worse (paid more for buy, received less for sell)
        if expected_price > 0:
            slippage_pct = (actual_price - expected_price) / expected_price * 100.0
        else:
            slippage_pct = 0.0

        fill_ratio = actual_qty / max(expected_qty, 0.001)

        record = ReconciliationRecord(
            order_id=order_id,
            symbol=symbol,
            expected_price=expected_price,
            actual_price=actual_price,
            expected_qty=expected_qty,
            actual_qty=actual_qty,
            slippage_pct=slippage_pct,
            fill_ratio=min(fill_ratio, 1.0),
            broker_name=broker_name,
            latency_ms=latency_ms,
        )
        self._records.append(record)
        return record

    def get_stats(self) -> SlippageStats:
        """Compute aggregate slippage statistics.

        Returns:
            SlippageStats across all recorded reconciliations.
        """
        if not self._records:
            return SlippageStats()

        slippages = [r.slippage_pct for r in self._records]
        fill_ratios = [r.fill_ratio for r in self._records]
        latencies = [r.latency_ms for r in self._records if r.latency_ms > 0]
        full_fills = sum(1 for r in self._records if r.fill_ratio >= 0.999)

        # Per-broker slippage
        broker_slippages: dict[str, list[float]] = {}
        for r in self._records:
            if r.broker_name:
                broker_slippages.setdefault(r.broker_name, []).append(r.slippage_pct)
        by_broker = {
            b: sum(s) / len(s) for b, s in broker_slippages.items()
        }

        return SlippageStats(
            total_records=len(self._records),
            avg_slippage_pct=sum(slippages) / len(slippages),
            max_slippage_pct=max(slippages),
            min_slippage_pct=min(slippages),
            avg_fill_ratio=sum(fill_ratios) / len(fill_ratios),
            full_fill_rate=full_fills / len(self._records),
            avg_latency_ms=sum(latencies) / max(len(latencies), 1),
            by_broker=by_broker,
        )

    def get_records_by_symbol(self, symbol: str) -> list[ReconciliationRecord]:
        """Get reconciliation records for a specific symbol."""
        return [r for r in self._records if r.symbol == symbol]

    def get_records_by_broker(self, broker: str) -> list[ReconciliationRecord]:
        """Get reconciliation records for a specific broker."""
        return [r for r in self._records if r.broker_name == broker]

    def clear(self) -> None:
        """Clear all reconciliation records."""
        self._records.clear()
