"""TradingView Scanner data models."""

from dataclasses import dataclass, field
from typing import Any, Optional

from src.tv_scanner.config import AssetClass, TVScanCategory, TVTimeInterval


@dataclass
class TVFieldSpec:
    """Specification for a single field to select from the screener."""

    field_name: str
    interval: Optional[TVTimeInterval] = None
    alias: Optional[str] = None


@dataclass
class TVFilterCriterion:
    """A single filter condition for the screener query."""

    field_name: str
    operator: str  # gt, lt, gte, lte, eq, between, isin
    value: Any = None
    value2: Any = None  # Used for 'between' operator
    interval: Optional[TVTimeInterval] = None

    def describe(self) -> str:
        """Human-readable description of this filter."""
        if self.operator == "between":
            return f"{self.field_name} between {self.value} and {self.value2}"
        if self.operator == "isin":
            return f"{self.field_name} in {self.value}"
        op_map = {
            "gt": ">",
            "lt": "<",
            "gte": ">=",
            "lte": "<=",
            "eq": "==",
        }
        symbol = op_map.get(self.operator, self.operator)
        return f"{self.field_name} {symbol} {self.value}"


@dataclass
class TVPreset:
    """A complete scan preset combining field selection and filter criteria."""

    name: str
    description: str
    category: TVScanCategory
    asset_class: AssetClass = AssetClass.STOCK
    select_fields: list[TVFieldSpec] = field(default_factory=list)
    criteria: list[TVFilterCriterion] = field(default_factory=list)
    sort_field: Optional[str] = None
    sort_ascending: bool = False
    max_results: int = 150


@dataclass
class TVScanResult:
    """A single row returned from a TradingView scan."""

    symbol: str
    company_name: Optional[str] = None
    price: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None
    relative_volume: Optional[float] = None
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    tv_rating: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    sector: Optional[str] = None
    perf_week: Optional[float] = None
    perf_month: Optional[float] = None
    perf_year: Optional[float] = None
    signal_strength: float = 0.0
    raw_data: dict = field(default_factory=dict)
    data_source: str = "tradingview"


@dataclass
class TVScanReport:
    """Result container for a complete scan execution."""

    preset_name: str
    total_results: int = 0
    results: list[TVScanResult] = field(default_factory=list)
    execution_time_ms: float = 0.0
    error: Optional[str] = None
