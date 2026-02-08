"""Configuration for compliance engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SurveillanceType(str, Enum):
    WASH_TRADE = "wash_trade"
    LAYERING = "layering"
    SPOOFING = "spoofing"
    FRONT_RUNNING = "front_running"
    INSIDER_TRADING = "insider_trading"
    PUMP_AND_DUMP = "pump_and_dump"
    EXCESSIVE_TRADING = "excessive_trading"
    MARKING_CLOSE = "marking_close"


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BlackoutStatus(str, Enum):
    OPEN = "open"
    BLACKOUT = "blackout"
    PRE_CLEARANCE_REQUIRED = "pre_clearance_required"


class ExecutionQuality(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    FAILED = "failed"


class ReportType(str, Enum):
    DAILY_COMPLIANCE = "daily_compliance"
    BEST_EXECUTION = "best_execution"
    SURVEILLANCE_SUMMARY = "surveillance_summary"
    INSIDER_TRADING = "insider_trading"
    VIOLATION_LOG = "violation_log"


# Thresholds for surveillance detection
WASH_TRADE_WINDOW_SECONDS = 300  # 5 minutes
WASH_TRADE_PRICE_TOLERANCE = 0.001  # 0.1%
LAYERING_ORDER_THRESHOLD = 5  # 5+ orders on same side
SPOOFING_CANCEL_RATIO = 0.90  # 90% cancel rate
EXCESSIVE_TRADING_THRESHOLD = 50  # trades per day
MARKING_CLOSE_WINDOW_MINUTES = 5  # last 5 minutes


@dataclass
class SurveillanceConfig:
    """Configuration for trade surveillance."""

    wash_trade_window: int = WASH_TRADE_WINDOW_SECONDS
    wash_trade_price_tolerance: float = WASH_TRADE_PRICE_TOLERANCE
    layering_threshold: int = LAYERING_ORDER_THRESHOLD
    spoofing_cancel_ratio: float = SPOOFING_CANCEL_RATIO
    excessive_trading_limit: int = EXCESSIVE_TRADING_THRESHOLD
    marking_close_window_min: int = MARKING_CLOSE_WINDOW_MINUTES
    enabled_checks: List[SurveillanceType] = field(default_factory=lambda: list(SurveillanceType))


@dataclass
class BlackoutConfig:
    """Configuration for insider trading blackout windows."""

    default_blackout_days_before: int = 14
    default_blackout_days_after: int = 2
    require_pre_clearance: bool = True
    pre_clearance_valid_days: int = 5
    max_trade_value_without_clearance: float = 10_000


@dataclass
class BestExecutionConfig:
    """Configuration for best execution monitoring."""

    max_slippage_bps: float = 10.0
    excellent_threshold_bps: float = 2.0
    good_threshold_bps: float = 5.0
    acceptable_threshold_bps: float = 10.0
    min_price_improvement_pct: float = 0.0
    review_period_days: int = 30
