"""Advanced Risk Management (PRD-150).

Production-grade risk controls that plug into the trade pipeline:
- Portfolio-level leverage monitoring and sector concentration limits
- Correlation-based position limits with VIX-based dynamic sizing
- Circuit breaker for cascading losses with cooldown/half-open states
- Enhanced kill switch with order cancellation and event recording
- Market calendar enforcement with holiday/session awareness
"""

from src.risk_manager.portfolio_risk import (
    PortfolioRiskConfig,
    PortfolioRiskMonitor,
    RiskLevel,
    RiskSnapshot,
    SECTOR_MAP,
)
from src.risk_manager.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerState,
    CircuitBreakerStatus,
    TradingCircuitBreaker,
)
from src.risk_manager.kill_switch import (
    EnhancedKillSwitch,
    KillSwitchConfig,
    KillSwitchEvent,
    KillSwitchState,
)
from src.risk_manager.market_hours import (
    MarketCalendarConfig,
    MarketHoursEnforcer,
    MarketSession,
    MARKET_HOLIDAYS,
)

__all__ = [
    # Portfolio risk
    "PortfolioRiskConfig",
    "PortfolioRiskMonitor",
    "RiskLevel",
    "RiskSnapshot",
    "SECTOR_MAP",
    # Circuit breaker
    "CircuitBreakerConfig",
    "CircuitBreakerState",
    "CircuitBreakerStatus",
    "TradingCircuitBreaker",
    # Kill switch
    "EnhancedKillSwitch",
    "KillSwitchConfig",
    "KillSwitchEvent",
    "KillSwitchState",
    # Market hours
    "MarketCalendarConfig",
    "MarketHoursEnforcer",
    "MarketSession",
    "MARKET_HOLIDAYS",
]
