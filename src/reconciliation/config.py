"""PRD-126: Trade Reconciliation — Configuration & enums."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ReconciliationStatus(str, Enum):
    PENDING = "pending"
    MATCHED = "matched"
    BROKEN = "broken"
    RESOLVED = "resolved"
    SETTLED = "settled"


class BreakType(str, Enum):
    PRICE_MISMATCH = "price_mismatch"
    QUANTITY_MISMATCH = "quantity_mismatch"
    MISSING_BROKER = "missing_broker"
    MISSING_INTERNAL = "missing_internal"
    TIMING = "timing"
    DUPLICATE = "duplicate"
    SIDE_MISMATCH = "side_mismatch"


class SettlementStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SETTLED = "settled"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MatchStrategy(str, Enum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    MANUAL = "manual"


class BreakSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ToleranceConfig:
    """Tolerance thresholds for fuzzy matching."""

    price_tolerance_pct: float = 0.01  # 1% price tolerance
    quantity_tolerance_pct: float = 0.0  # exact quantity by default
    time_window_seconds: int = 300  # 5 min window
    allow_partial_fills: bool = True


@dataclass
class ReconciliationConfig:
    """Configuration for the reconciliation engine."""

    strategy: MatchStrategy = MatchStrategy.FUZZY
    tolerances: ToleranceConfig = field(default_factory=ToleranceConfig)
    auto_resolve_threshold: float = 0.99  # confidence threshold for auto-resolve
    settlement_days: int = 2  # T+2 default
    max_breaks_before_halt: int = 100
    enable_duplicate_detection: bool = True
    reconcile_interval_minutes: int = 15
