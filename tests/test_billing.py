"""Tests for PRD-125: Cost & Usage Metering + Billing."""

from datetime import datetime, timezone, timedelta
import json

import pytest

from src.billing.config import (
    MeterType,
    InvoiceStatus,
    BillingPeriod,
    PricingTier,
    BillingConfig,
)
from src.billing.meter import MeterDefinition, UsageRecord, UsageMeter
from src.billing.engine import BillLineItem, Bill, BillingEngine
from src.billing.invoices import Invoice, InvoiceManager
from src.billing.analytics import CostBreakdown, CostAnalytics


# ── Config Tests ──────────────────────────────────────────────────────


class TestBillingConfig:
    def test_meter_type_values(self):
        assert MeterType.API_CALL.value == "api_call"
        assert MeterType.DATA_FEED.value == "data_feed"
        assert MeterType.BACKTEST_RUN.value == "backtest_run"
        assert MeterType.MODEL_TRAINING.value == "model_training"
        assert MeterType.STORAGE_GB.value == "storage_gb"

    def test_meter_type_count(self):
        assert len(MeterType) == 5

    def test_invoice_status_values(self):
        assert InvoiceStatus.DRAFT.value == "draft"
        assert InvoiceStatus.SENT.value == "sent"
        assert InvoiceStatus.PAID.value == "paid"
        assert InvoiceStatus.OVERDUE.value == "overdue"
        assert InvoiceStatus.CANCELLED.value == "cancelled"
        assert InvoiceStatus.REFUNDED.value == "refunded"

    def test_invoice_status_count(self):
        assert len(InvoiceStatus) == 6

    def test_billing_period_values(self):
        assert BillingPeriod.HOURLY.value == "hourly"
        assert BillingPeriod.DAILY.value == "daily"
        assert BillingPeriod.MONTHLY.value == "monthly"

    def test_billing_period_count(self):
        assert len(BillingPeriod) == 3

    def test_pricing_tier_values(self):
        assert PricingTier.FREE.value == "free"
        assert PricingTier.STARTER.value == "starter"
        assert PricingTier.PROFESSIONAL.value == "professional"
        assert PricingTier.ENTERPRISE.value == "enterprise"

    def test_pricing_tier_count(self):
        assert len(PricingTier) == 4

    def test_billing_config_defaults(self):
        cfg = BillingConfig()
        assert cfg.default_period == BillingPeriod.MONTHLY
        assert cfg.tax_rate == 0.0
        assert cfg.currency == "USD"
        assert cfg.grace_period_days == 7

    def test_billing_config_custom(self):
        cfg = BillingConfig(
            default_period=BillingPeriod.DAILY,
            tax_rate=0.08,
            currency="EUR",
            grace_period_days=14,
        )
        assert cfg.default_period == BillingPeriod.DAILY
        assert cfg.tax_rate == 0.08
        assert cfg.currency == "EUR"
        assert cfg.grace_period_days == 14

    def test_billing_config_extra_fields(self):
        cfg = BillingConfig()
        assert cfg.invoice_prefix == "INV"
        assert cfg.auto_finalize is False
        assert cfg.send_reminders is True
        assert cfg.reminder_days_before_due == 3
        assert cfg.overdue_penalty_rate == 0.0
        assert cfg.max_credit_balance == 10000.0


# ── Dataclass Tests ───────────────────────────────────────────────────


