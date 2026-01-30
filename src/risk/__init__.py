"""Enterprise Risk Management System.

A comprehensive risk management solution including:
- Portfolio & position risk metrics (Sharpe, Sortino, drawdown, beta)
- Value at Risk (VaR) calculations (Historical, Parametric, Monte Carlo)
- Stress testing (historical scenarios and hypothetical shocks)
- Drawdown protection with automated rules engine
- Pre-trade risk validation
- Performance attribution (Brinson and factor-based)
- Real-time risk monitoring and alerting
"""

# Configuration
from src.risk.config import (
    RiskConfig,
    DEFAULT_RISK_CONFIG,
    DrawdownRule,
    RiskAlert,
    CheckResult,
    ValidationResult,
)

# Risk Metrics
from src.risk.metrics import (
    RiskMetricsCalculator,
    PortfolioRiskMetrics,
    PositionRiskMetrics,
    ConcentrationMetrics,
)

# Value at Risk
from src.risk.var import (
    VaRCalculator,
    VaRResult,
)

# Stress Testing
from src.risk.stress_test import (
    StressTestEngine,
    StressTestResult,
    StressScenario,
    HISTORICAL_SCENARIOS,
    HYPOTHETICAL_SCENARIOS,
)

# Drawdown Protection
from src.risk.drawdown import (
    DrawdownProtection,
    RecoveryProtocol,
    DrawdownState,
)

# Pre-Trade Risk
from src.risk.pre_trade import (
    PreTradeRiskChecker,
    OrderContext,
    PortfolioContext,
)

# Attribution
from src.risk.attribution import (
    AttributionAnalyzer,
    BrinsonAttribution,
    FactorAttribution,
)

# Real-Time Monitor
from src.risk.monitor import (
    RiskMonitor,
    RiskDashboardData,
    RiskStatus,
)

__all__ = [
    # Config
    "RiskConfig",
    "DEFAULT_RISK_CONFIG",
    "DrawdownRule",
    "RiskAlert",
    "CheckResult",
    "ValidationResult",
    # Metrics
    "RiskMetricsCalculator",
    "PortfolioRiskMetrics",
    "PositionRiskMetrics",
    "ConcentrationMetrics",
    # VaR
    "VaRCalculator",
    "VaRResult",
    # Stress Test
    "StressTestEngine",
    "StressTestResult",
    "StressScenario",
    "HISTORICAL_SCENARIOS",
    "HYPOTHETICAL_SCENARIOS",
    # Drawdown
    "DrawdownProtection",
    "RecoveryProtocol",
    "DrawdownState",
    # Pre-Trade
    "PreTradeRiskChecker",
    "OrderContext",
    "PortfolioContext",
    # Attribution
    "AttributionAnalyzer",
    "BrinsonAttribution",
    "FactorAttribution",
    # Monitor
    "RiskMonitor",
    "RiskDashboardData",
    "RiskStatus",
]
