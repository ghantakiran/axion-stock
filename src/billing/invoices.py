"""PRD-125: Cost & Usage Metering + Billing — Invoice Manager."""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import json
import uuid

from .config import BillingConfig, InvoiceStatus


@dataclass
class Invoice:
    """Generated invoice for a bill."""

    invoice_id: str
    bill_id: str
    workspace_id: str
    amount: float
    status: InvoiceStatus = InvoiceStatus.DRAFT
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    line_items_json: str = "[]"
    payment_method: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""


class InvoiceManager:
    """Invoice lifecycle management."""

    def __init__(self, config: Optional[BillingConfig] = None) -> None:
        self._config = config or BillingConfig()
        self._invoices: Dict[str, Invoice] = {}

    @property
    def config(self) -> BillingConfig:
        return self._config

    # ── Invoice Creation ──────────────────────────────────────────────

    def create_invoice(
        self,
        bill_id: str,
        workspace_id: str,
        amount: float,
        line_items: Optional[List[Dict]] = None,
        due_date: Optional[datetime] = None,
        payment_method: str = "",
    ) -> Invoice:
        """Create an invoice from a bill."""
        if amount < 0:
            raise ValueError("Invoice amount must be non-negative")

        invoice_id = f"{self._config.invoice_prefix}-{uuid.uuid4().hex[:16]}"
        if due_date is None:
            due_date = datetime.now(timezone.utc) + timedelta(
                days=self._config.grace_period_days
            )

        invoice = Invoice(
            invoice_id=invoice_id,
            bill_id=bill_id,
            workspace_id=workspace_id,
            amount=round(amount, 4),
            due_date=due_date,
            line_items_json=json.dumps(line_items or []),
            payment_method=payment_method,
        )
        self._invoices[invoice_id] = invoice
        return invoice

    # ── Status Transitions ────────────────────────────────────────────

    def send_invoice(self, invoice_id: str) -> Invoice:
        """Mark invoice as sent."""
        invoice = self._invoices.get(invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice not found: {invoice_id}")
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Can only send DRAFT invoices")
        invoice.status = InvoiceStatus.SENT
        invoice.sent_at = datetime.now(timezone.utc)
        return invoice

    def record_payment(
        self,
        invoice_id: str,
        payment_method: str = "",
        paid_at: Optional[datetime] = None,
    ) -> Invoice:
        """Record a payment for an invoice."""
        invoice = self._invoices.get(invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice not found: {invoice_id}")
        if invoice.status not in (InvoiceStatus.SENT, InvoiceStatus.OVERDUE):
            raise ValueError("Can only pay SENT or OVERDUE invoices")
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = paid_at or datetime.now(timezone.utc)
        if payment_method:
            invoice.payment_method = payment_method
        return invoice

    def mark_overdue(self, invoice_id: str) -> Invoice:
        """Mark a sent invoice as overdue."""
        invoice = self._invoices.get(invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice not found: {invoice_id}")
        if invoice.status != InvoiceStatus.SENT:
            raise ValueError("Can only mark SENT invoices as overdue")
        invoice.status = InvoiceStatus.OVERDUE
        return invoice

    def issue_refund(self, invoice_id: str, reason: str = "") -> Invoice:
        """Refund a paid invoice."""
        invoice = self._invoices.get(invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice not found: {invoice_id}")
        if invoice.status != InvoiceStatus.PAID:
            raise ValueError("Can only refund PAID invoices")
        invoice.status = InvoiceStatus.REFUNDED
        if reason:
            invoice.notes = reason
        return invoice

    def cancel_invoice(self, invoice_id: str) -> Invoice:
        """Cancel a draft or sent invoice."""
        invoice = self._invoices.get(invoice_id)
        if invoice is None:
            raise ValueError(f"Invoice not found: {invoice_id}")
        if invoice.status not in (InvoiceStatus.DRAFT, InvoiceStatus.SENT):
            raise ValueError("Can only cancel DRAFT or SENT invoices")
        invoice.status = InvoiceStatus.CANCELLED
        return invoice

    # ── Queries ───────────────────────────────────────────────────────

    def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """Retrieve invoice by ID."""
        return self._invoices.get(invoice_id)

    def list_invoices(
        self,
        workspace_id: Optional[str] = None,
        status: Optional[InvoiceStatus] = None,
    ) -> List[Invoice]:
        """List invoices with optional filters."""
        invoices = list(self._invoices.values())
        if workspace_id:
            invoices = [i for i in invoices if i.workspace_id == workspace_id]
        if status:
            invoices = [i for i in invoices if i.status == status]
        return sorted(invoices, key=lambda i: i.created_at, reverse=True)

    def get_statistics(self) -> Dict[str, object]:
        """Get invoice statistics."""
        invoices = list(self._invoices.values())
        total = len(invoices)
        by_status: Dict[str, int] = {}
        total_amount = 0.0
        total_paid = 0.0
        total_outstanding = 0.0

        for inv in invoices:
            status_key = inv.status.value
            by_status[status_key] = by_status.get(status_key, 0) + 1
            total_amount += inv.amount
            if inv.status == InvoiceStatus.PAID:
                total_paid += inv.amount
            elif inv.status in (InvoiceStatus.SENT, InvoiceStatus.OVERDUE):
                total_outstanding += inv.amount

        return {
            "total_invoices": total,
            "by_status": by_status,
            "total_amount": round(total_amount, 4),
            "total_paid": round(total_paid, 4),
            "total_outstanding": round(total_outstanding, 4),
            "collection_rate": round(total_paid / total_amount, 4) if total_amount else 0.0,
        }