class TestBillingDataclasses:
    def test_meter_definition(self):
        m = MeterDefinition(
            meter_id="m1", name="API", meter_type=MeterType.API_CALL,
            unit="calls", price_per_unit=0.001,
        )
        assert m.meter_id == "m1"
        assert m.name == "API"
        assert m.meter_type == MeterType.API_CALL
        assert m.unit == "calls"
        assert m.price_per_unit == 0.001
        assert m.tier_pricing == {}
        assert isinstance(m.created_at, datetime)

    def test_meter_definition_with_tiers(self):
        m = MeterDefinition(
            meter_id="m2", name="Data", meter_type=MeterType.DATA_FEED,
            unit="feeds", price_per_unit=5.0,
            tier_pricing={"100": 4.0, "1000": 3.0},
        )
        assert m.tier_pricing == {"100": 4.0, "1000": 3.0}

    def test_usage_record(self):
        r = UsageRecord(
            record_id="r1", meter_id="m1", workspace_id="ws1",
            quantity=100, cost=10.0,
        )
        assert r.record_id == "r1"
        assert r.quantity == 100
        assert r.cost == 10.0
        assert r.period == BillingPeriod.MONTHLY
        assert isinstance(r.timestamp, datetime)

    def test_bill_line_item(self):
        li = BillLineItem(
            description="API usage", meter_type=MeterType.API_CALL,
            quantity=1000, unit_price=0.001, amount=1.0,
        )
        assert li.description == "API usage"
        assert li.amount == 1.0

    def test_bill(self):
        now = datetime.now(timezone.utc)
        b = Bill(
            bill_id="b1", workspace_id="ws1",
            period_start=now - timedelta(days=30), period_end=now,
        )
        assert b.bill_id == "b1"
        assert b.status == InvoiceStatus.DRAFT
        assert b.subtotal == 0.0
        assert b.line_items == []

    def test_invoice(self):
        inv = Invoice(
            invoice_id="INV-123", bill_id="b1",
            workspace_id="ws1", amount=100.0,
        )
        assert inv.invoice_id == "INV-123"
        assert inv.status == InvoiceStatus.DRAFT
        assert inv.sent_at is None
        assert inv.paid_at is None
        assert inv.line_items_json == "[]"

    def test_cost_breakdown(self):
        cb = CostBreakdown(workspace_id="ws1", period="2024-01")
        assert cb.total == 0.0
        assert cb.trend_pct == 0.0
        assert cb.by_meter == {}


# ── UsageMeter Tests ──────────────────────────────────────────────────


