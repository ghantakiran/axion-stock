"""Best execution monitoring and reporting."""

from datetime import date, datetime
from typing import Dict, List, Optional

from .config import BestExecutionConfig, ExecutionQuality
from .models import BestExecutionReport, ExecutionMetric


class BestExecutionMonitor:
    """Monitors execution quality and generates best execution reports."""

    def __init__(self, config: Optional[BestExecutionConfig] = None):
        self.config = config or BestExecutionConfig()
        self._metrics: List[ExecutionMetric] = []

    def record_execution(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: int,
        limit_price: float,
        fill_price: float,
        benchmark_price: float,
        venue: str = "",
    ) -> ExecutionMetric:
        """Record a trade execution for quality analysis."""
        if benchmark_price > 0:
            if side.lower() == "buy":
                slippage_bps = (fill_price - benchmark_price) / benchmark_price * 10000
            else:
                slippage_bps = (benchmark_price - fill_price) / benchmark_price * 10000
        else:
            slippage_bps = 0.0

        # Price improvement: positive means better than limit
        if limit_price > 0:
            if side.lower() == "buy":
                pi_bps = (limit_price - fill_price) / limit_price * 10000
            else:
                pi_bps = (fill_price - limit_price) / limit_price * 10000
        else:
            pi_bps = 0.0

        quality = self._classify_quality(slippage_bps)

        metric = ExecutionMetric(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            limit_price=limit_price,
            fill_price=fill_price,
            benchmark_price=benchmark_price,
            slippage_bps=slippage_bps,
            price_improvement_bps=max(0, pi_bps),
            quality=quality,
            venue=venue,
        )
        self._metrics.append(metric)
        return metric

    def _classify_quality(self, slippage_bps: float) -> str:
        if slippage_bps <= self.config.excellent_threshold_bps:
            return ExecutionQuality.EXCELLENT.value
        elif slippage_bps <= self.config.good_threshold_bps:
            return ExecutionQuality.GOOD.value
        elif slippage_bps <= self.config.acceptable_threshold_bps:
            return ExecutionQuality.ACCEPTABLE.value
        elif slippage_bps <= self.config.max_slippage_bps * 2:
            return ExecutionQuality.POOR.value
        else:
            return ExecutionQuality.FAILED.value

    def generate_report(
        self,
        period_start: date,
        period_end: date,
    ) -> BestExecutionReport:
        """Generate best execution report for a period."""
        filtered = [
            m for m in self._metrics
            if period_start <= m.executed_at.date() <= period_end
        ]

        if not filtered:
            return BestExecutionReport(
                period_start=period_start,
                period_end=period_end,
                overall_quality=ExecutionQuality.ACCEPTABLE.value,
            )

        total = len(filtered)
        avg_slippage = sum(m.slippage_bps for m in filtered) / total
        avg_pi = sum(m.price_improvement_bps for m in filtered) / total

        quality_counts = {}
        for m in filtered:
            quality_counts[m.quality] = quality_counts.get(m.quality, 0) + 1

        excellent_pct = quality_counts.get("excellent", 0) / total
        good_pct = quality_counts.get("good", 0) / total
        poor_pct = quality_counts.get("poor", 0) / total
        failed_pct = quality_counts.get("failed", 0) / total

        # Per-venue breakdown
        by_venue: Dict[str, Dict[str, float]] = {}
        venue_groups: Dict[str, List[ExecutionMetric]] = {}
        for m in filtered:
            venue_groups.setdefault(m.venue or "unknown", []).append(m)

        for venue, metrics in venue_groups.items():
            n = len(metrics)
            by_venue[venue] = {
                "count": n,
                "avg_slippage_bps": sum(m.slippage_bps for m in metrics) / n,
                "avg_pi_bps": sum(m.price_improvement_bps for m in metrics) / n,
            }

        # Cost savings from price improvement
        total_saved = sum(
            m.price_improvement_bps / 10000 * m.fill_price * m.quantity
            for m in filtered
            if m.price_improvement_bps > 0
        )

        overall = self._classify_quality(avg_slippage)

        return BestExecutionReport(
            period_start=period_start,
            period_end=period_end,
            total_orders=total,
            avg_slippage_bps=avg_slippage,
            avg_price_improvement_bps=avg_pi,
            excellent_pct=excellent_pct,
            good_pct=good_pct,
            poor_pct=poor_pct,
            failed_pct=failed_pct,
            total_cost_saved=total_saved,
            overall_quality=overall,
            by_venue=by_venue,
        )

    def get_poor_executions(self) -> List[ExecutionMetric]:
        return [m for m in self._metrics if m.quality in ("poor", "failed")]

    def get_venue_ranking(self) -> List[Dict]:
        """Rank venues by average execution quality."""
        venue_groups: Dict[str, List[ExecutionMetric]] = {}
        for m in self._metrics:
            venue_groups.setdefault(m.venue or "unknown", []).append(m)

        rankings = []
        for venue, metrics in venue_groups.items():
            avg_slip = sum(m.slippage_bps for m in metrics) / len(metrics)
            rankings.append({
                "venue": venue,
                "orders": len(metrics),
                "avg_slippage_bps": avg_slip,
                "quality": self._classify_quality(avg_slip),
            })

        return sorted(rankings, key=lambda r: r["avg_slippage_bps"])

    def get_all_metrics(self) -> List[ExecutionMetric]:
        return self._metrics
