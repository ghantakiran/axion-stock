"""PRD-125: Cost & Usage Metering + Billing — Billing Engine."""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import uuid

from .config import BillingConfig, BillingPeriod, InvoiceStatus, MeterType
from .meter import UsageMeter


@dataclass
class BillLineItem:
    """Single line item on a bill."""

    description: str
    meter_type: MeterType
    quantity: float
    unit_price: float
    amount: float


@dataclass
class Bill:
    """Generated bill for a workspace."""

    bill_id: str
    workspace_id: str
    period_start: datetime
    period_end: datetime
    line_items: List[BillLineItem] = field(default_factory=list)
    subtotal: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    discounts: float = 0.0
    credits: float = 0.0
    status: InvoiceStatus = InvoiceStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""


class BillingEngine:
    """Bill generation and management from metered usage."""

    def __init__(
        self,
        meter: UsageMeter,
        config: Optional[BillingConfig] = None,
    ) -> None:
        self._meter = meter
        self._config = config or BillingConfig()
        self._bills: Dict[str, Bill] = {}

    @property
    def config(self) -> BillingConfig:
        return self._config

    # ── Bill Generation ───────────────────────────────────────────────

    def generate_bill(
        self,
        workspace_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> Bill:
        """Generate a bill for a workspace based on metered usage."""
        bill_id = uuid.uuid4().hex[:16]

        # Gather usage records in the period
        records = [
            r
            for r in self._meter.get_workspace_usage(workspace_id)
            if period_start <= r.timestamp <= period_end
        ]

        # Aggregate by meter type
        agg: Dict[MeterType, Dict] = {}
        for record in records:
            meter_def = self._meter.get_meter(record.meter_id)
            if meter_def is None:
                continue
            mt = meter_def.meter_type
            if mt not in agg:
                agg[mt] = {
                    "name": meter_def.name,
                    "quantity": 0.0,
                    "cost": 0.0,
                    "unit_price": meter_def.price_per_unit,
                }
            agg[mt]["quantity"] += record.quantity
            agg[mt]["cost"] += record.cost

        # Build line items
        line_items = []
        for mt, data in agg.items():
            line_items.append(
                BillLineItem(
                    description=f"{data['name']} usage",
                    meter_type=mt,
                    quantity=round(data["quantity"], 4),
                    unit_price=data["unit_price"],
                    amount=round(data["cost"], 4),
                )
            )

        subtotal = round(sum(li.amount for li in line_items), 4)
        tax = round(subtotal * self._config.tax_rate, 4)
        total = round(subtotal + tax, 4)

        bill = Bill(
            bill_id=bill_id,
            workspace_id=workspace_id,
            period_start=period_start,
            period_end=period_end,
            line_items=line_items,
            subtotal=subtotal,
            tax=tax,
            total=total,
        )
        self._bills[bill_id] = bill
        return bill

    # ── Adjustments ───────────────────────────────────────────────────

    def apply_discount(self, bill_id: str, discount_amount: float, reason: str = "") -> Bill:
        """Apply a discount to a draft bill."""
        bill = self._bills.get(bill_id)
        if bill is None:
            raise ValueError(f"Bill not found: {bill_id}")
        if bill.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only apply discounts to DRAFT bills")
        if discount_amount < 0:
            raise ValueError("Discount amount must be non-negative")
        bill.discounts = round(bill.discounts + discount_amount, 4)
        bill.total = round(bill.subtotal + bill.tax - bill.discounts - bill.credits, 4)
        bill.total = max(bill.total, 0.0)
        if reason:
            bill.notes = f"{bill.notes}; Discount: {reason}".strip("; ")
        return bill

    def apply_credit(self, bill_id: str, credit_amount: float, reason: str = "") -> Bill:
        """Apply a credit to a draft bill."""
        bill = self._bills.get(bill_id)
        if bill is None:
            raise ValueError(f"Bill not found: {bill_id}")
        if bill.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only apply credits to DRAFT bills")
        if credit_amount < 0:
            raise ValueError("Credit amount must be non-negative")
        bill.credits = round(bill.credits + credit_amount, 4)
        bill.total = round(bill.subtotal + bill.tax - bill.discounts - bill.credits, 4)
        bill.total = max(bill.total, 0.0)
        if reason:
            bill.notes = f"{bill.notes}; Credit: {reason}".strip("; ")
        return bill

    def finalize_bill(self, bill_id: str) -> Bill:
        """Finalize a bill (no more changes allowed)."""
        bill = self._bills.get(bill_id)
        if bill is None:
            raise ValueError(f"Bill not found: {bill_id}")
        if bill.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only finalize DRAFT bills")
        bill.status = InvoiceStatus.SENT
        return bill

    # ── Queries ───────────────────────────────────────────────────────

    def get_bill(self, bill_id: str) -> Optional[Bill]:
        """Retrieve a bill by ID."""
        return self._bills.get(bill_id)

    def list_bills(
        self,
        workspace_id: Optional[str] = None,
        status: Optional[InvoiceStatus] = None,
    ) -> List[Bill]:
        """List bills with optional filters."""
        bills = list(self._bills.values())
        if workspace_id:
            bills = [b for b in bills if b.workspace_id == workspace_id]
        if status:
            bills = [b for b in bills if b.status == status]
        return sorted(bills, key=lambda b: b.created_at, reverse=True)

    def get_revenue_summary(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """Summarize revenue across all bills."""
        bills = list(self._bills.values())
        if start:
            bills = [b for b in bills if b.period_start >= start]
        if end:
            bills = [b for b in bills if b.period_end <= end]

        total_revenue = sum(b.total for b in bills)
        total_discounts = sum(b.discounts for b in bills)
        total_credits = sum(b.credits for b in bills)
        total_tax = sum(b.tax for b in bills)
        bill_count = len(bills)

        return {
            "total_revenue": round(total_revenue, 4),
            "total_discounts": round(total_discounts, 4),
            "total_credits": round(total_credits, 4),
            "total_tax": round(total_tax, 4),
            "bill_count": bill_count,
            "avg_bill_amount": round(total_revenue / bill_count, 4) if bill_count else 0.0,
        }
