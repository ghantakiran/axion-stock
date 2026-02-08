"""PRD-103: Observability & Metrics Export — Trading Metrics."""

import logging
from typing import Optional

from .config import MetricsConfig
from .registry import Counter, Gauge, Histogram, MetricsRegistry

logger = logging.getLogger(__name__)


class TradingMetrics:
    """Trading-specific metrics for order execution, positions, signals, and slippage."""

    def __init__(self, config: Optional[MetricsConfig] = None):
        self.config = config or MetricsConfig()
        self.registry = MetricsRegistry()
        self._register_metrics()

    def _register_metrics(self) -> None:
        """Register all trading metrics."""
        prefix = self.config.prefix

        # ── Order Metrics ─────────────────────────────────────────────
        self.orders_total: Counter = self.registry.counter(
            name=f"{prefix}_orders_total",
            description="Total number of orders processed",
            label_names=("status", "broker", "side"),
        )

        self.order_latency_seconds: Histogram = self.registry.histogram(
            name=f"{prefix}_order_latency_seconds",
            description="Order execution latency in seconds",
            label_names=(),
            buckets=self.config.buckets.order_latency,
        )

        # ── Position Metrics ──────────────────────────────────────────
        self.positions_active: Gauge = self.registry.gauge(
            name=f"{prefix}_positions_active",
            description="Number of currently active positions",
        )

        self.portfolio_value_dollars: Gauge = self.registry.gauge(
            name=f"{prefix}_portfolio_value_dollars",
            description="Current portfolio value in dollars",
        )

        # ── Signal Metrics ────────────────────────────────────────────
        self.signals_generated_total: Counter = self.registry.counter(
            name=f"{prefix}_signals_generated_total",
            description="Total number of trading signals generated",
            label_names=("strategy", "direction"),
        )

        # ── Slippage Metrics ──────────────────────────────────────────
        self.slippage_basis_points: Histogram = self.registry.histogram(
            name=f"{prefix}_slippage_basis_points",
            description="Order slippage in basis points",
            label_names=(),
            buckets=self.config.buckets.slippage,
        )

        logger.info("Trading metrics registered")

    # ── Convenience Methods ───────────────────────────────────────────

    def record_order(
        self,
        status: str = "filled",
        broker: str = "alpaca",
        side: str = "buy",
        latency_seconds: Optional[float] = None,
    ) -> None:
        """Record an order event."""
        self.orders_total.increment(
            labels={"status": status, "broker": broker, "side": side}
        )
        if latency_seconds is not None:
            self.order_latency_seconds.observe(latency_seconds)

    def update_positions(self, active_count: int, portfolio_value: float) -> None:
        """Update position and portfolio metrics."""
        self.positions_active.set(active_count)
        self.portfolio_value_dollars.set(portfolio_value)

    def record_signal(self, strategy: str, direction: str) -> None:
        """Record a trading signal."""
        self.signals_generated_total.increment(
            labels={"strategy": strategy, "direction": direction}
        )

    def record_slippage(self, basis_points: float) -> None:
        """Record slippage for an executed order."""
        self.slippage_basis_points.observe(basis_points)

    @staticmethod
    def generate_sample_data() -> "TradingMetrics":
        """Generate sample trading metrics for dashboards."""
        tm = TradingMetrics()

        # Sample orders
        for _ in range(150):
            tm.record_order(status="filled", broker="alpaca", side="buy", latency_seconds=0.12)
        for _ in range(45):
            tm.record_order(status="filled", broker="alpaca", side="sell", latency_seconds=0.08)
        for _ in range(12):
            tm.record_order(status="rejected", broker="ib", side="buy", latency_seconds=0.25)
        for _ in range(5):
            tm.record_order(status="cancelled", broker="alpaca", side="buy")

        # Positions
        tm.update_positions(active_count=23, portfolio_value=1_250_000.0)

        # Signals
        for _ in range(80):
            tm.record_signal(strategy="momentum", direction="long")
        for _ in range(35):
            tm.record_signal(strategy="mean_reversion", direction="short")
        for _ in range(20):
            tm.record_signal(strategy="ml_ranking", direction="long")

        # Slippage
        for bps in [0.5, 1.2, 0.8, 2.5, 1.0, 3.0, 0.3, 1.5, 0.7, 4.2]:
            tm.record_slippage(bps)

        return tm
