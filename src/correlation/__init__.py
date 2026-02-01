"""Correlation Analysis Module.

Cross-asset correlation matrices, rolling correlations, pair identification,
regime detection, and portfolio diversification scoring.

Example:
    from src.correlation import CorrelationEngine, CorrelationRegimeDetector
    import pandas as pd

    engine = CorrelationEngine()
    returns = pd.DataFrame(...)  # Daily returns
    matrix = engine.compute_matrix(returns)
    print(f"Avg correlation: {matrix.avg_correlation:.3f}")

    pairs = engine.get_top_pairs(matrix, n=5)
    for p in pairs:
        print(f"{p.symbol_a}-{p.symbol_b}: {p.correlation:.3f}")
"""

from src.correlation.config import (
    CorrelationMethod,
    RegimeType,
    DiversificationLevel,
    WindowType,
    STANDARD_WINDOWS,
    CorrelationConfig,
    RollingConfig,
    RegimeConfig,
    DiversificationConfig,
    CorrelationAnalysisConfig,
    DEFAULT_CORRELATION_CONFIG,
    DEFAULT_ROLLING_CONFIG,
    DEFAULT_REGIME_CONFIG,
    DEFAULT_DIVERSIFICATION_CONFIG,
    DEFAULT_CONFIG,
)

from src.correlation.models import (
    CorrelationMatrix,
    CorrelationPair,
    RollingCorrelation,
    CorrelationRegime,
    DiversificationScore,
)

from src.correlation.engine import CorrelationEngine
from src.correlation.regime import CorrelationRegimeDetector
from src.correlation.diversification import DiversificationAnalyzer

__all__ = [
    # Config
    "CorrelationMethod",
    "RegimeType",
    "DiversificationLevel",
    "WindowType",
    "STANDARD_WINDOWS",
    "CorrelationConfig",
    "RollingConfig",
    "RegimeConfig",
    "DiversificationConfig",
    "CorrelationAnalysisConfig",
    "DEFAULT_CORRELATION_CONFIG",
    "DEFAULT_ROLLING_CONFIG",
    "DEFAULT_REGIME_CONFIG",
    "DEFAULT_DIVERSIFICATION_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "CorrelationMatrix",
    "CorrelationPair",
    "RollingCorrelation",
    "CorrelationRegime",
    "DiversificationScore",
    # Components
    "CorrelationEngine",
    "CorrelationRegimeDetector",
    "DiversificationAnalyzer",
]
