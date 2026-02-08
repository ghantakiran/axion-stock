"""Cost analysis for PRD-130: Capacity Planning & Auto-Scaling."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from .config import CapacityConfig, ResourceType
from .monitor import ResourceMonitor


@dataclass
class ResourceCost:
    """Cost information for a resource."""

    resource_type: ResourceType = ResourceType.CPU
    service: str = "default"
    hourly_cost: float = 0.0
    monthly_cost: float = 0.0
    utilization_pct: float = 0.0

    def __post_init__(self):
        if self.monthly_cost == 0.0 and self.hourly_cost > 0:
            self.monthly_cost = round(self.hourly_cost * 730, 2)  # ~730 hrs/month
        elif self.hourly_cost == 0.0 and self.monthly_cost > 0:
            self.hourly_cost = round(self.monthly_cost / 730, 4)


@dataclass
class SavingsOpportunity:
    """A cost savings opportunity."""

    opportunity_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    resource: ResourceType = ResourceType.CPU
    service: str = "default"
    current_cost: float = 0.0
    recommended_cost: float = 0.0
    savings_pct: float = 0.0
    action: str = ""

    def __post_init__(self):
        if self.current_cost > 0 and self.savings_pct == 0.0:
            self.savings_pct = round(
                ((self.current_cost - self.recommended_cost) / self.current_cost) * 100,
                2,
            )


@dataclass
class CostReport:
    """Comprehensive cost report."""

    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    period: str = "monthly"
    total_cost: float = 0.0
    by_service: Dict[str, float] = field(default_factory=dict)
    by_resource: Dict[str, float] = field(default_factory=dict)
    savings_opportunities: List[SavingsOpportunity] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CostAnalyzer:
    """Analyzes resource costs and identifies savings opportunities."""

    def __init__(
        self,
        monitor: Optional[ResourceMonitor] = None,
        config: Optional[CapacityConfig] = None,
    ):
        self.monitor = monitor or ResourceMonitor()
        self.config = config or CapacityConfig()
        self._cost_rates: Dict[str, ResourceCost] = {}
        self._trade_count: int = 0

    def set_cost_rate(self, cost: ResourceCost) -> None:
        """Set the cost rate for a resource/service combination."""
        key = f"{cost.resource_type.value}:{cost.service}"
        self._cost_rates[key] = cost

    def set_trade_count(self, count: int) -> None:
        """Set the number of trades for cost-per-trade calculation."""
        self._trade_count = count

    def calculate_costs(self, period: str = "monthly") -> CostReport:
        """Calculate comprehensive cost report."""
        by_service: Dict[str, float] = {}
        by_resource: Dict[str, float] = {}
        total = 0.0

        for key, cost in self._cost_rates.items():
            rt_val, svc = key.split(":", 1)

            # Determine period cost
            if period == "hourly":
                period_cost = cost.hourly_cost
            elif period == "daily":
                period_cost = cost.hourly_cost * 24
            else:  # monthly
                period_cost = cost.monthly_cost

            # Update utilization from monitor
            try:
                rt = ResourceType(rt_val)
                metric = self.monitor.get_current_utilization(rt, svc)
                if metric:
                    cost.utilization_pct = metric.utilization_pct
            except (ValueError, KeyError):
                pass

            by_service[svc] = by_service.get(svc, 0) + period_cost
            by_resource[rt_val] = by_resource.get(rt_val, 0) + period_cost
            total += period_cost

        savings = self.find_savings()

        return CostReport(
            period=period,
            total_cost=round(total, 2),
            by_service=by_service,
            by_resource=by_resource,
            savings_opportunities=savings,
        )

    def find_savings(self, threshold_pct: float = 50.0) -> List[SavingsOpportunity]:
        """Find savings opportunities where utilization is below threshold."""
        opportunities = []

        for key, cost in self._cost_rates.items():
            rt_val, svc = key.split(":", 1)

            # Get actual utilization from monitor
            try:
                rt = ResourceType(rt_val)
                metric = self.monitor.get_current_utilization(rt, svc)
                util = metric.utilization_pct if metric else cost.utilization_pct
            except (ValueError, KeyError):
                util = cost.utilization_pct

            if util < threshold_pct and cost.monthly_cost > 0:
                # Recommend sizing down proportionally
                ratio = max(util / 100.0, 0.1) if util > 0 else 0.1
                recommended = round(cost.monthly_cost * (ratio + 0.2), 2)
                recommended = min(recommended, cost.monthly_cost)

                savings_amount = cost.monthly_cost - recommended
                if savings_amount > 0:
                    opportunities.append(
                        SavingsOpportunity(
                            resource=ResourceType(rt_val),
                            service=svc,
                            current_cost=cost.monthly_cost,
                            recommended_cost=recommended,
                            action=f"Right-size {rt_val} for {svc} (util: {util:.1f}%)",
                        )
                    )

        return opportunities

    def right_size_recommendations(self) -> List[Dict]:
        """Get right-sizing recommendations for all resources."""
        recommendations = []

        for key, cost in self._cost_rates.items():
            rt_val, svc = key.split(":", 1)
            try:
                rt = ResourceType(rt_val)
                metric = self.monitor.get_current_utilization(rt, svc)
                util = metric.utilization_pct if metric else cost.utilization_pct
            except (ValueError, KeyError):
                util = cost.utilization_pct

            if util < 30:
                action = "downsize"
                target_pct = 50.0
            elif util > 80:
                action = "upsize"
                target_pct = 60.0
            else:
                action = "maintain"
                target_pct = util

            recommendations.append({
                "resource": rt_val,
                "service": svc,
                "current_utilization_pct": round(util, 1),
                "action": action,
                "target_utilization_pct": target_pct,
                "current_monthly_cost": cost.monthly_cost,
                "estimated_monthly_cost": round(
                    cost.monthly_cost * (target_pct / max(util, 1)) if action != "maintain" else cost.monthly_cost,
                    2,
                ),
            })

        return recommendations

    def cost_forecast(self, months: int = 6) -> List[Dict]:
        """Forecast costs for the next N months."""
        current_report = self.calculate_costs("monthly")
        base_cost = current_report.total_cost

        # Simple growth model: 5% monthly growth rate
        growth_rate = 0.05
        projections = []
        now = datetime.now(timezone.utc)

        for i in range(1, months + 1):
            projected = round(base_cost * ((1 + growth_rate) ** i), 2)
            month_dt = now + timedelta(days=30 * i)
            projections.append({
                "month": month_dt.strftime("%Y-%m"),
                "projected_cost": projected,
                "growth_pct": round(growth_rate * 100 * i, 1),
            })

        return projections

    def cost_per_trade(self) -> float:
        """Calculate the cost per trade."""
        if self._trade_count <= 0:
            return 0.0
        report = self.calculate_costs("monthly")
        return round(report.total_cost / self._trade_count, 4)

    def efficiency_score(self) -> float:
        """Calculate overall cost efficiency score (0-100).

        Higher score means better cost efficiency.
        """
        if not self._cost_rates:
            return 100.0

        utilizations = []
        for key, cost in self._cost_rates.items():
            rt_val, svc = key.split(":", 1)
            try:
                rt = ResourceType(rt_val)
                metric = self.monitor.get_current_utilization(rt, svc)
                util = metric.utilization_pct if metric else cost.utilization_pct
            except (ValueError, KeyError):
                util = cost.utilization_pct
            utilizations.append(util)

        if not utilizations:
            return 100.0

        avg_util = sum(utilizations) / len(utilizations)

        # Score: penalty for both under-utilization and over-utilization
        # Optimal is around 60-70%
        optimal = 65.0
        deviation = abs(avg_util - optimal)
        score = max(0.0, 100.0 - deviation * 1.5)
        return round(score, 1)
