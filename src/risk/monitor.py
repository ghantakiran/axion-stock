"""Real-Time Risk Monitor.

Integrates all risk components into a unified monitoring system.
Provides real-time risk status, alerts, and dashboard data.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Callable, Any

import pandas as pd

from src.risk.config import RiskConfig, RiskAlert
from src.risk.metrics import RiskMetricsCalculator, PortfolioRiskMetrics, ConcentrationMetrics
from src.risk.var import VaRCalculator, VaRResult
from src.risk.stress_test import StressTestEngine, StressTestResult
from src.risk.drawdown import DrawdownProtection
from src.risk.pre_trade import PreTradeRiskChecker, OrderContext, PortfolioContext

logger = logging.getLogger(__name__)


class RiskStatus:
    """Overall risk status levels."""

    NORMAL = "normal"  # All metrics within limits
    WARNING = "warning"  # Some warnings, no blocks
    ELEVATED = "elevated"  # Near limit on critical metrics
    CRITICAL = "critical"  # Limits breached, action needed


@dataclass
class RiskDashboardData:
    """Data for risk dashboard display."""

    # Status
    overall_status: str = RiskStatus.NORMAL
    status_message: str = ""
    last_updated: datetime = field(default_factory=datetime.now)

    # Portfolio metrics
    portfolio_metrics: Optional[PortfolioRiskMetrics] = None
    concentration_metrics: Optional[ConcentrationMetrics] = None
    var_metrics: Optional[VaRResult] = None

    # Drawdown status
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    daily_pnl: float = 0.0
    worst_position_drawdown: float = 0.0
    worst_position_symbol: str = ""

    # Stress test results
    stress_test_results: list[StressTestResult] = field(default_factory=list)

    # Active alerts
    active_alerts: list[RiskAlert] = field(default_factory=list)

    # Limits utilization (0-1)
    position_limit_util: float = 0.0
    sector_limit_util: float = 0.0
    beta_limit_util: float = 0.0
    var_limit_util: float = 0.0

    # Trading status
    trading_allowed: bool = True
    trading_halt_reason: str = ""
    recovery_state: str = "normal"
    position_size_multiplier: float = 1.0


class RiskMonitor:
    """Unified risk monitoring system.

    Integrates all risk components and provides:
    - Real-time risk metrics
    - Pre-trade risk checks
    - Drawdown protection
    - Stress testing
    - Dashboard data

    Example:
        monitor = RiskMonitor(config)

        # Update with current portfolio
        dashboard = monitor.update(
            positions=positions,
            returns=returns,
            benchmark_returns=spy_returns,
            portfolio_value=100_000,
        )

        # Check before trade
        result = monitor.check_order(order, portfolio_context)

        # Get current status
        status = monitor.get_status()
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        sector_map: Optional[dict[str, str]] = None,
        historical_data: Optional[pd.DataFrame] = None,
        on_alert: Optional[Callable[[RiskAlert], Any]] = None,
    ):
        """Initialize risk monitor.

        Args:
            config: Risk configuration.
            sector_map: Symbol to sector mapping.
            historical_data: Historical price data for stress tests.
            on_alert: Callback for alerts.
        """
        self.config = config or RiskConfig()
        self.sector_map = sector_map or {}
        self.on_alert = on_alert

        # Initialize components
        self.metrics_calculator = RiskMetricsCalculator()
        self.var_calculator = VaRCalculator(horizon_days=self.config.var_horizon_days)
        self.stress_engine = StressTestEngine(historical_data=historical_data)
        self.drawdown_protection = DrawdownProtection(
            config=self.config,
            on_alert=on_alert,
        )
        self.pre_trade_checker = PreTradeRiskChecker(
            config=self.config,
            sector_map=self.sector_map,
        )

        # State
        self._dashboard_data = RiskDashboardData()
        self._active_alerts: list[RiskAlert] = []
        self._last_update: Optional[datetime] = None

    # =========================================================================
    # Main Update
    # =========================================================================

    def update(
        self,
        positions: list[dict],  # [{symbol, market_value, qty, entry_price, current_price, sector}]
        returns: Optional[pd.Series] = None,  # Portfolio returns
        benchmark_returns: Optional[pd.Series] = None,  # Benchmark returns
        portfolio_value: float = 0.0,
        factor_scores: Optional[dict[str, dict]] = None,  # {symbol: {value, momentum, ...}}
    ) -> RiskDashboardData:
        """Update all risk metrics.

        Args:
            positions: Current portfolio positions.
            returns: Historical portfolio returns.
            benchmark_returns: Benchmark returns.
            portfolio_value: Current portfolio value.
            factor_scores: Factor scores by symbol.

        Returns:
            RiskDashboardData for dashboard display.
        """
        dashboard = RiskDashboardData()
        dashboard.last_updated = datetime.now()

        # Add sector info to positions
        for pos in positions:
            if "sector" not in pos:
                pos["sector"] = self.sector_map.get(pos.get("symbol", ""), "Unknown")
            # Calculate weight
            pos["weight"] = pos.get("market_value", 0) / portfolio_value if portfolio_value > 0 else 0

        # Update drawdown protection
        self.drawdown_protection.update_portfolio(portfolio_value)

        # Update position stop-losses
        for pos in positions:
            self.drawdown_protection.update_position(
                symbol=pos.get("symbol", ""),
                current_value=pos.get("market_value", 0),
                entry_price=pos.get("entry_price", 0),
                current_price=pos.get("current_price", 0),
            )

        # Calculate portfolio metrics
        if returns is not None and len(returns) > 1:
            dashboard.portfolio_metrics = self.metrics_calculator.calculate_portfolio_metrics(
                returns=returns,
                benchmark_returns=benchmark_returns,
                portfolio_value=portfolio_value,
            )

            # Calculate VaR
            dashboard.var_metrics = self.var_calculator.historical_var_full(
                returns=returns,
                portfolio_value=portfolio_value,
            )

        # Calculate concentration
        dashboard.concentration_metrics = self.metrics_calculator.calculate_concentration(
            positions=positions,
        )

        # Drawdown data
        dd_state = self.drawdown_protection.get_drawdown_state()
        dashboard.current_drawdown = dd_state["portfolio"]["current_drawdown"]
        dashboard.max_drawdown = dashboard.portfolio_metrics.max_drawdown if dashboard.portfolio_metrics else 0
        dashboard.daily_pnl = dd_state["daily"]["pnl"]

        # Worst position
        if dd_state["worst_positions"]:
            worst = dd_state["worst_positions"][0]
            dashboard.worst_position_symbol = worst["symbol"]
            dashboard.worst_position_drawdown = worst["drawdown"]

        # Trading status
        trading_allowed, reason = self.drawdown_protection.is_trading_allowed()
        dashboard.trading_allowed = trading_allowed
        dashboard.trading_halt_reason = reason
        dashboard.recovery_state = dd_state["recovery_state"]
        dashboard.position_size_multiplier = dd_state["position_size_multiplier"]

        # Run stress tests
        dashboard.stress_test_results = self.stress_engine.run_hypothetical_tests(
            positions=positions,
            portfolio_value=portfolio_value,
            sector_map=self.sector_map,
            factor_scores=factor_scores,
        )

        # Calculate limit utilization
        if dashboard.concentration_metrics:
            cm = dashboard.concentration_metrics
            dashboard.position_limit_util = cm.largest_position_weight / self.config.max_position_pct
            dashboard.sector_limit_util = cm.largest_sector_weight / self.config.max_sector_pct

        if dashboard.portfolio_metrics:
            pm = dashboard.portfolio_metrics
            dashboard.beta_limit_util = abs(pm.portfolio_beta) / self.config.max_portfolio_beta

        if dashboard.var_metrics:
            dashboard.var_limit_util = dashboard.var_metrics.var_95_pct / self.config.var_max_pct

        # Check for alerts
        alerts = self._check_alerts(dashboard)
        dashboard.active_alerts = alerts
        self._active_alerts = alerts

        # Determine overall status
        dashboard.overall_status = self._determine_status(dashboard)
        dashboard.status_message = self._get_status_message(dashboard)

        self._dashboard_data = dashboard
        self._last_update = datetime.now()

        return dashboard

    # =========================================================================
    # Pre-Trade Checks
    # =========================================================================

    def check_order(
        self,
        order: OrderContext,
        portfolio: PortfolioContext,
    ):
        """Run pre-trade risk checks on an order.

        Args:
            order: Order to check.
            portfolio: Current portfolio context.

        Returns:
            ValidationResult.
        """
        return self.pre_trade_checker.validate_sync(order, portfolio)

    # =========================================================================
    # Status & Alerts
    # =========================================================================

    def _check_alerts(self, dashboard: RiskDashboardData) -> list[RiskAlert]:
        """Check for alert conditions.

        Args:
            dashboard: Current dashboard data.

        Returns:
            List of active alerts.
        """
        alerts = []

        # Drawdown alerts
        if dashboard.current_drawdown <= self.config.portfolio_drawdown_warning:
            level = "warning"
            if dashboard.current_drawdown <= self.config.portfolio_drawdown_reduce:
                level = "critical"
            if dashboard.current_drawdown <= self.config.portfolio_drawdown_emergency:
                level = "emergency"

            alerts.append(RiskAlert(
                level=level,
                category="drawdown",
                message=f"Portfolio drawdown: {dashboard.current_drawdown:.1%}",
                metric_name="drawdown",
                metric_value=dashboard.current_drawdown,
                threshold=self.config.portfolio_drawdown_warning,
                timestamp=datetime.now().isoformat(),
            ))

        # Concentration alerts
        if dashboard.concentration_metrics:
            cm = dashboard.concentration_metrics

            if cm.largest_position_weight > self.config.max_position_pct * 0.9:
                alerts.append(RiskAlert(
                    level="warning",
                    category="concentration",
                    message=f"Position concentration: {cm.largest_position_symbol} at {cm.largest_position_weight:.1%}",
                    metric_name="position_weight",
                    metric_value=cm.largest_position_weight,
                    threshold=self.config.max_position_pct,
                    position=cm.largest_position_symbol,
                    timestamp=datetime.now().isoformat(),
                ))

            if cm.largest_sector_weight > self.config.max_sector_pct * 0.9:
                alerts.append(RiskAlert(
                    level="warning",
                    category="concentration",
                    message=f"Sector concentration: {cm.largest_sector_name} at {cm.largest_sector_weight:.1%}",
                    metric_name="sector_weight",
                    metric_value=cm.largest_sector_weight,
                    threshold=self.config.max_sector_pct,
                    timestamp=datetime.now().isoformat(),
                ))

            if cm.high_correlation_pairs >= 3:
                alerts.append(RiskAlert(
                    level="warning",
                    category="correlation",
                    message=f"High correlation cluster detected: {cm.high_correlation_pairs} pairs",
                    metric_name="correlation_pairs",
                    metric_value=cm.high_correlation_pairs,
                    threshold=3,
                    timestamp=datetime.now().isoformat(),
                ))

        # VaR alert
        if dashboard.var_metrics and dashboard.var_metrics.var_95_pct > self.config.var_max_pct:
            alerts.append(RiskAlert(
                level="warning",
                category="var",
                message=f"VaR elevated: {dashboard.var_metrics.var_95_pct:.1%}",
                metric_name="var_95",
                metric_value=dashboard.var_metrics.var_95_pct,
                threshold=self.config.var_max_pct,
                timestamp=datetime.now().isoformat(),
            ))

        # Beta alert
        if dashboard.portfolio_metrics and abs(dashboard.portfolio_metrics.portfolio_beta) > self.config.max_portfolio_beta:
            alerts.append(RiskAlert(
                level="warning",
                category="beta",
                message=f"Portfolio beta: {dashboard.portfolio_metrics.portfolio_beta:.2f}",
                metric_name="beta",
                metric_value=dashboard.portfolio_metrics.portfolio_beta,
                threshold=self.config.max_portfolio_beta,
                timestamp=datetime.now().isoformat(),
            ))

        # Trigger callbacks
        for alert in alerts:
            if self.on_alert:
                self.on_alert(alert)

        return alerts

    def _determine_status(self, dashboard: RiskDashboardData) -> str:
        """Determine overall risk status.

        Args:
            dashboard: Dashboard data.

        Returns:
            Risk status string.
        """
        if not dashboard.trading_allowed:
            return RiskStatus.CRITICAL

        emergency_alerts = [a for a in dashboard.active_alerts if a.level == "emergency"]
        critical_alerts = [a for a in dashboard.active_alerts if a.level == "critical"]
        warning_alerts = [a for a in dashboard.active_alerts if a.level == "warning"]

        if emergency_alerts:
            return RiskStatus.CRITICAL
        if critical_alerts:
            return RiskStatus.ELEVATED
        if warning_alerts:
            return RiskStatus.WARNING
        return RiskStatus.NORMAL

    def _get_status_message(self, dashboard: RiskDashboardData) -> str:
        """Get status message for display.

        Args:
            dashboard: Dashboard data.

        Returns:
            Status message string.
        """
        status = dashboard.overall_status

        if status == RiskStatus.NORMAL:
            return "All risk metrics within limits"
        elif status == RiskStatus.WARNING:
            count = len([a for a in dashboard.active_alerts if a.level == "warning"])
            return f"{count} warning(s) active"
        elif status == RiskStatus.ELEVATED:
            return "Risk limits approaching - review positions"
        elif status == RiskStatus.CRITICAL:
            if not dashboard.trading_allowed:
                return f"Trading halted: {dashboard.trading_halt_reason}"
            return "Critical risk level - action required"

        return ""

    # =========================================================================
    # Getters
    # =========================================================================

    def get_status(self) -> str:
        """Get current overall risk status."""
        return self._dashboard_data.overall_status

    def get_dashboard_data(self) -> RiskDashboardData:
        """Get current dashboard data."""
        return self._dashboard_data

    def get_active_alerts(self) -> list[RiskAlert]:
        """Get currently active alerts."""
        return self._active_alerts

    def is_trading_allowed(self) -> tuple[bool, str]:
        """Check if trading is currently allowed."""
        return self.drawdown_protection.is_trading_allowed()

    def get_position_size_multiplier(self) -> float:
        """Get position size multiplier based on recovery state."""
        return self.drawdown_protection.get_position_size_multiplier()

    def can_open_new_position(self) -> tuple[bool, str]:
        """Check if new positions can be opened."""
        return self.drawdown_protection.can_open_new_position()

    # =========================================================================
    # Utility
    # =========================================================================

    def generate_risk_report(self) -> str:
        """Generate a text risk report.

        Returns:
            Formatted risk report string.
        """
        d = self._dashboard_data

        lines = [
            "=" * 60,
            "RISK REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            "",
            f"STATUS: {d.overall_status.upper()}",
            f"Message: {d.status_message}",
            "",
            "PORTFOLIO METRICS",
            "-" * 30,
        ]

        if d.portfolio_metrics:
            pm = d.portfolio_metrics
            lines.extend([
                f"  Sharpe Ratio:      {pm.sharpe_ratio:.2f}",
                f"  Sortino Ratio:     {pm.sortino_ratio:.2f}",
                f"  Portfolio Beta:    {pm.portfolio_beta:.2f}",
                f"  Volatility (ann):  {pm.portfolio_volatility:.1%}",
                f"  Current Drawdown:  {pm.current_drawdown:.1%}",
                f"  Max Drawdown:      {pm.max_drawdown:.1%}",
            ])

        lines.extend(["", "VALUE AT RISK", "-" * 30])

        if d.var_metrics:
            v = d.var_metrics
            lines.extend([
                f"  VaR (95%):  ${v.var_95:,.2f} ({v.var_95_pct:.2%})",
                f"  VaR (99%):  ${v.var_99:,.2f} ({v.var_99_pct:.2%})",
                f"  CVaR (95%): ${v.cvar_95:,.2f} ({v.cvar_95_pct:.2%})",
            ])

        lines.extend(["", "CONCENTRATION", "-" * 30])

        if d.concentration_metrics:
            cm = d.concentration_metrics
            lines.extend([
                f"  Largest Position: {cm.largest_position_symbol} ({cm.largest_position_weight:.1%})",
                f"  Top 5 Weight:     {cm.top5_weight:.1%}",
                f"  Largest Sector:   {cm.largest_sector_name} ({cm.largest_sector_weight:.1%})",
            ])

        lines.extend(["", "STRESS TESTS", "-" * 30])

        for result in d.stress_test_results[:5]:
            lines.append(
                f"  {result.scenario_name:25} {result.portfolio_impact_pct:+.1%} "
                f"(${result.portfolio_impact_dollars:+,.0f})"
            )

        lines.extend(["", "ACTIVE ALERTS", "-" * 30])

        if d.active_alerts:
            for alert in d.active_alerts:
                lines.append(f"  [{alert.level.upper()}] {alert.message}")
        else:
            lines.append("  No active alerts")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)
