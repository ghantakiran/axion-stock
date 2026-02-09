"""Regime-Adaptive Strategy Engine (PRD-155).

Dynamically adjusts trading parameters based on detected market regimes.
Bridges the regime detection system (src/regime/) with the trade executor
(src/trade_executor/), enabling the autonomous bot to automatically shift
between aggressive, defensive, and protective trading postures.
"""

from src.regime_adaptive.profiles import (
    StrategyProfile,
    ProfileRegistry,
)
from src.regime_adaptive.adapter import (
    AdapterConfig,
    ConfigAdaptation,
    RegimeAdapter,
)
from src.regime_adaptive.tuner import (
    TunerConfig,
    TuningAdjustment,
    TunerResult,
    PerformanceTuner,
)
from src.regime_adaptive.monitor import (
    MonitorConfig,
    RegimeTransition,
    MonitorState,
    RegimeMonitor,
)

__all__ = [
    # Profiles
    "StrategyProfile",
    "ProfileRegistry",
    # Adapter
    "AdapterConfig",
    "ConfigAdaptation",
    "RegimeAdapter",
    # Tuner
    "TunerConfig",
    "TuningAdjustment",
    "TunerResult",
    "PerformanceTuner",
    # Monitor
    "MonitorConfig",
    "RegimeTransition",
    "MonitorState",
    "RegimeMonitor",
]