class TestUsageMeter:
    def setup_method(self):
        self.meter = UsageMeter()
        self.api_meter = self.meter.define_meter(
            "API Calls", MeterType.API_CALL, "calls", 0.001,
        )
        self.data_meter = self.meter.define_meter(
            "Data Feed", MeterType.DATA_FEED, "feeds", 5.0,
        )

    def test_define_meter(self):
        assert self.api_meter.name == "API Calls"
        assert self.api_meter.meter_type == MeterType.API_CALL
        assert self.api_meter.price_per_unit == 0.001
        assert len(self.api_meter.meter_id) == 16

    def test_define_meter_with_description(self):
        m = self.meter.define_meter(
            "Storage", MeterType.STORAGE_GB, "GB", 0.10,
            description="Per-GB storage",
        )
        assert m.description == "Per-GB storage"

    def test_get_meter(self):
        found = self.meter.get_meter(self.api_meter.meter_id)
        assert found is not None
        assert found.name == "API Calls"

    def test_get_meter_not_found(self):
        assert self.meter.get_meter("nonexistent") is None

    def test_list_meters(self):
        meters = self.meter.list_meters()
        assert len(meters) == 2

    def test_record_usage(self):
        record = self.meter.record_usage(self.api_meter.meter_id, "ws1", 1000)
        assert record.quantity == 1000
        assert record.cost == 1.0
        assert record.workspace_id == "ws1"
        assert len(record.record_id) == 16

    def test_record_usage_cost_calculation(self):
        record = self.meter.record_usage(self.data_meter.meter_id, "ws1", 3)
        assert record.cost == 15.0

    def test_record_usage_unknown_meter(self):
        with pytest.raises(ValueError, match="Unknown meter"):
            self.meter.record_usage("bad_id", "ws1", 100)

    def test_record_usage_zero_quantity(self):
        with pytest.raises(ValueError, match="Quantity must be positive"):
            self.meter.record_usage(self.api_meter.meter_id, "ws1", 0)

    def test_record_usage_negative_quantity(self):
        with pytest.raises(ValueError, match="Quantity must be positive"):
            self.meter.record_usage(self.api_meter.meter_id, "ws1", -5)

    def test_record_usage_with_metadata(self):
        record = self.meter.record_usage(
            self.api_meter.meter_id, "ws1", 500,
            metadata={"endpoint": "/api/v1/quotes"},
        )
        assert record.metadata == {"endpoint": "/api/v1/quotes"}

    def test_record_usage_custom_timestamp(self):
        ts = datetime(2024, 6, 15, tzinfo=timezone.utc)
        record = self.meter.record_usage(
            self.api_meter.meter_id, "ws1", 100, timestamp=ts,
        )
        assert record.timestamp == ts

    def test_get_usage(self):
        self.meter.record_usage(self.api_meter.meter_id, "ws1", 100)
        self.meter.record_usage(self.api_meter.meter_id, "ws2", 200)
        records = self.meter.get_usage(self.api_meter.meter_id)
        assert len(records) == 2

    def test_get_usage_by_workspace(self):
        self.meter.record_usage(self.api_meter.meter_id, "ws1", 100)
        self.meter.record_usage(self.api_meter.meter_id, "ws2", 200)
        records = self.meter.get_usage(self.api_meter.meter_id, workspace_id="ws1")
        assert len(records) == 1
        assert records[0].workspace_id == "ws1"

    def test_get_usage_time_range(self):
        now = datetime.now(timezone.utc)
        self.meter.record_usage(
            self.api_meter.meter_id, "ws1", 100,
            timestamp=now - timedelta(hours=2),
        )
        self.meter.record_usage(
            self.api_meter.meter_id, "ws1", 200,
            timestamp=now,
        )
        records = self.meter.get_usage(
            self.api_meter.meter_id,
            start=now - timedelta(hours=1),
        )
        assert len(records) == 1
        assert records[0].quantity == 200

    def test_get_cost_summary(self):
        self.meter.record_usage(self.api_meter.meter_id, "ws1", 1000)
        self.meter.record_usage(self.data_meter.meter_id, "ws1", 2)
        summary = self.meter.get_cost_summary("ws1")
        assert summary["api_call"] == 1.0
        assert summary["data_feed"] == 10.0

    def test_get_cost_summary_empty(self):
        summary = self.meter.get_cost_summary("ws_none")
        assert summary == {}

    def test_get_workspace_usage(self):
        self.meter.record_usage(self.api_meter.meter_id, "ws1", 100)
        self.meter.record_usage(self.api_meter.meter_id, "ws2", 200)
        records = self.meter.get_workspace_usage("ws1")
        assert len(records) == 1

    def test_reset_period_all(self):
        self.meter.record_usage(self.api_meter.meter_id, "ws1", 100)
        self.meter.record_usage(self.api_meter.meter_id, "ws2", 200)
        count = self.meter.reset_period()
        assert count == 2
        assert self.meter.get_statistics()["total_records"] == 0

    def test_reset_period_workspace(self):
        self.meter.record_usage(self.api_meter.meter_id, "ws1", 100)
        self.meter.record_usage(self.api_meter.meter_id, "ws2", 200)
        count = self.meter.reset_period("ws1")
        assert count == 1
        assert self.meter.get_statistics()["total_records"] == 1

    def test_get_statistics(self):
        self.meter.record_usage(self.api_meter.meter_id, "ws1", 1000)
        self.meter.record_usage(self.data_meter.meter_id, "ws2", 2)
        stats = self.meter.get_statistics()
        assert stats["total_records"] == 2
        assert stats["total_cost"] == 11.0
        assert stats["unique_workspaces"] == 2
        assert stats["active_meters"] == 2
        assert stats["defined_meters"] == 2

    def test_tiered_pricing(self):
        tiered = self.meter.define_meter(
            "Tiered API", MeterType.API_CALL, "calls", 0.01,
            tier_pricing={"100": 0.01, "500": 0.008, "1000": 0.005},
        )
        record = self.meter.record_usage(tiered.meter_id, "ws1", 50)
        assert record.cost == 0.5  # 50 * 0.01


