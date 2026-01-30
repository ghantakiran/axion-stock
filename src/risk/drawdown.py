"""Drawdown Protection System.

Monitors portfolio and position drawdowns, triggers alerts and
automatic de-risking when thresholds are breached.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable, Any

from src.risk.config import RiskConfig, DrawdownRule, RiskAlert

logger = logging.getLogger(__name__)


class DrawdownAction(Enum):
    """Actions triggered by drawdown rules."""

    ALERT = "alert"
    REDUCE_EXPOSURE = "reduce_exposure"
    LIQUIDATE_TO_CASH = "liquidate_to_cash"
    CLOSE_POSITION = "close_position"
    HALT_TRADING = "halt_trading"


class RecoveryState(Enum):
    """Portfolio recovery state after drawdown event."""

    NORMAL = "normal"
    COOLDOWN = "cooldown"  # No new buys
    SCALING_IN = "scaling_in"  # Gradual re-entry
    REDUCED_SIZE = "reduced_size"  # Reduced position sizes


@dataclass
class DrawdownState:
    """Current drawdown state for portfolio or position."""

    current_value: float
    peak_value: float
    drawdown_pct: float
    drawdown_duration_days: int = 0
    peak_date: Optional[datetime] = None
    last_update: datetime = field(default_factory=datetime.now)

    @property
    def is_in_drawdown(self) -> bool:
        return self.drawdown_pct < -0.001  # More than 0.1% below peak


@dataclass
class RecoveryProtocol:
    """Recovery protocol state after drawdown event."""

    state: RecoveryState = RecoveryState.NORMAL
    triggered_at: Optional[datetime] = None
    cooldown_ends: Optional[datetime] = None
    scale_in_day: int = 0
    scale_in_total_days: int = 5
    reduced_size_pct: float = 0.50
    reduced_size_until: Optional[datetime] = None
    original_threshold_multiplier: float = 1.0  # Tightened thresholds

    def is_in_recovery(self) -> bool:
        return self.state != RecoveryState.NORMAL

    def get_position_size_multiplier(self) -> float:
        """Get multiplier for position sizing during recovery."""
        if self.state == RecoveryState.COOLDOWN:
            return 0.0  # No new buys
        elif self.state == RecoveryState.SCALING_IN:
            # Linear scale-in
            return (self.scale_in_day / self.scale_in_total_days) * self.reduced_size_pct
        elif self.state == RecoveryState.REDUCED_SIZE:
            return self.reduced_size_pct
        return 1.0


class DrawdownProtection:
    """Monitor and protect against portfolio drawdowns.

    Example:
        protection = DrawdownProtection(config)

        # Check portfolio drawdown
        alerts = protection.check_portfolio_drawdown(
            current_value=95000,
            peak_value=100000,
        )

        # Check position stop-loss
        alert = protection.check_position_stop_loss(
            symbol="AAPL",
            entry_price=150,
            current_price=125,
        )

        # Get current state
        state = protection.get_drawdown_state()
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        on_alert: Optional[Callable[[RiskAlert], Any]] = None,
        on_action: Optional[Callable[[DrawdownAction, dict], Any]] = None,
    ):
        """Initialize drawdown protection.

        Args:
            config: Risk configuration.
            on_alert: Callback for alerts.
            on_action: Callback for actions (reduce, liquidate, etc.).
        """
        self.config = config or RiskConfig()
        self.on_alert = on_alert
        self.on_action = on_action

        # Build rules from config
        self.rules = self._build_rules()

        # State tracking
        self.portfolio_state = DrawdownState(
            current_value=0,
            peak_value=0,
            drawdown_pct=0,
        )
        self.position_states: dict[str, DrawdownState] = {}
        self.recovery_protocol = RecoveryProtocol()

        # Daily tracking
        self.daily_pnl = 0.0
        self.daily_start_value = 0.0
        self.last_trading_day: Optional[datetime] = None

        # Trading halt state
        self.trading_halted = False
        self.trading_halt_until: Optional[datetime] = None

    def _build_rules(self) -> list[DrawdownRule]:
        """Build drawdown rules from config."""
        return [
            DrawdownRule(
                name="portfolio_warning",
                threshold=self.config.portfolio_drawdown_warning,
                action="alert",
                message="Portfolio drawdown warning",
                severity="warning",
            ),
            DrawdownRule(
                name="portfolio_reduce",
                threshold=self.config.portfolio_drawdown_reduce,
                action="reduce_exposure",
                target_cash=self.config.portfolio_drawdown_reduce_target,
                message="Portfolio drawdown - reducing exposure",
                severity="critical",
            ),
            DrawdownRule(
                name="portfolio_emergency",
                threshold=self.config.portfolio_drawdown_emergency,
                action="liquidate_to_cash",
                target_cash=self.config.portfolio_drawdown_emergency_target,
                message="Portfolio emergency - liquidating to cash",
                severity="emergency",
            ),
            DrawdownRule(
                name="position_stop",
                threshold=self.config.position_stop_loss,
                action="close_position",
                message="Position stop-loss triggered",
                severity="critical",
            ),
            DrawdownRule(
                name="daily_loss_limit",
                threshold=self.config.daily_loss_limit,
                action="halt_trading",
                cooldown_hours=self.config.daily_loss_cooldown_hours,
                message="Daily loss limit hit - trading halted",
                severity="emergency",
            ),
        ]

    # =========================================================================
    # Portfolio Drawdown
    # =========================================================================

    def update_portfolio(self, current_value: float) -> list[RiskAlert]:
        """Update portfolio state and check drawdown rules.

        Args:
            current_value: Current portfolio value.

        Returns:
            List of triggered alerts.
        """
        alerts = []

        # Update peak
        if current_value > self.portfolio_state.peak_value:
            self.portfolio_state.peak_value = current_value
            self.portfolio_state.peak_date = datetime.now()
            self.portfolio_state.drawdown_duration_days = 0

        # Calculate drawdown
        if self.portfolio_state.peak_value > 0:
            drawdown = (current_value - self.portfolio_state.peak_value) / self.portfolio_state.peak_value
        else:
            drawdown = 0

        self.portfolio_state.current_value = current_value
        self.portfolio_state.drawdown_pct = drawdown
        self.portfolio_state.last_update = datetime.now()

        # Update drawdown duration
        if self.portfolio_state.is_in_drawdown and self.portfolio_state.peak_date:
            self.portfolio_state.drawdown_duration_days = (
                datetime.now() - self.portfolio_state.peak_date
            ).days

        # Check rules
        alerts = self.check_portfolio_drawdown(current_value, self.portfolio_state.peak_value)

        return alerts

    def check_portfolio_drawdown(
        self,
        current_value: float,
        peak_value: float,
    ) -> list[RiskAlert]:
        """Check portfolio drawdown against rules.

        Args:
            current_value: Current portfolio value.
            peak_value: Peak portfolio value.

        Returns:
            List of triggered alerts.
        """
        alerts = []

        if peak_value <= 0:
            return alerts

        drawdown = (current_value - peak_value) / peak_value

        # Check each portfolio rule
        for rule in self.rules:
            if rule.name.startswith("portfolio_") or rule.name == "daily_loss_limit":
                if drawdown <= rule.threshold:
                    alert = RiskAlert(
                        level=rule.severity,
                        category="drawdown",
                        message=rule.message,
                        metric_name="portfolio_drawdown",
                        metric_value=drawdown,
                        threshold=rule.threshold,
                        timestamp=datetime.now().isoformat(),
                        action_required=rule.action != "alert",
                        action_type=rule.action,
                    )
                    alerts.append(alert)

                    # Trigger callbacks
                    if self.on_alert:
                        self.on_alert(alert)

                    # Trigger action
                    self._trigger_action(rule, {"drawdown": drawdown, "current_value": current_value})

        return alerts

    # =========================================================================
    # Daily Loss Limit
    # =========================================================================

    def start_trading_day(self, portfolio_value: float):
        """Reset daily tracking at start of trading day.

        Args:
            portfolio_value: Portfolio value at market open.
        """
        self.daily_start_value = portfolio_value
        self.daily_pnl = 0.0
        self.last_trading_day = datetime.now()

        # Check if trading halt has expired
        if self.trading_halted and self.trading_halt_until:
            if datetime.now() >= self.trading_halt_until:
                self.trading_halted = False
                self.trading_halt_until = None
                logger.info("Trading halt expired, resuming normal operations")

    def update_daily_pnl(self, current_value: float) -> Optional[RiskAlert]:
        """Update daily P&L and check limit.

        Args:
            current_value: Current portfolio value.

        Returns:
            Alert if daily loss limit is breached.
        """
        if self.daily_start_value <= 0:
            return None

        self.daily_pnl = (current_value - self.daily_start_value) / self.daily_start_value

        # Check daily loss limit
        if self.daily_pnl <= self.config.daily_loss_limit:
            alert = RiskAlert(
                level="emergency",
                category="daily_loss",
                message=f"Daily loss limit breached: {self.daily_pnl:.2%}",
                metric_name="daily_pnl",
                metric_value=self.daily_pnl,
                threshold=self.config.daily_loss_limit,
                timestamp=datetime.now().isoformat(),
                action_required=True,
                action_type="halt_trading",
            )

            # Halt trading
            self.trading_halted = True
            self.trading_halt_until = datetime.now() + timedelta(
                hours=self.config.daily_loss_cooldown_hours
            )

            if self.on_alert:
                self.on_alert(alert)

            return alert

        return None

    # =========================================================================
    # Position Stop-Loss
    # =========================================================================

    def update_position(
        self,
        symbol: str,
        current_value: float,
        entry_price: float,
        current_price: float,
    ) -> Optional[RiskAlert]:
        """Update position state and check stop-loss.

        Args:
            symbol: Position symbol.
            current_value: Current position value.
            entry_price: Position entry price.
            current_price: Current price.

        Returns:
            Alert if stop-loss triggered.
        """
        # Get or create position state
        if symbol not in self.position_states:
            self.position_states[symbol] = DrawdownState(
                current_value=current_value,
                peak_value=current_value,
                drawdown_pct=0,
            )

        state = self.position_states[symbol]

        # Update peak
        if current_value > state.peak_value:
            state.peak_value = current_value
            state.peak_date = datetime.now()

        state.current_value = current_value

        # Calculate drawdown from entry
        if entry_price > 0:
            pnl_pct = (current_price - entry_price) / entry_price
            state.drawdown_pct = pnl_pct
        else:
            state.drawdown_pct = 0

        state.last_update = datetime.now()

        # Check stop-loss
        return self.check_position_stop_loss(symbol, entry_price, current_price)

    def check_position_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
    ) -> Optional[RiskAlert]:
        """Check if position stop-loss is triggered.

        Args:
            symbol: Position symbol.
            entry_price: Entry price.
            current_price: Current price.

        Returns:
            Alert if stop-loss triggered.
        """
        if entry_price <= 0:
            return None

        pnl_pct = (current_price - entry_price) / entry_price

        if pnl_pct <= self.config.position_stop_loss:
            alert = RiskAlert(
                level="critical",
                category="stop_loss",
                message=f"Stop-loss triggered for {symbol}: {pnl_pct:.2%}",
                metric_name="position_pnl",
                metric_value=pnl_pct,
                threshold=self.config.position_stop_loss,
                timestamp=datetime.now().isoformat(),
                position=symbol,
                action_required=True,
                action_type="close_position",
            )

            if self.on_alert:
                self.on_alert(alert)

            return alert

        return None

    # =========================================================================
    # Action Handling
    # =========================================================================

    def _trigger_action(self, rule: DrawdownRule, context: dict):
        """Trigger action for a rule breach.

        Args:
            rule: The triggered rule.
            context: Context data.
        """
        action = DrawdownAction(rule.action)

        if action == DrawdownAction.HALT_TRADING:
            self.trading_halted = True
            self.trading_halt_until = datetime.now() + timedelta(
                hours=rule.cooldown_hours or self.config.daily_loss_cooldown_hours
            )

        # Start recovery protocol for reduce/liquidate actions
        if action in [DrawdownAction.REDUCE_EXPOSURE, DrawdownAction.LIQUIDATE_TO_CASH]:
            self._start_recovery_protocol()

        # Trigger callback
        if self.on_action:
            action_data = {
                "rule_name": rule.name,
                "action": rule.action,
                "target_cash": rule.target_cash,
                **context,
            }
            self.on_action(action, action_data)

        logger.warning(
            "Drawdown action triggered: %s (rule: %s, threshold: %s)",
            rule.action,
            rule.name,
            rule.threshold,
        )

    # =========================================================================
    # Recovery Protocol
    # =========================================================================

    def _start_recovery_protocol(self):
        """Start recovery protocol after drawdown event."""
        self.recovery_protocol = RecoveryProtocol(
            state=RecoveryState.COOLDOWN,
            triggered_at=datetime.now(),
            cooldown_ends=datetime.now() + timedelta(hours=self.config.recovery_cooldown_hours),
            scale_in_day=0,
            scale_in_total_days=self.config.recovery_scale_in_days,
            reduced_size_pct=self.config.recovery_reduced_size_pct,
            reduced_size_until=datetime.now() + timedelta(weeks=self.config.recovery_reduced_size_weeks),
            original_threshold_multiplier=self.config.recovery_threshold_multiplier,
        )

        logger.info("Recovery protocol started: cooldown until %s", self.recovery_protocol.cooldown_ends)

    def update_recovery_state(self):
        """Update recovery protocol state based on time."""
        if not self.recovery_protocol.is_in_recovery():
            return

        now = datetime.now()

        if self.recovery_protocol.state == RecoveryState.COOLDOWN:
            if self.recovery_protocol.cooldown_ends and now >= self.recovery_protocol.cooldown_ends:
                self.recovery_protocol.state = RecoveryState.SCALING_IN
                logger.info("Recovery: moving from cooldown to scaling-in")

        elif self.recovery_protocol.state == RecoveryState.SCALING_IN:
            # Increment scale-in day
            self.recovery_protocol.scale_in_day += 1
            if self.recovery_protocol.scale_in_day >= self.recovery_protocol.scale_in_total_days:
                self.recovery_protocol.state = RecoveryState.REDUCED_SIZE
                logger.info("Recovery: moving from scaling-in to reduced size")

        elif self.recovery_protocol.state == RecoveryState.REDUCED_SIZE:
            if self.recovery_protocol.reduced_size_until and now >= self.recovery_protocol.reduced_size_until:
                self.recovery_protocol.state = RecoveryState.NORMAL
                logger.info("Recovery protocol complete, returning to normal operations")

    def can_open_new_position(self) -> tuple[bool, str]:
        """Check if new positions can be opened.

        Returns:
            Tuple of (allowed, reason).
        """
        if self.trading_halted:
            return False, f"Trading halted until {self.trading_halt_until}"

        if self.recovery_protocol.state == RecoveryState.COOLDOWN:
            return False, f"In cooldown period until {self.recovery_protocol.cooldown_ends}"

        return True, ""

    def get_position_size_multiplier(self) -> float:
        """Get position size multiplier based on recovery state.

        Returns:
            Multiplier to apply to normal position sizes.
        """
        return self.recovery_protocol.get_position_size_multiplier()

    # =========================================================================
    # State Queries
    # =========================================================================

    def get_drawdown_state(self) -> dict:
        """Get current drawdown state summary.

        Returns:
            Dict with all drawdown state information.
        """
        return {
            "portfolio": {
                "current_drawdown": self.portfolio_state.drawdown_pct,
                "duration_days": self.portfolio_state.drawdown_duration_days,
                "peak_value": self.portfolio_state.peak_value,
                "current_value": self.portfolio_state.current_value,
            },
            "daily": {
                "pnl": self.daily_pnl,
                "start_value": self.daily_start_value,
            },
            "trading_halted": self.trading_halted,
            "halt_until": self.trading_halt_until.isoformat() if self.trading_halt_until else None,
            "recovery_state": self.recovery_protocol.state.value,
            "position_size_multiplier": self.get_position_size_multiplier(),
            "worst_positions": self._get_worst_positions(5),
        }

    def _get_worst_positions(self, n: int = 5) -> list[dict]:
        """Get positions with worst drawdowns.

        Args:
            n: Number of positions to return.

        Returns:
            List of position drawdown info.
        """
        positions = [
            {"symbol": sym, "drawdown": state.drawdown_pct}
            for sym, state in self.position_states.items()
        ]
        positions.sort(key=lambda x: x["drawdown"])
        return positions[:n]

    def is_trading_allowed(self) -> tuple[bool, str]:
        """Check if trading is currently allowed.

        Returns:
            Tuple of (allowed, reason).
        """
        if self.trading_halted:
            return False, f"Trading halted until {self.trading_halt_until}"

        return True, ""
