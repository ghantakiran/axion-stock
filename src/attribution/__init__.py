"""Performance Attribution System.

Comprehensive attribution and reporting with Brinson-Fachler decomposition,
factor attribution, benchmark comparison, and tear sheet generation.

Example:
    from src.attribution import TearSheetGenerator, MetricsCalculator
    import pandas as pd

    # Compute metrics
    calc = MetricsCalculator()
    metrics = calc.compute(daily_returns)

    # Generate tear sheet
    gen = TearSheetGenerator()
    sheet = gen.generate(
        portfolio_returns=daily_returns,
        benchmark_returns=spy_returns,
        name="My Portfolio",
    )
"""

from src.attribution.config import (
    AttributionMethod,
    AttributionLevel,
    BenchmarkType,
    TimePeriod,
    RiskMetricType,
    STANDARD_FACTORS,
    COMMON_BENCHMARKS,
    TRADING_DAYS_PER_YEAR,
    RISK_FREE_RATE,
    BenchmarkDefinition,
    AttributionConfig,
    DEFAULT_ATTRIBUTION_CONFIG,
)

from src.attribution.models import (
    SectorAttribution,
    BrinsonAttribution,
    FactorContribution,
    FactorAttribution,
    BenchmarkComparison,
    DrawdownPeriod,
    PerformanceMetrics,
    MonthlyReturns,
    TearSheet,
)

from src.attribution.brinson import BrinsonAnalyzer
from src.attribution.factor_attribution import FactorAnalyzer
from src.attribution.benchmark import BenchmarkAnalyzer
from src.attribution.metrics import MetricsCalculator
from src.attribution.tearsheet import TearSheetGenerator
from src.attribution.risk import RiskDecomposer
from src.attribution.performance import (
    PositionContribution,
    ContributionSummary,
    PerformanceContributor,
)
from src.attribution.multi_period import (
    PeriodAttribution,
    LinkedAttribution,
    CumulativeEffect,
    MultiPeriodAttribution,
)
from src.attribution.fama_french import (
    FFFactorExposure,
    FFModelResult,
    FFComparison,
    FamaFrenchAnalyzer,
)
from src.attribution.geographic import (
    CountryAttribution,
    RegionAttribution,
    GeographicAttribution,
    GeographicAnalyzer,
)
from src.attribution.risk_adjusted import (
    RiskAdjustedMetrics,
    MetricComparison,
    RiskAdjustedReport,
    RiskAdjustedAnalyzer,
)

__all__ = [
    # Config
    "AttributionMethod",
    "AttributionLevel",
    "BenchmarkType",
    "TimePeriod",
    "RiskMetricType",
    "STANDARD_FACTORS",
    "COMMON_BENCHMARKS",
    "TRADING_DAYS_PER_YEAR",
    "RISK_FREE_RATE",
    "BenchmarkDefinition",
    "AttributionConfig",
    "DEFAULT_ATTRIBUTION_CONFIG",
    # Models
    "SectorAttribution",
    "BrinsonAttribution",
    "FactorContribution",
    "FactorAttribution",
    "BenchmarkComparison",
    "DrawdownPeriod",
    "PerformanceMetrics",
    "MonthlyReturns",
    "TearSheet",
    "PositionContribution",
    "ContributionSummary",
    # Analyzers
    "BrinsonAnalyzer",
    "FactorAnalyzer",
    "BenchmarkAnalyzer",
    "MetricsCalculator",
    "TearSheetGenerator",
    "RiskDecomposer",
    "PerformanceContributor",
    # Multi-Period Attribution
    "PeriodAttribution",
    "LinkedAttribution",
    "CumulativeEffect",
    "MultiPeriodAttribution",
    # Fama-French
    "FFFactorExposure",
    "FFModelResult",
    "FFComparison",
    "FamaFrenchAnalyzer",
    # Geographic Attribution
    "CountryAttribution",
    "RegionAttribution",
    "GeographicAttribution",
    "GeographicAnalyzer",
    # Risk-Adjusted Metrics
    "RiskAdjustedMetrics",
    "MetricComparison",
    "RiskAdjustedReport",
    "RiskAdjustedAnalyzer",
]
