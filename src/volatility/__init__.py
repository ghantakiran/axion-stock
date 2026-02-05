"""Volatility Analysis Module.

Historical and implied volatility estimation, term structure analysis,
volatility surface/smile modeling, and vol regime detection.

Example:
    from src.volatility import VolatilityEngine, VolRegimeDetector
    import pandas as pd

    engine = VolatilityEngine()
    returns = pd.Series([0.01, -0.02, 0.005, ...])
    est = engine.compute_historical(returns, window=21, symbol="AAPL")
    print(f"Vol: {est.value:.2%}")

    detector = VolRegimeDetector()
    state = detector.detect(returns)
    print(f"Regime: {state.regime.value}")
"""

from src.volatility.config import (
    VolMethod,
    VolRegime,
    VolTimeframe,
    SurfaceInterpolation,
    STANDARD_WINDOWS,
    VolConfig,
    TermStructureConfig,
    SurfaceConfig,
    RegimeConfig,
    VolAnalysisConfig,
    DEFAULT_VOL_CONFIG,
    DEFAULT_TERM_STRUCTURE_CONFIG,
    DEFAULT_SURFACE_CONFIG,
    DEFAULT_REGIME_CONFIG,
    DEFAULT_CONFIG,
)

from src.volatility.models import (
    VolEstimate,
    TermStructurePoint,
    TermStructure,
    VolSmilePoint,
    VolSurface,
    VolRegimeState,
    VolConePoint,
)

from src.volatility.engine import VolatilityEngine
from src.volatility.surface import VolSurfaceAnalyzer
from src.volatility.regime import VolRegimeDetector
from src.volatility.svi_model import (
    SVIParams,
    SVISurface,
    CalibrationResult,
    SVICalibrator,
)
from src.volatility.skew_analytics import (
    RiskReversal,
    SkewDynamics,
    SkewTermStructure,
    SkewRegime,
    SkewAnalyzer,
)
from src.volatility.term_model import (
    TermStructureFit,
    CarryRollDown,
    TermDynamics,
    TermComparison,
    TermStructureModeler,
)
from src.volatility.vol_regime_signals import (
    VolOfVol,
    MeanReversionSignal,
    RegimeTransitionSignal,
    VolSignalSummary,
    VolRegimeSignalGenerator,
)

__all__ = [
    # Config
    "VolMethod",
    "VolRegime",
    "VolTimeframe",
    "SurfaceInterpolation",
    "STANDARD_WINDOWS",
    "VolConfig",
    "TermStructureConfig",
    "SurfaceConfig",
    "RegimeConfig",
    "VolAnalysisConfig",
    "DEFAULT_VOL_CONFIG",
    "DEFAULT_TERM_STRUCTURE_CONFIG",
    "DEFAULT_SURFACE_CONFIG",
    "DEFAULT_REGIME_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "VolEstimate",
    "TermStructurePoint",
    "TermStructure",
    "VolSmilePoint",
    "VolSurface",
    "VolRegimeState",
    "VolConePoint",
    # Components
    "VolatilityEngine",
    "VolSurfaceAnalyzer",
    "VolRegimeDetector",
    # SVI Surface (PRD-64)
    "SVIParams",
    "SVISurface",
    "CalibrationResult",
    "SVICalibrator",
    # Skew Analytics (PRD-64)
    "RiskReversal",
    "SkewDynamics",
    "SkewTermStructure",
    "SkewRegime",
    "SkewAnalyzer",
    # Term Structure Modeling (PRD-64)
    "TermStructureFit",
    "CarryRollDown",
    "TermDynamics",
    "TermComparison",
    "TermStructureModeler",
    # Vol Regime Signals (PRD-64)
    "VolOfVol",
    "MeanReversionSignal",
    "RegimeTransitionSignal",
    "VolSignalSummary",
    "VolRegimeSignalGenerator",
]
