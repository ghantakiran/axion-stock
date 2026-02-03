"""Cross-Asset Signal Generation Module.

Analyzes intermarket relationships, detects lead-lag patterns,
computes cross-asset momentum/mean-reversion signals, and
generates composite trading signals.

Example:
    from src.crossasset import IntermarketAnalyzer, CrossAssetMomentum

    analyzer = IntermarketAnalyzer()
    corr = analyzer.rolling_correlation(equity_returns, bond_returns)
    print(f"Corr: {corr.correlation:.2f} ({corr.regime})")
"""

from src.crossasset.config import (
    AssetClass,
    CorrelationRegime,
    SignalDirection,
    SignalStrength,
    IntermarketConfig,
    LeadLagConfig,
    MomentumConfig,
    SignalConfig,
)

from src.crossasset.models import (
    AssetPairCorrelation,
    RelativeStrength,
    LeadLagResult,
    MomentumSignal,
    CrossAssetSignal,
)

from src.crossasset.intermarket import IntermarketAnalyzer
from src.crossasset.leadlag import LeadLagDetector
from src.crossasset.momentum import CrossAssetMomentum
from src.crossasset.signals import CrossAssetSignalGenerator

__all__ = [
    # Config
    "AssetClass",
    "CorrelationRegime",
    "SignalDirection",
    "SignalStrength",
    "IntermarketConfig",
    "LeadLagConfig",
    "MomentumConfig",
    "SignalConfig",
    # Models
    "AssetPairCorrelation",
    "RelativeStrength",
    "LeadLagResult",
    "MomentumSignal",
    "CrossAssetSignal",
    # Components
    "IntermarketAnalyzer",
    "LeadLagDetector",
    "CrossAssetMomentum",
    "CrossAssetSignalGenerator",
]
