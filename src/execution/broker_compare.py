"""Broker Comparison Analytics.

Compares execution quality across brokers based on fill rate,
slippage, latency, and overall cost metrics.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class BrokerStats:
    """Execution statistics for a single broker."""
    broker: str = ""
    n_orders: int = 0
    n_filled: int = 0
    total_notional: float = 0.0

    # Fill metrics
    fill_rate: float = 0.0
    avg_fill_time_ms: float = 0.0
    median_fill_time_ms: float = 0.0

    # Cost metrics
    avg_slippage_bps: float = 0.0
    avg_commission_bps: float = 0.0
    avg_total_cost_bps: float = 0.0

    # Price improvement
    price_improvement_rate: float = 0.0
    avg_price_improvement_bps: float = 0.0

    # Rejection
    rejection_rate: float = 0.0

    # Composite score (0-100)
    score: float = 0.0

    @property
    def total_cost_dollar(self) -> float:
        return self.avg_total_cost_bps / 10_000 * self.total_notional

    @property
    def is_top_performer(self) -> bool:
        return self.score >= 80.0


@dataclass
class BrokerComparison:
    """Comparison across multiple brokers."""
    brokers: list[BrokerStats] = field(default_factory=list)
    best_broker: str = ""
    best_score: float = 0.0
    worst_broker: str = ""
    worst_score: float = 0.0

    @property
    def n_brokers(self) -> int:
        return len(self.brokers)

    @property
    def avg_score(self) -> float:
        if not self.brokers:
            return 0.0
        return sum(b.score for b in self.brokers) / len(self.brokers)


@dataclass
class TradeRecord:
    """Simplified trade record for broker comparison."""
    broker: str = ""
    symbol: str = ""
    side: str = "buy"
    quantity: float = 0.0
    filled_quantity: float = 0.0
    expected_price: float = 0.0
    fill_price: float = 0.0
    commission: float = 0.0
    fill_time_ms: float = 0.0
    is_filled: bool = True
    is_rejected: bool = False


# ---------------------------------------------------------------------------
# Broker Comparator
# ---------------------------------------------------------------------------
class BrokerComparator:
    """Compares execution quality across brokers."""

    def __init__(
        self,
        fill_rate_weight: float = 0.25,
        slippage_weight: float = 0.30,
        latency_weight: float = 0.15,
        cost_weight: float = 0.20,
        improvement_weight: float = 0.10,
    ) -> None:
        self.weights = {
            "fill_rate": fill_rate_weight,
            "slippage": slippage_weight,
            "latency": latency_weight,
            "cost": cost_weight,
            "improvement": improvement_weight,
        }

    def compute_broker_stats(
        self,
        trades: list[TradeRecord],
        broker: str,
    ) -> BrokerStats:
        """Compute execution statistics for a single broker.

        Args:
            trades: Trade records for this broker.
            broker: Broker name.

        Returns:
            BrokerStats with execution quality metrics.
        """
        if not trades:
            return BrokerStats(broker=broker)

        filled = [t for t in trades if t.is_filled]
        rejected = [t for t in trades if t.is_rejected]

        n_orders = len(trades)
        n_filled = len(filled)
        fill_rate = n_filled / n_orders if n_orders > 0 else 0.0

        # Notional
        total_notional = sum(t.filled_quantity * t.fill_price for t in filled)

        # Fill times
        fill_times = [t.fill_time_ms for t in filled if t.fill_time_ms > 0]
        avg_fill_time = float(np.mean(fill_times)) if fill_times else 0.0
        median_fill_time = float(np.median(fill_times)) if fill_times else 0.0

        # Slippage
        slippages = []
        improvements = []
        for t in filled:
            if t.expected_price > 0:
                sign = 1 if t.side == "buy" else -1
                slip_bps = sign * (t.fill_price - t.expected_price) / t.expected_price * 10_000
                slippages.append(slip_bps)
                if slip_bps < 0:  # Negative slippage = price improvement
                    improvements.append(abs(slip_bps))

        avg_slippage = float(np.mean(slippages)) if slippages else 0.0

        # Commission
        commissions_bps = []
        for t in filled:
            notional = t.filled_quantity * t.fill_price
            if notional > 0:
                commissions_bps.append(t.commission / notional * 10_000)
        avg_commission = float(np.mean(commissions_bps)) if commissions_bps else 0.0

        # Price improvement
        improvement_rate = len(improvements) / len(slippages) if slippages else 0.0
        avg_improvement = float(np.mean(improvements)) if improvements else 0.0

        # Rejection rate
        rejection_rate = len(rejected) / n_orders if n_orders > 0 else 0.0

        stats = BrokerStats(
            broker=broker,
            n_orders=n_orders,
            n_filled=n_filled,
            total_notional=round(total_notional, 2),
            fill_rate=round(fill_rate, 4),
            avg_fill_time_ms=round(avg_fill_time, 1),
            median_fill_time_ms=round(median_fill_time, 1),
            avg_slippage_bps=round(avg_slippage, 2),
            avg_commission_bps=round(avg_commission, 2),
            avg_total_cost_bps=round(avg_slippage + avg_commission, 2),
            price_improvement_rate=round(improvement_rate, 4),
            avg_price_improvement_bps=round(avg_improvement, 2),
            rejection_rate=round(rejection_rate, 4),
        )

        stats.score = self._compute_score(stats)
        return stats

    def compare(
        self,
        trade_records: dict[str, list[TradeRecord]],
    ) -> BrokerComparison:
        """Compare execution quality across multiple brokers.

        Args:
            trade_records: Dict of {broker_name: [TradeRecord, ...]}.

        Returns:
            BrokerComparison with ranked results.
        """
        if not trade_records:
            return BrokerComparison()

        broker_stats = []
        for broker, trades in trade_records.items():
            stats = self.compute_broker_stats(trades, broker)
            broker_stats.append(stats)

        # Sort by score descending
        broker_stats.sort(key=lambda x: x.score, reverse=True)

        best = broker_stats[0] if broker_stats else BrokerStats()
        worst = broker_stats[-1] if broker_stats else BrokerStats()

        return BrokerComparison(
            brokers=broker_stats,
            best_broker=best.broker,
            best_score=best.score,
            worst_broker=worst.broker,
            worst_score=worst.score,
        )

    def _compute_score(self, stats: BrokerStats) -> float:
        """Compute composite broker score (0-100).

        Higher is better. Components:
        - Fill rate score (0-100)
        - Slippage score (inverted, lower is better)
        - Latency score (inverted, lower is better)
        - Cost score (inverted)
        - Improvement score (higher is better)
        """
        # Fill rate: 100% = 100 score
        fill_score = stats.fill_rate * 100

        # Slippage: 0 bps = 100, 50+ bps = 0
        slip_raw = max(0, min(50, stats.avg_slippage_bps))
        slippage_score = max(0, 100 - slip_raw * 2)

        # Latency: 0 ms = 100, 1000+ ms = 0
        lat_raw = max(0, min(1000, stats.avg_fill_time_ms))
        latency_score = max(0, 100 - lat_raw / 10)

        # Cost: 0 bps = 100, 100+ bps = 0
        cost_raw = max(0, min(100, stats.avg_total_cost_bps))
        cost_score = max(0, 100 - cost_raw)

        # Improvement: 50%+ rate = 100
        improvement_score = min(100, stats.price_improvement_rate * 200)

        composite = (
            fill_score * self.weights["fill_rate"]
            + slippage_score * self.weights["slippage"]
            + latency_score * self.weights["latency"]
            + cost_score * self.weights["cost"]
            + improvement_score * self.weights["improvement"]
        )

        return round(composite, 1)
