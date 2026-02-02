"""Macro Regime Analysis Module.

Economic indicator tracking, yield curve analysis,
regime detection, and macro factor models.

Example:
    from src.macro import IndicatorTracker, YieldCurveAnalyzer, RegimeDetector

    tracker = IndicatorTracker()
    tracker.add_indicators(indicators)
    summary = tracker.summarize()
    print(f"Composite: {summary.composite_index}, Breadth: {summary.breadth}")

    curve = YieldCurveAnalyzer()
    snapshot = curve.analyze(rates, "2026-01-31")
    print(f"Shape: {snapshot.shape.value}, Spread: {snapshot.term_spread}")
"""

from src.macro.config import (
    RegimeType,
    CurveShape,
    IndicatorType,
    MacroFactor,
    IndicatorConfig,
    YieldCurveConfig,
    RegimeConfig,
    FactorConfig,
    MacroConfig,
    DEFAULT_INDICATOR_CONFIG,
    DEFAULT_YIELDCURVE_CONFIG,
    DEFAULT_REGIME_CONFIG,
    DEFAULT_FACTOR_CONFIG,
    DEFAULT_CONFIG,
)

from src.macro.models import (
    EconomicIndicator,
    IndicatorSummary,
    YieldCurveSnapshot,
    RegimeState,
    MacroFactorResult,
)

from src.macro.indicators import IndicatorTracker
from src.macro.yieldcurve import YieldCurveAnalyzer
from src.macro.regime import RegimeDetector
from src.macro.factors import MacroFactorModel

__all__ = [
    # Config
    "RegimeType",
    "CurveShape",
    "IndicatorType",
    "MacroFactor",
    "IndicatorConfig",
    "YieldCurveConfig",
    "RegimeConfig",
    "FactorConfig",
    "MacroConfig",
    "DEFAULT_INDICATOR_CONFIG",
    "DEFAULT_YIELDCURVE_CONFIG",
    "DEFAULT_REGIME_CONFIG",
    "DEFAULT_FACTOR_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "EconomicIndicator",
    "IndicatorSummary",
    "YieldCurveSnapshot",
    "RegimeState",
    "MacroFactorResult",
    # Components
    "IndicatorTracker",
    "YieldCurveAnalyzer",
    "RegimeDetector",
    "MacroFactorModel",
]
