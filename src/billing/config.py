"""PRD-125: Cost & Usage Metering + Billing — Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class MeterType(Enum):
    """Types of billable meters."""

    API_CALL = "api_call"
    DATA_FEED = "data_feed"
    BACKTEST_RUN = "backtest_run"
    MODEL_TRAINING = "model_training"
    STORAGE_GB = "storage_gb"


class InvoiceStatus(Enum):
    """Invoice lifecycle states."""

    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class BillingPeriod(Enum):
    """Billing period granularity."""

    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"


class PricingTier(Enum):
    """Subscription pricing tiers."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass
class BillingConfig:
    """Global billing configuration."""

    default_period: BillingPeriod = BillingPeriod.MONTHLY
    tax_rate: float = 0.0
    currency: str = "USD"
    grace_period_days: int = 7
    invoice_prefix: str = "INV"
    auto_finalize: bool = False
    send_reminders: bool = True
    reminder_days_before_due: int = 3
    overdue_penalty_rate: float = 0.0
    max_credit_balance: float = 10000.0
