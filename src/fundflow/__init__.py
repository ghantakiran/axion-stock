"""Fund Flow Analysis Module.

ETF/mutual fund flow tracking, institutional positioning,
sector rotation detection, and smart money signals.

Example:
    from src.fundflow import FlowTracker, SmartMoneyDetector

    tracker = FlowTracker()
    tracker.add_flows(flows)
    summary = tracker.summarize("SPY")
    print(f"Net flow: {summary.net_flow}, Strength: {summary.strength.value}")

    detector = SmartMoneyDetector()
    result = detector.analyze(inst_flows, retail_flows, prices, "AAPL")
    print(f"Signal: {result.signal.value}, Conviction: {result.conviction}")
"""

from src.fundflow.config import (
    FlowDirection,
    FlowStrength,
    RotationPhase,
    SmartMoneySignal,
    FlowTrackerConfig,
    InstitutionalConfig,
    RotationConfig,
    SmartMoneyConfig,
    FundFlowConfig,
    DEFAULT_TRACKER_CONFIG,
    DEFAULT_INSTITUTIONAL_CONFIG,
    DEFAULT_ROTATION_CONFIG,
    DEFAULT_SMARTMONEY_CONFIG,
    DEFAULT_CONFIG,
)

from src.fundflow.models import (
    FundFlow,
    FlowSummary,
    InstitutionalPosition,
    InstitutionalSummary,
    SectorRotation,
    SmartMoneyResult,
)

from src.fundflow.tracker import FlowTracker
from src.fundflow.institutional import InstitutionalAnalyzer
from src.fundflow.rotation import RotationDetector
from src.fundflow.smartmoney import SmartMoneyDetector

__all__ = [
    # Config
    "FlowDirection",
    "FlowStrength",
    "RotationPhase",
    "SmartMoneySignal",
    "FlowTrackerConfig",
    "InstitutionalConfig",
    "RotationConfig",
    "SmartMoneyConfig",
    "FundFlowConfig",
    "DEFAULT_TRACKER_CONFIG",
    "DEFAULT_INSTITUTIONAL_CONFIG",
    "DEFAULT_ROTATION_CONFIG",
    "DEFAULT_SMARTMONEY_CONFIG",
    "DEFAULT_CONFIG",
    # Models
    "FundFlow",
    "FlowSummary",
    "InstitutionalPosition",
    "InstitutionalSummary",
    "SectorRotation",
    "SmartMoneyResult",
    # Components
    "FlowTracker",
    "InstitutionalAnalyzer",
    "RotationDetector",
    "SmartMoneyDetector",
]