# ── BillingEngine Tests ──────────────────────────────────────────────


class TestBillingEngine:
    def setup_method(self):
        self.config = BillingConfig(tax_rate=0.10)
        self.meter = UsageMeter()
        self.engine = BillingEngine(self.meter, self.config)
        self.api_meter = self.meter.define_meter(
            "API Calls", MeterType.API_CALL, "calls", 0.001,
        )
        self.data_meter = self.meter.define_meter(
            "Data Feed", MeterType.DATA_FEED, "feeds", 5.0,
        )
        self.now = datetime.now(timezone.utc)
        self.period_start = self.now - timedelta(days=30)
        self.period_end = self.now

    def _add_usage(self, ws="ws1"):
        self.meter.record_usage(
            self.api_meter.meter_id, ws, 10000,
            timestamp=self.now - timedelta(days=15),
        )
        self.meter.record_usage(
            self.data_meter.meter_id, ws, 2,
            timestamp=self.now - timedelta(days=10),
        )

    def test_generate_bill(self):
        self._add_usage()
        bill = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        assert bill.workspace_id == "ws1"
        assert len(bill.line_items) == 2
        assert bill.subtotal == 20.0  # 10 + 10
        assert bill.tax == 2.0  # 10% of 20
        assert bill.total == 22.0
        assert bill.status == InvoiceStatus.DRAFT

    def test_generate_bill_no_usage(self):
        bill = self.engine.generate_bill("ws_empty", self.period_start, self.period_end)
        assert bill.subtotal == 0.0
        assert bill.total == 0.0
        assert len(bill.line_items) == 0

    def test_generate_bill_id_format(self):
        self._add_usage()
        bill = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        assert len(bill.bill_id) == 16

    def test_apply_discount(self):
        self._add_usage()
        bill = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        updated = self.engine.apply_discount(bill.bill_id, 5.0, "Loyalty discount")
        assert updated.discounts == 5.0
        assert updated.total == 17.0  # 22 - 5

    def test_apply_discount_not_found(self):
        with pytest.raises(ValueError, match="Bill not found"):
            self.engine.apply_discount("bad_id", 5.0)

    def test_apply_discount_non_draft(self):
        self._add_usage()
        bill = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        self.engine.finalize_bill(bill.bill_id)
        with pytest.raises(ValueError, match="DRAFT"):
            self.engine.apply_discount(bill.bill_id, 5.0)

    def test_apply_discount_negative(self):
        self._add_usage()
        bill = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        with pytest.raises(ValueError, match="non-negative"):
            self.engine.apply_discount(bill.bill_id, -1.0)

    def test_apply_credit(self):
        self._add_usage()
        bill = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        updated = self.engine.apply_credit(bill.bill_id, 3.0, "Promo credit")
        assert updated.credits == 3.0
        assert updated.total == 19.0  # 22 - 3

    def test_apply_credit_not_found(self):
        with pytest.raises(ValueError, match="Bill not found"):
            self.engine.apply_credit("bad_id", 3.0)

    def test_apply_credit_non_draft(self):
        self._add_usage()
        bill = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        self.engine.finalize_bill(bill.bill_id)
        with pytest.raises(ValueError, match="DRAFT"):
            self.engine.apply_credit(bill.bill_id, 3.0)

    def test_apply_credit_negative(self):
        self._add_usage()
        bill = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        with pytest.raises(ValueError, match="non-negative"):
            self.engine.apply_credit(bill.bill_id, -1.0)

    def test_apply_discount_and_credit(self):
        self._add_usage()
        bill = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        self.engine.apply_discount(bill.bill_id, 5.0)
        self.engine.apply_credit(bill.bill_id, 3.0)
        assert bill.total == 14.0  # 22 - 5 - 3

    def test_total_floor_zero(self):
        self._add_usage()
        bill = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        self.engine.apply_discount(bill.bill_id, 100.0)
        assert bill.total == 0.0

    def test_finalize_bill(self):
        self._add_usage()
        bill = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        finalized = self.engine.finalize_bill(bill.bill_id)
        assert finalized.status == InvoiceStatus.SENT

    def test_finalize_bill_not_found(self):
        with pytest.raises(ValueError, match="Bill not found"):
            self.engine.finalize_bill("bad_id")

    def test_finalize_bill_already_finalized(self):
        self._add_usage()
        bill = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        self.engine.finalize_bill(bill.bill_id)
        with pytest.raises(ValueError, match="DRAFT"):
            self.engine.finalize_bill(bill.bill_id)

    def test_get_bill(self):
        self._add_usage()
        bill = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        found = self.engine.get_bill(bill.bill_id)
        assert found is not None
        assert found.bill_id == bill.bill_id

    def test_get_bill_not_found(self):
        assert self.engine.get_bill("nonexistent") is None

    def test_list_bills(self):
        self._add_usage("ws1")
        self._add_usage("ws2")
        self.engine.generate_bill("ws1", self.period_start, self.period_end)
        self.engine.generate_bill("ws2", self.period_start, self.period_end)
        assert len(self.engine.list_bills()) == 2

    def test_list_bills_filter_workspace(self):
        self._add_usage("ws1")
        self._add_usage("ws2")
        self.engine.generate_bill("ws1", self.period_start, self.period_end)
        self.engine.generate_bill("ws2", self.period_start, self.period_end)
        bills = self.engine.list_bills(workspace_id="ws1")
        assert len(bills) == 1
        assert bills[0].workspace_id == "ws1"

    def test_list_bills_filter_status(self):
        self._add_usage("ws1")
        b1 = self.engine.generate_bill("ws1", self.period_start, self.period_end)
        self._add_usage("ws2")
        self.engine.generate_bill("ws2", self.period_start, self.period_end)
        self.engine.finalize_bill(b1.bill_id)
        drafts = self.engine.list_bills(status=InvoiceStatus.DRAFT)
        assert len(drafts) == 1

    def test_get_revenue_summary(self):
        self._add_usage("ws1")
        self._add_usage("ws2")
        self.engine.generate_bill("ws1", self.period_start, self.period_end)
        self.engine.generate_bill("ws2", self.period_start, self.period_end)
        summary = self.engine.get_revenue_summary()
        assert summary["bill_count"] == 2
        assert summary["total_revenue"] == 44.0
        assert summary["avg_bill_amount"] == 22.0

    def test_config_property(self):
        assert self.engine.config.tax_rate == 0.10


