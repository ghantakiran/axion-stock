"""Market Scanner Data Models.

Dataclasses for scanners, criteria, results, and patterns.
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import Optional, Union, Any
import uuid

from src.scanner.config import (
    Operator,
    ScanCategory,
    ActivityType,
    PatternType,
    CandlePattern,
    SignalStrength,
    Universe,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# =============================================================================
# Scan Criteria
# =============================================================================

@dataclass
class ScanCriterion:
    """A single scan criterion."""
    criterion_id: str = field(default_factory=_new_id)
    field: str = ""
    operator: Operator = Operator.GT
    value: Union[float, tuple[float, float], str] = 0.0
    
    # Time-based
    timeframe: Optional[str] = None  # 1m, 5m, 1h, 1d
    periods_back: int = 0
    
    # Comparison field (for crosses_above/below)
    compare_field: Optional[str] = None
    
    def evaluate(self, data: dict) -> bool:
        """Evaluate criterion against data.
        
        Args:
            data: Dict with field values.
            
        Returns:
            True if criterion is met.
        """
        current = data.get(self.field)
        if current is None:
            return False
        
        if self.operator == Operator.GT:
            return current > self.value
        elif self.operator == Operator.LT:
            return current < self.value
        elif self.operator == Operator.EQ:
            return current == self.value
        elif self.operator == Operator.GTE:
            return current >= self.value
        elif self.operator == Operator.LTE:
            return current <= self.value
        elif self.operator == Operator.BETWEEN:
            if isinstance(self.value, tuple) and len(self.value) == 2:
                return self.value[0] <= current <= self.value[1]
        elif self.operator == Operator.CROSSES_ABOVE:
            prev = data.get(f"{self.field}_prev")
            threshold = self.value
            if self.compare_field:
                threshold = data.get(self.compare_field, self.value)
            if prev is not None:
                return prev < threshold and current >= threshold
        elif self.operator == Operator.CROSSES_BELOW:
            prev = data.get(f"{self.field}_prev")
            threshold = self.value
            if self.compare_field:
                threshold = data.get(self.compare_field, self.value)
            if prev is not None:
                return prev > threshold and current <= threshold
        
        return False


# =============================================================================
# Scanner Models
# =============================================================================

@dataclass
class Scanner:
    """A market scanner configuration."""
    scanner_id: str = field(default_factory=_new_id)
    name: str = ""
    description: str = ""
    category: ScanCategory = ScanCategory.CUSTOM
    
    # Criteria
    criteria: list[ScanCriterion] = field(default_factory=list)
    universe: Universe = Universe.ALL
    universe_symbols: list[str] = field(default_factory=list)
    
    # Configuration
    is_active: bool = True
    scan_interval: int = 60
    max_results: int = 50
    
    # Filters
    min_price: float = 1.0
    max_price: Optional[float] = None
    min_volume: int = 100000
    min_market_cap: float = 0
    sectors: list[str] = field(default_factory=list)
    
    # Scheduling
    active_start: Optional[time] = None
    active_end: Optional[time] = None
    active_days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    
    # Results
    last_scan: Optional[datetime] = None
    last_result_count: int = 0
    
    # Metadata
    created_at: datetime = field(default_factory=_utc_now)
    created_by: str = ""
    is_preset: bool = False


@dataclass
class ScanResult:
    """Result of a scan match."""
    result_id: str = field(default_factory=_new_id)
    scanner_id: str = ""
    scanner_name: str = ""
    symbol: str = ""
    company_name: str = ""
    
    # Match info
    matched_at: datetime = field(default_factory=_utc_now)
    matched_criteria: list[str] = field(default_factory=list)
    
    # Current values
    price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    relative_volume: float = 0.0
    
    # Scores
    signal_strength: float = 0.0  # 0-100
    
    # Context
    sector: str = ""
    market_cap: float = 0.0
    
    # Additional data
    extra_data: dict = field(default_factory=dict)


# =============================================================================
# Unusual Activity
# =============================================================================

@dataclass
class UnusualActivity:
    """Detected unusual activity."""
    activity_id: str = field(default_factory=_new_id)
    symbol: str = ""
    company_name: str = ""
    activity_type: ActivityType = ActivityType.VOLUME_SURGE
    
    # Metrics
    current_value: float = 0.0
    normal_value: float = 0.0
    deviation: float = 0.0  # Standard deviations
    percentile: float = 0.0  # Historical percentile
    
    # Context
    price: float = 0.0
    change_pct: float = 0.0
    
    # Description
    description: str = ""
    
    # Timing
    detected_at: datetime = field(default_factory=_utc_now)


# =============================================================================
# Pattern Detection
# =============================================================================

@dataclass
class ChartPattern:
    """Detected chart pattern."""
    pattern_id: str = field(default_factory=_new_id)
    symbol: str = ""
    pattern_type: PatternType = PatternType.DOUBLE_BOTTOM
    
    # Pattern details
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    pattern_length: int = 0  # bars
    
    # Price levels
    entry_price: float = 0.0
    target_price: float = 0.0
    stop_price: float = 0.0
    
    # Quality
    confidence: float = 0.0  # 0-100
    signal_strength: SignalStrength = SignalStrength.MODERATE
    
    # Breakout
    is_confirmed: bool = False
    breakout_price: Optional[float] = None
    
    # Detected
    detected_at: datetime = field(default_factory=_utc_now)


@dataclass
class CandlestickPattern:
    """Detected candlestick pattern."""
    pattern_id: str = field(default_factory=_new_id)
    symbol: str = ""
    pattern_type: CandlePattern = CandlePattern.DOJI
    
    # Pattern details
    pattern_date: Optional[datetime] = None
    is_bullish: bool = True
    
    # Price context
    price: float = 0.0
    
    # Quality
    confidence: float = 0.0
    
    # Description
    description: str = ""
    
    # Detected
    detected_at: datetime = field(default_factory=_utc_now)


# =============================================================================
# Scan Alert
# =============================================================================

@dataclass
class ScanAlert:
    """Alert from scanner."""
    alert_id: str = field(default_factory=_new_id)
    scanner_id: str = ""
    scanner_name: str = ""
    
    # Alert content
    symbol: str = ""
    title: str = ""
    message: str = ""
    
    # Priority
    priority: str = "normal"  # low, normal, high, urgent
    
    # Status
    is_read: bool = False
    created_at: datetime = field(default_factory=_utc_now)
