"""PRD-125: Cost & Usage Metering + Billing — Usage Meter."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from .config import BillingPeriod, MeterType, PricingTier


@dataclass
class MeterDefinition:
    """Definition of a billable meter."""

    meter_id: str
    name: str
    meter_type: MeterType
    unit: str
    price_per_unit: float
    tier_pricing: Dict[str, float] = field(default_factory=dict)
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class UsageRecord:
    """Single usage event."""

    record_id: str
    meter_id: str
    workspace_id: str
    quantity: float
    cost: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period: BillingPeriod = BillingPeriod.MONTHLY
    metadata: Dict[str, str] = field(default_factory=dict)


class UsageMeter:
    """Real-time usage metering and cost calculation."""

    def __init__(self) -> None:
        self._meters: Dict[str, MeterDefinition] = {}
        self._records: List[UsageRecord] = []

    # ── Meter Management ──────────────────────────────────────────────

    def define_meter(
        self,
        name: str,
        meter_type: MeterType,
        unit: str,
        price_per_unit: float,
        tier_pricing: Optional[Dict[str, float]] = None,
        description: str = "",
    ) -> MeterDefinition:
        """Register a new billing meter."""
        meter_id = uuid.uuid4().hex[:16]
        meter = MeterDefinition(
            meter_id=meter_id,
            name=name,
            meter_type=meter_type,
            unit=unit,
            price_per_unit=price_per_unit,
            tier_pricing=tier_pricing or {},
            description=description,
        )
        self._meters[meter_id] = meter
        return meter

    def get_meter(self, meter_id: str) -> Optional[MeterDefinition]:
        """Retrieve meter definition by ID."""
        return self._meters.get(meter_id)

    def list_meters(self) -> List[MeterDefinition]:
        """List all defined meters."""
        return list(self._meters.values())

    # ── Usage Recording ───────────────────────────────────────────────

    def record_usage(
        self,
        meter_id: str,
        workspace_id: str,
        quantity: float,
        period: BillingPeriod = BillingPeriod.MONTHLY,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> UsageRecord:
        """Record a usage event and calculate cost."""
        meter = self._meters.get(meter_id)
        if meter is None:
            raise ValueError(f"Unknown meter: {meter_id}")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        cost = self._calculate_cost(meter, quantity, workspace_id)
        record = UsageRecord(
            record_id=uuid.uuid4().hex[:16],
            meter_id=meter_id,
            workspace_id=workspace_id,
            quantity=quantity,
            cost=cost,
            timestamp=timestamp or datetime.now(timezone.utc),
            period=period,
            metadata=metadata or {},
        )
        self._records.append(record)
        return record

    def _calculate_cost(
        self, meter: MeterDefinition, quantity: float, workspace_id: str
    ) -> float:
        """Calculate cost using tiered pricing if available."""
        if meter.tier_pricing:
            # Sum existing usage for the workspace on this meter
            existing = sum(
                r.quantity
                for r in self._records
                if r.meter_id == meter.meter_id and r.workspace_id == workspace_id
            )
            total_after = existing + quantity
            # Tiered pricing: keys are string threshold, values are per-unit price
            sorted_tiers = sorted(
                [(int(k), v) for k, v in meter.tier_pricing.items()], key=lambda t: t[0]
            )
            cost = 0.0
            remaining = quantity
            prev_threshold = 0
            for threshold, tier_price in sorted_tiers:
                if existing >= threshold:
                    prev_threshold = threshold
                    continue
                tier_quantity = min(remaining, threshold - max(existing, prev_threshold))
                if tier_quantity > 0:
                    cost += tier_quantity * tier_price
                    remaining -= tier_quantity
                prev_threshold = threshold
                if remaining <= 0:
                    break
            # Any remaining quantity uses last tier price or base price
            if remaining > 0:
                last_price = sorted_tiers[-1][1] if sorted_tiers else meter.price_per_unit
                cost += remaining * last_price
            return round(cost, 4)
        return round(quantity * meter.price_per_unit, 4)

    # ── Queries ───────────────────────────────────────────────────────

    def get_usage(
        self,
        meter_id: str,
        workspace_id: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[UsageRecord]:
        """Query usage records with optional filters."""
        results = [r for r in self._records if r.meter_id == meter_id]
        if workspace_id:
            results = [r for r in results if r.workspace_id == workspace_id]
        if start:
            results = [r for r in results if r.timestamp >= start]
        if end:
            results = [r for r in results if r.timestamp <= end]
        return results

    def get_cost_summary(
        self,
        workspace_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """Get cost breakdown by meter type for a workspace."""
        records = [r for r in self._records if r.workspace_id == workspace_id]
        if start:
            records = [r for r in records if r.timestamp >= start]
        if end:
            records = [r for r in records if r.timestamp <= end]

        summary: Dict[str, float] = {}
        for record in records:
            meter = self._meters.get(record.meter_id)
            if meter:
                key = meter.meter_type.value
                summary[key] = summary.get(key, 0.0) + record.cost
        # Round values
        return {k: round(v, 4) for k, v in summary.items()}

    def get_workspace_usage(self, workspace_id: str) -> List[UsageRecord]:
        """Get all usage records for a workspace."""
        return [r for r in self._records if r.workspace_id == workspace_id]

    def reset_period(self, workspace_id: Optional[str] = None) -> int:
        """Reset usage records, optionally for a specific workspace. Returns count removed."""
        if workspace_id:
            before = len(self._records)
            self._records = [
                r for r in self._records if r.workspace_id != workspace_id
            ]
            return before - len(self._records)
        count = len(self._records)
        self._records.clear()
        return count

    def get_statistics(self) -> Dict[str, object]:
        """Get aggregate metering statistics."""
        total_records = len(self._records)
        total_cost = sum(r.cost for r in self._records)
        total_quantity = sum(r.quantity for r in self._records)
        workspaces = set(r.workspace_id for r in self._records)
        meters = set(r.meter_id for r in self._records)
        return {
            "total_records": total_records,
            "total_cost": round(total_cost, 4),
            "total_quantity": round(total_quantity, 4),
            "unique_workspaces": len(workspaces),
            "active_meters": len(meters),
            "defined_meters": len(self._meters),
        }