# ── InvoiceManager Tests ─────────────────────────────────────────────


class TestInvoiceManager:
    def setup_method(self):
        self.config = BillingConfig(grace_period_days=14)
        self.mgr = InvoiceManager(self.config)

    def _create_invoice(self, ws="ws1", amount=100.0):
        return self.mgr.create_invoice("bill1", ws, amount)

    def test_create_invoice(self):
        inv = self._create_invoice()
        assert inv.workspace_id == "ws1"
        assert inv.amount == 100.0
        assert inv.status == InvoiceStatus.DRAFT
        assert inv.invoice_id.startswith("INV-")

    def test_create_invoice_due_date(self):
        inv = self._create_invoice()
        assert inv.due_date is not None
        expected = datetime.now(timezone.utc) + timedelta(days=14)
        diff = abs((inv.due_date - expected).total_seconds())
        assert diff < 5  # within 5 seconds

    def test_create_invoice_custom_due_date(self):
        due = datetime(2025, 12, 31, tzinfo=timezone.utc)
        inv = self.mgr.create_invoice("b1", "ws1", 50.0, due_date=due)
        assert inv.due_date == due

    def test_create_invoice_with_line_items(self):
        items = [{"desc": "API", "amount": 50.0}, {"desc": "Data", "amount": 50.0}]
        inv = self.mgr.create_invoice("b1", "ws1", 100.0, line_items=items)
        parsed = json.loads(inv.line_items_json)
        assert len(parsed) == 2

    def test_create_invoice_negative_amount(self):
        with pytest.raises(ValueError, match="non-negative"):
            self.mgr.create_invoice("b1", "ws1", -10.0)

    def test_create_invoice_payment_method(self):
        inv = self.mgr.create_invoice("b1", "ws1", 100.0, payment_method="credit_card")
        assert inv.payment_method == "credit_card"

    def test_send_invoice(self):
        inv = self._create_invoice()
        sent = self.mgr.send_invoice(inv.invoice_id)
        assert sent.status == InvoiceStatus.SENT
        assert sent.sent_at is not None

    def test_send_invoice_not_found(self):
        with pytest.raises(ValueError, match="Invoice not found"):
            self.mgr.send_invoice("bad_id")

    def test_send_invoice_already_sent(self):
        inv = self._create_invoice()
        self.mgr.send_invoice(inv.invoice_id)
        with pytest.raises(ValueError, match="DRAFT"):
            self.mgr.send_invoice(inv.invoice_id)

    def test_record_payment(self):
        inv = self._create_invoice()
        self.mgr.send_invoice(inv.invoice_id)
        paid = self.mgr.record_payment(inv.invoice_id, "bank_transfer")
        assert paid.status == InvoiceStatus.PAID
        assert paid.paid_at is not None
        assert paid.payment_method == "bank_transfer"

    def test_record_payment_overdue(self):
        inv = self._create_invoice()
        self.mgr.send_invoice(inv.invoice_id)
        self.mgr.mark_overdue(inv.invoice_id)
        paid = self.mgr.record_payment(inv.invoice_id)
        assert paid.status == InvoiceStatus.PAID

    def test_record_payment_not_found(self):
        with pytest.raises(ValueError, match="Invoice not found"):
            self.mgr.record_payment("bad_id")

    def test_record_payment_draft(self):
        inv = self._create_invoice()
        with pytest.raises(ValueError, match="SENT or OVERDUE"):
            self.mgr.record_payment(inv.invoice_id)

    def test_mark_overdue(self):
        inv = self._create_invoice()
        self.mgr.send_invoice(inv.invoice_id)
        overdue = self.mgr.mark_overdue(inv.invoice_id)
        assert overdue.status == InvoiceStatus.OVERDUE

    def test_mark_overdue_not_sent(self):
        inv = self._create_invoice()
        with pytest.raises(ValueError, match="SENT"):
            self.mgr.mark_overdue(inv.invoice_id)

    def test_issue_refund(self):
        inv = self._create_invoice()
        self.mgr.send_invoice(inv.invoice_id)
        self.mgr.record_payment(inv.invoice_id)
        refunded = self.mgr.issue_refund(inv.invoice_id, "Duplicate charge")
        assert refunded.status == InvoiceStatus.REFUNDED
        assert refunded.notes == "Duplicate charge"

    def test_issue_refund_not_paid(self):
        inv = self._create_invoice()
        with pytest.raises(ValueError, match="PAID"):
            self.mgr.issue_refund(inv.invoice_id)

    def test_cancel_invoice_draft(self):
        inv = self._create_invoice()
        cancelled = self.mgr.cancel_invoice(inv.invoice_id)
        assert cancelled.status == InvoiceStatus.CANCELLED

    def test_cancel_invoice_sent(self):
        inv = self._create_invoice()
        self.mgr.send_invoice(inv.invoice_id)
        cancelled = self.mgr.cancel_invoice(inv.invoice_id)
        assert cancelled.status == InvoiceStatus.CANCELLED

    def test_cancel_invoice_paid(self):
        inv = self._create_invoice()
        self.mgr.send_invoice(inv.invoice_id)
        self.mgr.record_payment(inv.invoice_id)
        with pytest.raises(ValueError, match="DRAFT or SENT"):
            self.mgr.cancel_invoice(inv.invoice_id)

    def test_get_invoice(self):
        inv = self._create_invoice()
        found = self.mgr.get_invoice(inv.invoice_id)
        assert found is not None
        assert found.invoice_id == inv.invoice_id

    def test_get_invoice_not_found(self):
        assert self.mgr.get_invoice("nonexistent") is None

    def test_list_invoices(self):
        self._create_invoice("ws1")
        self._create_invoice("ws2")
        assert len(self.mgr.list_invoices()) == 2

    def test_list_invoices_filter_workspace(self):
        self._create_invoice("ws1")
        self._create_invoice("ws2")
        invoices = self.mgr.list_invoices(workspace_id="ws1")
        assert len(invoices) == 1

    def test_list_invoices_filter_status(self):
        inv1 = self._create_invoice("ws1")
        self._create_invoice("ws2")
        self.mgr.send_invoice(inv1.invoice_id)
        sent = self.mgr.list_invoices(status=InvoiceStatus.SENT)
        assert len(sent) == 1

    def test_get_statistics(self):
        inv1 = self._create_invoice("ws1", 100.0)
        inv2 = self._create_invoice("ws2", 200.0)
        self.mgr.send_invoice(inv1.invoice_id)
        self.mgr.record_payment(inv1.invoice_id)
        self.mgr.send_invoice(inv2.invoice_id)
        stats = self.mgr.get_statistics()
        assert stats["total_invoices"] == 2
        assert stats["total_amount"] == 300.0
        assert stats["total_paid"] == 100.0
        assert stats["total_outstanding"] == 200.0

    def test_get_statistics_collection_rate(self):
        inv1 = self._create_invoice("ws1", 100.0)
        inv2 = self._create_invoice("ws2", 100.0)
        self.mgr.send_invoice(inv1.invoice_id)
        self.mgr.record_payment(inv1.invoice_id)
        self.mgr.send_invoice(inv2.invoice_id)
        self.mgr.record_payment(inv2.invoice_id)
        stats = self.mgr.get_statistics()
        assert stats["collection_rate"] == 1.0

    def test_get_statistics_empty(self):
        stats = self.mgr.get_statistics()
        assert stats["total_invoices"] == 0
        assert stats["collection_rate"] == 0.0

    def test_config_property(self):
        assert self.mgr.config.grace_period_days == 14


