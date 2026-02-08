"""PRD-63: Regime-Aware Signals.

Signal generation system that adapts to detected market regimes:
- HMM-based regime detection
- Regime-conditional signals
- Dynamic parameter optimization
- Signal performance tracking
"""

from src.regime_signals.config import (
    RegimeType,
    SignalType,
    SignalDirection,
    DetectionMethod,
    TrendDirection,
    VolatilityLevel,
    SignalOutcome,
    REGIME_PARAMETERS,
)
from src.regime_signals.models import (
    RegimeState,
    RegimeSignal,
    SignalPerformance,
    RegimeParameter,
    SignalResult,
)
from src.regime_signals.detector import RegimeDetector
from src.regime_signals.generator import SignalGenerator
from src.regime_signals.optimizer import ParameterOptimizer
from src.regime_signals.tracker import PerformanceTracker

__all__ = [
    # Config
    "RegimeType",
    "SignalType",
    "SignalDirection",
    "DetectionMethod",
    "TrendDirection",
    "VolatilityLevel",
    "SignalOutcome",
    "REGIME_PARAMETERS",
    # Models
    "RegimeState",
    "RegimeSignal",
    "SignalPerformance",
    "RegimeParameter",
    "SignalResult",
    # Managers
    "RegimeDetector",
    "SignalGenerator",
    "ParameterOptimizer",
    "PerformanceTracker",
]
