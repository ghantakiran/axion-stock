"""Unified Risk Context & Correlation Guard (PRD-163).

Consolidates all risk systems into a single pass-through context:
- Portfolio-level correlation matrix with configurable thresholds
- VaR/CVaR-based dynamic position sizing
- Regime-adaptive risk limits (reads market_regime table)
- Unified daily P&L tracking (single source of truth)
- Risk snapshot aggregation across all subsystems

Replaces fragmented risk checks with one coherent RiskContext.
"""

from src.unified_risk.context import (
    RiskContext,
    RiskContextConfig,
    UnifiedRiskAssessment,
)
from src.unified_risk.correlation import (
    CorrelationGuard,
    CorrelationMatrix,
    CorrelationConfig,
)
from src.unified_risk.var_sizer import (
    VaRPositionSizer,
    VaRConfig,
    VaRResult,
)
from src.unified_risk.regime_limits import (
    RegimeRiskAdapter,
    RegimeLimits,
)

__all__ = [
    # Core context
    "RiskContext",
    "RiskContextConfig",
    "UnifiedRiskAssessment",
    # Correlation
    "CorrelationGuard",
    "CorrelationMatrix",
    "CorrelationConfig",
    # VaR sizing
    "VaRPositionSizer",
    "VaRConfig",
    "VaRResult",
    # Regime
    "RegimeRiskAdapter",
    "RegimeLimits",
]