# ── CostAnalytics Tests ──────────────────────────────────────────────


class TestCostAnalytics:
    def setup_method(self):
        self.config = BillingConfig(tax_rate=0.05)
        self.meter = UsageMeter()
        self.engine = BillingEngine(self.meter, self.config)
        self.analytics = CostAnalytics(self.meter, self.engine)
        self.api_meter = self.meter.define_meter(
            "API Calls", MeterType.API_CALL, "calls", 0.001,
        )
        self.data_meter = self.meter.define_meter(
            "Data Feed", MeterType.DATA_FEED, "feeds", 5.0,
        )
        self.now = datetime.now(timezone.utc)

    def _add_usage(self, ws="ws1", api_qty=10000, data_qty=2):
        self.meter.record_usage(
            self.api_meter.meter_id, ws, api_qty,
            timestamp=self.now - timedelta(days=5),
        )
        self.meter.record_usage(
            self.data_meter.meter_id, ws, data_qty,
            timestamp=self.now - timedelta(days=3),
        )

    def test_get_workspace_costs(self):
        self._add_usage("ws1")
        breakdown = self.analytics.get_workspace_costs("ws1")
        assert breakdown.workspace_id == "ws1"
        assert breakdown.total == 20.0
        assert "api_call" in breakdown.by_meter
        assert "data_feed" in breakdown.by_meter

    def test_get_workspace_costs_empty(self):
        breakdown = self.analytics.get_workspace_costs("ws_none")
        assert breakdown.total == 0.0
        assert breakdown.by_meter == {}

    def test_get_workspace_costs_with_dates(self):
        self._add_usage("ws1")
        start = self.now - timedelta(days=10)
        end = self.now
        breakdown = self.analytics.get_workspace_costs("ws1", start, end)
        assert breakdown.total == 20.0
        assert "to" in breakdown.period

    def test_get_workspace_costs_period_string(self):
        self._add_usage("ws1")
        breakdown = self.analytics.get_workspace_costs("ws1")
        assert breakdown.period == "all-time"

    def test_get_cost_trend(self):
        self._add_usage("ws1")
        trend = self.analytics.get_cost_trend("ws1", periods=3, period_type=BillingPeriod.DAILY)
        assert len(trend) == 3
        for item in trend:
            assert isinstance(item, CostBreakdown)

    def test_get_top_consumers(self):
        self._add_usage("ws1", 20000, 4)
        self._add_usage("ws2", 10000, 2)
        self._add_usage("ws3", 5000, 1)
        top = self.analytics.get_top_consumers(limit=2)
        assert len(top) == 2
        assert top[0]["rank"] == 1
        assert top[0]["total_cost"] >= top[1]["total_cost"]

    def test_get_top_consumers_empty(self):
        top = self.analytics.get_top_consumers()
        assert top == []

    def test_get_budget_status_under(self):
        self._add_usage("ws1")
        status = self.analytics.get_budget_status("ws1", 100.0)
        assert status["status"] == "under"
        assert status["is_over_budget"] is False
        assert status["spent"] == 20.0
        assert status["remaining"] == 80.0

    def test_get_budget_status_exceeded(self):
        self._add_usage("ws1")
        status = self.analytics.get_budget_status("ws1", 10.0)
        assert status["status"] == "exceeded"
        assert status["is_over_budget"] is True
        assert status["remaining"] == 0.0

    def test_get_budget_status_warning(self):
        self._add_usage("ws1")
        status = self.analytics.get_budget_status("ws1", 25.0)
        # 20/25 = 80% -> warning
        assert status["status"] == "warning"

    def test_get_budget_status_critical(self):
        self._add_usage("ws1")
        status = self.analytics.get_budget_status("ws1", 21.5)
        # 20/21.5 = 93% -> critical
        assert status["status"] == "critical"

    def test_get_optimization_recommendations(self):
        self._add_usage("ws1")
        recs = self.analytics.get_optimization_recommendations("ws1")
        assert len(recs) >= 1
        assert all("type" in r and "message" in r for r in recs)

    def test_get_optimization_recommendations_empty(self):
        recs = self.analytics.get_optimization_recommendations("ws_none")
        assert len(recs) == 1
        assert recs[0]["type"] == "info"

    def test_get_optimization_recommendations_dominant_cost(self):
        # Make API calls dominate (>50%)
        self.meter.record_usage(
            self.api_meter.meter_id, "ws1", 100000,
            timestamp=self.now - timedelta(days=1),
        )
        self.meter.record_usage(
            self.data_meter.meter_id, "ws1", 1,
            timestamp=self.now - timedelta(days=1),
        )
        recs = self.analytics.get_optimization_recommendations("ws1")
        cost_center = [r for r in recs if r["type"] == "cost_center"]
        assert len(cost_center) >= 1

    def test_get_revenue_forecast(self):
        self._add_usage("ws1")
        self._add_usage("ws2")
        now = self.now
        self.engine.generate_bill("ws1", now - timedelta(days=60), now - timedelta(days=30))
        self.engine.generate_bill("ws2", now - timedelta(days=30), now)
        forecasts = self.analytics.get_revenue_forecast(periods_ahead=2)
        assert len(forecasts) == 2
        for f in forecasts:
            assert "period" in f
            assert "projected_revenue" in f

    def test_get_revenue_forecast_empty(self):
        forecasts = self.analytics.get_revenue_forecast()
        assert forecasts == []

    def test_get_revenue_forecast_daily(self):
        self._add_usage("ws1")
        now = self.now
        self.engine.generate_bill("ws1", now - timedelta(days=2), now - timedelta(days=1))
        forecasts = self.analytics.get_revenue_forecast(
            periods_ahead=3, period_type=BillingPeriod.DAILY,
        )
        assert len(forecasts) == 3
