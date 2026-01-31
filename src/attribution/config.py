"""Performance Attribution configuration.

Enums, constants, and configuration dataclasses.
"""

import enum
from dataclasses import dataclass, field


class AttributionMethod(enum.Enum):
    """Attribution methodology."""
    BRINSON_FACHLER = "brinson_fachler"
    FACTOR = "factor"
    RETURNS_BASED = "returns_based"


class AttributionLevel(enum.Enum):
    """Attribution decomposition level."""
    SECTOR = "sector"
    INDUSTRY = "industry"
    SECURITY = "security"


class BenchmarkType(enum.Enum):
    """Benchmark types."""
    INDEX = "index"
    CUSTOM = "custom"
    BLENDED = "blended"
    CASH = "cash"


class TimePeriod(enum.Enum):
    """Standard time periods."""
    MTD = "mtd"
    QTD = "qtd"
    YTD = "ytd"
    ONE_MONTH = "1M"
    THREE_MONTHS = "3M"
    SIX_MONTHS = "6M"
    ONE_YEAR = "1Y"
    THREE_YEARS = "3Y"
    FIVE_YEARS = "5Y"
    INCEPTION = "inception"


class RiskMetricType(enum.Enum):
    """Risk metric types."""
    VOLATILITY = "volatility"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    TREYNOR_RATIO = "treynor_ratio"
    INFORMATION_RATIO = "information_ratio"
    TRACKING_ERROR = "tracking_error"
    MAX_DRAWDOWN = "max_drawdown"
    BETA = "beta"
    ALPHA = "alpha"


# Standard factors for factor attribution
STANDARD_FACTORS = [
    "market",
    "value",
    "momentum",
    "quality",
    "growth",
    "volatility",
    "size",
]

# Common benchmarks
COMMON_BENCHMARKS: dict[str, dict] = {
    "SPY": {"name": "S&P 500", "type": BenchmarkType.INDEX},
    "QQQ": {"name": "NASDAQ 100", "type": BenchmarkType.INDEX},
    "IWM": {"name": "Russell 2000", "type": BenchmarkType.INDEX},
    "AGG": {"name": "US Aggregate Bond", "type": BenchmarkType.INDEX},
    "EFA": {"name": "MSCI EAFE", "type": BenchmarkType.INDEX},
    "60_40": {"name": "60/40 Portfolio", "type": BenchmarkType.BLENDED},
}

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.045  # 4.5% annualized


@dataclass
class BenchmarkDefinition:
    """Benchmark definition.

    Attributes:
        benchmark_id: Unique identifier.
        name: Display name.
        benchmark_type: Type of benchmark.
        components: For blended benchmarks, {symbol: weight}.
    """
    benchmark_id: str = "SPY"
    name: str = "S&P 500"
    benchmark_type: BenchmarkType = BenchmarkType.INDEX
    components: dict[str, float] = field(default_factory=dict)


@dataclass
class AttributionConfig:
    """Top-level attribution configuration."""
    default_benchmark: str = "SPY"
    risk_free_rate: float = RISK_FREE_RATE
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR
    min_history_days: int = 30
    rolling_window_days: int = 63  # ~3 months
    annualize: bool = True


DEFAULT_ATTRIBUTION_CONFIG = AttributionConfig()
