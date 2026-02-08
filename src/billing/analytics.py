"""PRD-125: Cost & Usage Metering + Billing — Cost Analytics."""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import statistics

from .config import BillingPeriod, MeterType
from .meter import UsageMeter
from .engine import BillingEngine


@dataclass
class CostBreakdown:
    """Cost breakdown for a workspace and period."""

    workspace_id: str
    period: str
    by_meter: Dict[str, float] = field(default_factory=dict)
    total: float = 0.0
    trend_pct: float = 0.0


class CostAnalytics:
    """Cost analysis, trend detection, and optimization recommendations."""

    def __init__(self, meter: UsageMeter, engine: BillingEngine) -> None:
        self._meter = meter
        self._engine = engine

    # ── Cost Analysis ─────────────────────────────────────────────────

    def get_workspace_costs(
        self,
        workspace_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> CostBreakdown:
        """Get detailed cost breakdown for a workspace."""
        records = self._meter.get_workspace_usage(workspace_id)
        if start:
            records = [r for r in records if r.timestamp >= start]
        if end:
            records = [r for r in records if r.timestamp <= end]

        by_meter: Dict[str, float] = {}
        for record in records:
            meter_def = self._meter.get_meter(record.meter_id)
            if meter_def:
                key = meter_def.meter_type.value
                by_meter[key] = by_meter.get(key, 0.0) + record.cost

        total = sum(by_meter.values())
        period_str = ""
        if start and end:
            period_str = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
        elif start:
            period_str = f"from {start.strftime('%Y-%m-%d')}"
        elif end:
            period_str = f"to {end.strftime('%Y-%m-%d')}"
        else:
            period_str = "all-time"

        return CostBreakdown(
            workspace_id=workspace_id,
            period=period_str,
            by_meter={k: round(v, 4) for k, v in by_meter.items()},
            total=round(total, 4),
        )

    def get_cost_trend(
        self,
        workspace_id: str,
        periods: int = 6,
        period_type: BillingPeriod = BillingPeriod.MONTHLY,
    ) -> List[CostBreakdown]:
        """Compute cost trend over multiple periods."""
        now = datetime.now(timezone.utc)
        results: List[CostBreakdown] = []

        for i in range(periods, 0, -1):
            if period_type == BillingPeriod.DAILY:
                period_start = now - timedelta(days=i)
                period_end = now - timedelta(days=i - 1)
            elif period_type == BillingPeriod.HOURLY:
                period_start = now - timedelta(hours=i)
                period_end = now - timedelta(hours=i - 1)
            else:  # MONTHLY
                period_start = now - timedelta(days=30 * i)
                period_end = now - timedelta(days=30 * (i - 1))

            breakdown = self.get_workspace_costs(workspace_id, period_start, period_end)

            # Calculate trend compared to previous period
            if results:
                prev_total = results[-1].total
                if prev_total > 0:
                    breakdown.trend_pct = round(
                        ((breakdown.total - prev_total) / prev_total) * 100, 2
                    )
            results.append(breakdown)

        return results

    def get_top_consumers(
        self,
        limit: int = 10,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, object]]:
        """Rank workspaces by total cost."""
        records = list(self._meter._records)
        if start:
            records = [r for r in records if r.timestamp >= start]
        if end:
            records = [r for r in records if r.timestamp <= end]

        workspace_costs: Dict[str, float] = {}
        workspace_counts: Dict[str, int] = {}
        for record in records:
            ws = record.workspace_id
            workspace_costs[ws] = workspace_costs.get(ws, 0.0) + record.cost
            workspace_counts[ws] = workspace_counts.get(ws, 0) + 1

        sorted_ws = sorted(workspace_costs.items(), key=lambda x: x[1], reverse=True)
        return [
            {
                "workspace_id": ws,
                "total_cost": round(cost, 4),
                "usage_count": workspace_counts.get(ws, 0),
                "rank": idx + 1,
            }
            for idx, (ws, cost) in enumerate(sorted_ws[:limit])
        ]

    def get_budget_status(
        self,
        workspace_id: str,
        budget: float,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Dict[str, object]:
        """Check budget utilization for a workspace."""
        breakdown = self.get_workspace_costs(workspace_id, start, end)
        spent = breakdown.total
        remaining = max(budget - spent, 0.0)
        utilization = (spent / budget * 100) if budget > 0 else 0.0
        is_over = spent > budget

        status = "under"
        if utilization >= 100:
            status = "exceeded"
        elif utilization >= 90:
            status = "critical"
        elif utilization >= 75:
            status = "warning"

        return {
            "workspace_id": workspace_id,
            "budget": round(budget, 4),
            "spent": round(spent, 4),
            "remaining": round(remaining, 4),
            "utilization_pct": round(utilization, 2),
            "status": status,
            "is_over_budget": is_over,
        }

    def get_optimization_recommendations(
        self,
        workspace_id: str,
    ) -> List[Dict[str, str]]:
        """Generate cost optimization recommendations based on usage patterns."""
        records = self._meter.get_workspace_usage(workspace_id)
        if not records:
            return [{"type": "info", "message": "No usage data available for analysis."}]

        recommendations: List[Dict[str, str]] = []

        # Check for meter type distribution
        meter_costs: Dict[str, float] = {}
        for record in records:
            meter_def = self._meter.get_meter(record.meter_id)
            if meter_def:
                key = meter_def.meter_type.value
                meter_costs[key] = meter_costs.get(key, 0.0) + record.cost

        total = sum(meter_costs.values())
        if total == 0:
            return [{"type": "info", "message": "No cost data to analyze."}]

        # Identify dominant cost centers (>50% of total)
        for mtype, cost in meter_costs.items():
            pct = cost / total * 100
            if pct > 50:
                recommendations.append({
                    "type": "cost_center",
                    "message": (
                        f"{mtype} accounts for {pct:.0f}% of costs. "
                        f"Consider negotiating volume pricing or reducing usage."
                    ),
                })

        # Check for high-frequency small usage (possible batching opportunity)
        small_records = [r for r in records if r.quantity < 1.0]
        if len(small_records) > len(records) * 0.5:
            recommendations.append({
                "type": "batching",
                "message": (
                    "Over 50% of usage records have quantity < 1. "
                    "Consider batching small requests to reduce overhead."
                ),
            })

        # Check for tier upgrade potential
        if total > 500:
            recommendations.append({
                "type": "tier_upgrade",
                "message": (
                    "Monthly spend exceeds $500. "
                    "Consider upgrading to a higher pricing tier for volume discounts."
                ),
            })

        # If usage is consistent, suggest reserved capacity
        costs = [r.cost for r in records]
        if len(costs) >= 5:
            mean = statistics.mean(costs)
            stdev = statistics.stdev(costs) if len(costs) > 1 else 0
            cv = stdev / mean if mean > 0 else 0
            if cv < 0.3:
                recommendations.append({
                    "type": "reserved_capacity",
                    "message": (
                        "Usage pattern is highly consistent. "
                        "Consider reserved capacity for predictable costs."
                    ),
                })

        if not recommendations:
            recommendations.append({
                "type": "info",
                "message": "Current usage pattern is well-optimized.",
            })

        return recommendations

    def get_revenue_forecast(
        self,
        periods_ahead: int = 3,
        period_type: BillingPeriod = BillingPeriod.MONTHLY,
    ) -> List[Dict[str, object]]:
        """Forecast future revenue based on historical bills."""
        bills = self._engine.list_bills()
        if not bills:
            return []

        # Group revenue by period
        period_revenue: Dict[str, float] = {}
        for bill in bills:
            if period_type == BillingPeriod.MONTHLY:
                key = bill.period_start.strftime("%Y-%m")
            elif period_type == BillingPeriod.DAILY:
                key = bill.period_start.strftime("%Y-%m-%d")
            else:
                key = bill.period_start.strftime("%Y-%m-%d %H")
            period_revenue[key] = period_revenue.get(key, 0.0) + bill.total

        if not period_revenue:
            return []

        # Simple linear forecast using average growth
        values = list(period_revenue.values())
        avg_revenue = statistics.mean(values)
        growth_rate = 0.0
        if len(values) >= 2:
            growth_rates = []
            for i in range(1, len(values)):
                if values[i - 1] > 0:
                    growth_rates.append((values[i] - values[i - 1]) / values[i - 1])
            if growth_rates:
                growth_rate = statistics.mean(growth_rates)

        forecasts = []
        last_value = values[-1] if values else avg_revenue
        now = datetime.now(timezone.utc)
        for i in range(1, periods_ahead + 1):
            projected = last_value * (1 + growth_rate)
            if period_type == BillingPeriod.MONTHLY:
                forecast_date = now + timedelta(days=30 * i)
                period_label = forecast_date.strftime("%Y-%m")
            elif period_type == BillingPeriod.DAILY:
                forecast_date = now + timedelta(days=i)
                period_label = forecast_date.strftime("%Y-%m-%d")
            else:
                forecast_date = now + timedelta(hours=i)
                period_label = forecast_date.strftime("%Y-%m-%d %H:00")

            forecasts.append({
                "period": period_label,
                "projected_revenue": round(projected, 4),
                "growth_rate": round(growth_rate * 100, 2),
                "confidence": "medium" if len(values) >= 3 else "low",
            })
            last_value = projected

        return forecasts
