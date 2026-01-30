"""Risk Management Configuration.

Contains all configurable risk parameters with sensible defaults.
Users can adjust limits within allowed ranges.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RiskConfig:
    """Configuration for the risk management system.

    All percentage values are expressed as decimals (e.g., 0.15 = 15%).
    """

    # ==========================================================================
    # Position Limits
    # ==========================================================================
    max_position_pct: float = 0.15  # Max 15% in single position
    max_sector_pct: float = 0.35  # Max 35% in single sector
    max_industry_pct: float = 0.20  # Max 20% in single industry
    max_top5_pct: float = 0.60  # Max 60% in top 5 positions
    max_correlation: float = 0.85  # Alert if 3+ positions >0.85 corr
    min_cash_pct: float = 0.02  # Keep minimum 2% cash

    # ==========================================================================
    # Stop-Loss Rules
    # ==========================================================================
    position_stop_loss: float = -0.15  # Close position at -15%
    position_stop_loss_min: float = -0.25  # Cannot disable below -25%

    # ==========================================================================
    # Portfolio Drawdown Thresholds
    # ==========================================================================
    portfolio_drawdown_warning: float = -0.05  # Alert at -5%
    portfolio_drawdown_reduce: float = -0.10  # Reduce exposure at -10%
    portfolio_drawdown_reduce_target: float = 0.30  # Target 30% cash
    portfolio_drawdown_emergency: float = -0.15  # Emergency at -15%
    portfolio_drawdown_emergency_target: float = 0.50  # Target 50% cash

    # ==========================================================================
    # Daily Loss Limit
    # ==========================================================================
    daily_loss_limit: float = -0.03  # Halt trading at -3% daily
    daily_loss_cooldown_hours: int = 24  # Cooldown period

    # ==========================================================================
    # Beta & Volatility Limits
    # ==========================================================================
    max_portfolio_beta: float = 1.5  # Max portfolio beta
    max_portfolio_volatility: float = 0.30  # Max 30% annualized vol
    max_position_volatility: float = 0.60  # Max 60% annualized vol for position

    # ==========================================================================
    # VaR Configuration
    # ==========================================================================
    var_confidence: float = 0.95  # 95% confidence
    var_horizon_days: int = 1  # 1-day VaR
    var_max_pct: float = 0.05  # Alert if VaR >5% of portfolio

    # ==========================================================================
    # Liquidity
    # ==========================================================================
    max_adv_participation: float = 0.05  # Max 5% of ADV per order
    cash_buffer_pct: float = 0.02  # Keep 2% buffer when checking buying power

    # ==========================================================================
    # Recovery Protocol
    # ==========================================================================
    recovery_cooldown_hours: int = 48  # No new buys for 48h
    recovery_scale_in_days: int = 5  # Scale back in over 5 days
    recovery_reduced_size_pct: float = 0.50  # 50% normal size
    recovery_reduced_size_weeks: int = 2  # For 2 weeks
    recovery_threshold_multiplier: float = 0.50  # Tighten thresholds 50%

    # ==========================================================================
    # Alert Configuration
    # ==========================================================================
    alert_email_enabled: bool = False
    alert_sms_enabled: bool = False
    alert_dashboard_enabled: bool = True

    def validate(self) -> list[str]:
        """Validate configuration settings.

        Returns:
            List of validation error messages.
        """
        errors = []

        # Position limits
        if not 0 < self.max_position_pct <= 1:
            errors.append("max_position_pct must be between 0 and 1")
        if not 0 < self.max_sector_pct <= 1:
            errors.append("max_sector_pct must be between 0 and 1")

        # Stop loss limits
        if self.position_stop_loss < self.position_stop_loss_min:
            errors.append(
                f"position_stop_loss ({self.position_stop_loss}) cannot be below "
                f"minimum ({self.position_stop_loss_min})"
            )

        # Drawdown thresholds must be ordered
        if not (
            self.portfolio_drawdown_warning
            > self.portfolio_drawdown_reduce
            > self.portfolio_drawdown_emergency
        ):
            errors.append("Drawdown thresholds must be in order: warning > reduce > emergency")

        # VaR confidence
        if not 0.5 <= self.var_confidence <= 0.999:
            errors.append("var_confidence must be between 0.5 and 0.999")

        return errors


# Default configuration
DEFAULT_RISK_CONFIG = RiskConfig()


@dataclass
class DrawdownRule:
    """Rule for drawdown-based actions."""

    name: str
    threshold: float  # e.g., -0.05 for 5% drawdown
    action: str  # 'alert', 'reduce_exposure', 'liquidate_to_cash', 'close_position', 'halt_trading'
    target_cash: Optional[float] = None  # Target cash % for reduce actions
    cooldown_hours: Optional[int] = None  # Cooldown for halt actions
    message: str = ""
    severity: str = "warning"  # 'info', 'warning', 'critical', 'emergency'


@dataclass
class RiskAlert:
    """Risk alert notification."""

    level: str  # 'info', 'warning', 'critical', 'emergency'
    category: str  # 'drawdown', 'concentration', 'var', 'stop_loss', etc.
    message: str
    metric_name: str
    metric_value: float
    threshold: float
    timestamp: str = ""
    position: Optional[str] = None  # Symbol if position-specific
    action_required: bool = False
    action_type: Optional[str] = None  # 'reduce', 'close', 'halt'


@dataclass
class CheckResult:
    """Result of a single risk check."""

    passed: bool
    severity: str = "info"  # 'info', 'warning', 'block'
    message: str = ""
    check_name: str = ""
    metric_value: Optional[float] = None
    threshold: Optional[float] = None


@dataclass
class ValidationResult:
    """Result of pre-trade validation."""

    approved: bool
    reasons: list[CheckResult] = field(default_factory=list)
    warnings: list[CheckResult] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def blocked_reasons(self) -> list[str]:
        return [r.message for r in self.reasons if r.severity == "block"]

    @property
    def warning_messages(self) -> list[str]:
        return [w.message for w in self.warnings]
