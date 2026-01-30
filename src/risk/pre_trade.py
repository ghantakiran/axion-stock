"""Pre-Trade Risk Checks.

Validates orders against risk limits before submission.
Blocks or warns on dangerous trades.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.risk.config import RiskConfig, CheckResult, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class PortfolioContext:
    """Current portfolio state for risk checks."""

    equity: float
    cash: float
    buying_power: float
    positions: list[dict]  # [{symbol, market_value, weight, sector, beta}]
    daily_pnl_pct: float = 0.0
    current_drawdown_pct: float = 0.0
    day_trades_remaining: int = 3

    def get_position(self, symbol: str) -> Optional[dict]:
        """Get position by symbol."""
        for pos in self.positions:
            if pos.get("symbol") == symbol:
                return pos
        return None

    def get_sector_exposure(self, sector: str) -> float:
        """Get total exposure to a sector."""
        return sum(
            pos.get("weight", 0)
            for pos in self.positions
            if pos.get("sector") == sector
        )


@dataclass
class OrderContext:
    """Order being validated."""

    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: float  # Estimated execution price
    order_type: str = "market"  # 'market', 'limit'
    extended_hours: bool = False

    @property
    def notional_value(self) -> float:
        return self.quantity * self.price

    @property
    def is_buy(self) -> bool:
        return self.side.lower() == "buy"

    @property
    def is_sell(self) -> bool:
        return self.side.lower() == "sell"


class PreTradeRiskChecker:
    """Run pre-trade risk checks on orders.

    Example:
        checker = PreTradeRiskChecker(config)

        result = await checker.validate(
            order=OrderContext(symbol="AAPL", side="buy", quantity=100, price=180),
            portfolio=portfolio_context,
        )

        if not result.approved:
            print(f"Order blocked: {result.blocked_reasons}")
        elif result.has_warnings:
            print(f"Warnings: {result.warning_messages}")
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        sector_map: Optional[dict[str, str]] = None,
        adv_data: Optional[dict[str, float]] = None,  # Average daily volume
        volatility_data: Optional[dict[str, float]] = None,  # Annualized vol
        correlation_matrix: Optional[dict] = None,
    ):
        """Initialize checker.

        Args:
            config: Risk configuration.
            sector_map: Symbol to sector mapping.
            adv_data: Average daily volume by symbol.
            volatility_data: Annualized volatility by symbol.
            correlation_matrix: Correlation matrix.
        """
        self.config = config or RiskConfig()
        self.sector_map = sector_map or {}
        self.adv_data = adv_data or {}
        self.volatility_data = volatility_data or {}
        self.correlation_matrix = correlation_matrix

    async def validate(
        self,
        order: OrderContext,
        portfolio: PortfolioContext,
    ) -> ValidationResult:
        """Run all pre-trade risk checks.

        Args:
            order: Order to validate.
            portfolio: Current portfolio state.

        Returns:
            ValidationResult with approval status and any warnings/blocks.
        """
        checks = [
            self._check_buying_power(order, portfolio),
            self._check_position_limit(order, portfolio),
            self._check_sector_limit(order, portfolio),
            self._check_concentration(order, portfolio),
            self._check_drawdown_state(portfolio),
            self._check_daily_loss_limit(portfolio),
            self._check_pdt_rule(order, portfolio),
            self._check_liquidity(order),
            self._check_volatility(order),
            self._check_correlation(order, portfolio),
            self._check_beta_exposure(order, portfolio),
        ]

        # Run all checks (they're not actually async, but structured for extensibility)
        results = await asyncio.gather(*[asyncio.coroutine(lambda c=c: c)() for c in checks])

        # Collect failures and warnings
        blocks = [r for r in results if not r.passed and r.severity == "block"]
        warnings = [r for r in results if not r.passed and r.severity == "warning"]

        if blocks:
            return ValidationResult(
                approved=False,
                reasons=blocks,
                warnings=warnings,
            )

        return ValidationResult(
            approved=True,
            reasons=[],
            warnings=warnings,
        )

    def validate_sync(
        self,
        order: OrderContext,
        portfolio: PortfolioContext,
    ) -> ValidationResult:
        """Synchronous version of validate.

        Args:
            order: Order to validate.
            portfolio: Current portfolio state.

        Returns:
            ValidationResult.
        """
        checks = [
            self._check_buying_power(order, portfolio),
            self._check_position_limit(order, portfolio),
            self._check_sector_limit(order, portfolio),
            self._check_concentration(order, portfolio),
            self._check_drawdown_state(portfolio),
            self._check_daily_loss_limit(portfolio),
            self._check_pdt_rule(order, portfolio),
            self._check_liquidity(order),
            self._check_volatility(order),
            self._check_correlation(order, portfolio),
            self._check_beta_exposure(order, portfolio),
        ]

        blocks = [r for r in checks if not r.passed and r.severity == "block"]
        warnings = [r for r in checks if not r.passed and r.severity == "warning"]

        if blocks:
            return ValidationResult(
                approved=False,
                reasons=blocks,
                warnings=warnings,
            )

        return ValidationResult(
            approved=True,
            reasons=[],
            warnings=warnings,
        )

    # =========================================================================
    # Individual Checks
    # =========================================================================

    def _check_buying_power(
        self,
        order: OrderContext,
        portfolio: PortfolioContext,
    ) -> CheckResult:
        """Check if sufficient buying power exists."""
        if not order.is_buy:
            return CheckResult(passed=True, check_name="buying_power")

        # Account for cash buffer
        available = portfolio.buying_power * (1 - self.config.cash_buffer_pct)

        if order.notional_value > available:
            return CheckResult(
                passed=False,
                severity="block",
                message=f"Insufficient buying power. Need ${order.notional_value:,.2f}, have ${available:,.2f}",
                check_name="buying_power",
                metric_value=order.notional_value,
                threshold=available,
            )

        return CheckResult(passed=True, check_name="buying_power")

    def _check_position_limit(
        self,
        order: OrderContext,
        portfolio: PortfolioContext,
    ) -> CheckResult:
        """Check if order would exceed single position limit."""
        if not order.is_buy:
            return CheckResult(passed=True, check_name="position_limit")

        # Get current position value
        current_pos = portfolio.get_position(order.symbol)
        current_value = current_pos.get("market_value", 0) if current_pos else 0

        # Calculate resulting position
        resulting_value = current_value + order.notional_value
        resulting_weight = resulting_value / portfolio.equity if portfolio.equity > 0 else 0

        if resulting_weight > self.config.max_position_pct:
            return CheckResult(
                passed=False,
                severity="block",
                message=f"Position in {order.symbol} would be {resulting_weight:.1%} "
                       f"(limit: {self.config.max_position_pct:.0%})",
                check_name="position_limit",
                metric_value=resulting_weight,
                threshold=self.config.max_position_pct,
            )

        # Warn if approaching limit
        if resulting_weight > self.config.max_position_pct * 0.8:
            return CheckResult(
                passed=False,
                severity="warning",
                message=f"Position approaching limit: {resulting_weight:.1%} "
                       f"(limit: {self.config.max_position_pct:.0%})",
                check_name="position_limit",
                metric_value=resulting_weight,
                threshold=self.config.max_position_pct,
            )

        return CheckResult(passed=True, check_name="position_limit")

    def _check_sector_limit(
        self,
        order: OrderContext,
        portfolio: PortfolioContext,
    ) -> CheckResult:
        """Check if order would exceed sector concentration limit."""
        if not order.is_buy:
            return CheckResult(passed=True, check_name="sector_limit")

        sector = self.sector_map.get(order.symbol, "Unknown")
        if sector == "Unknown":
            return CheckResult(passed=True, check_name="sector_limit")

        # Get current sector exposure
        current_sector_weight = portfolio.get_sector_exposure(sector)

        # Calculate resulting exposure
        new_weight = order.notional_value / portfolio.equity if portfolio.equity > 0 else 0
        resulting_sector_weight = current_sector_weight + new_weight

        if resulting_sector_weight > self.config.max_sector_pct:
            return CheckResult(
                passed=False,
                severity="block",
                message=f"Sector '{sector}' would be {resulting_sector_weight:.1%} "
                       f"(limit: {self.config.max_sector_pct:.0%})",
                check_name="sector_limit",
                metric_value=resulting_sector_weight,
                threshold=self.config.max_sector_pct,
            )

        return CheckResult(passed=True, check_name="sector_limit")

    def _check_concentration(
        self,
        order: OrderContext,
        portfolio: PortfolioContext,
    ) -> CheckResult:
        """Check top-5 position concentration."""
        if not order.is_buy:
            return CheckResult(passed=True, check_name="concentration")

        # Get top 5 weights
        weights = sorted(
            [p.get("weight", 0) for p in portfolio.positions],
            reverse=True,
        )[:5]
        current_top5 = sum(weights)

        # New position weight
        new_weight = order.notional_value / portfolio.equity if portfolio.equity > 0 else 0

        # Estimate new top 5 (simplified)
        weights.append(new_weight)
        weights.sort(reverse=True)
        new_top5 = sum(weights[:5])

        if new_top5 > self.config.max_top5_pct:
            return CheckResult(
                passed=False,
                severity="warning",
                message=f"Top 5 concentration would be {new_top5:.1%} "
                       f"(limit: {self.config.max_top5_pct:.0%})",
                check_name="concentration",
                metric_value=new_top5,
                threshold=self.config.max_top5_pct,
            )

        return CheckResult(passed=True, check_name="concentration")

    def _check_drawdown_state(
        self,
        portfolio: PortfolioContext,
    ) -> CheckResult:
        """Check if portfolio is in drawdown protection mode."""
        if portfolio.current_drawdown_pct <= self.config.portfolio_drawdown_reduce:
            return CheckResult(
                passed=False,
                severity="block",
                message=f"Portfolio in drawdown protection mode ({portfolio.current_drawdown_pct:.1%}). "
                       f"New buys blocked.",
                check_name="drawdown_state",
                metric_value=portfolio.current_drawdown_pct,
                threshold=self.config.portfolio_drawdown_reduce,
            )

        if portfolio.current_drawdown_pct <= self.config.portfolio_drawdown_warning:
            return CheckResult(
                passed=False,
                severity="warning",
                message=f"Portfolio in drawdown ({portfolio.current_drawdown_pct:.1%})",
                check_name="drawdown_state",
                metric_value=portfolio.current_drawdown_pct,
                threshold=self.config.portfolio_drawdown_warning,
            )

        return CheckResult(passed=True, check_name="drawdown_state")

    def _check_daily_loss_limit(
        self,
        portfolio: PortfolioContext,
    ) -> CheckResult:
        """Check if daily loss limit has been hit."""
        if portfolio.daily_pnl_pct <= self.config.daily_loss_limit:
            return CheckResult(
                passed=False,
                severity="block",
                message=f"Daily loss limit hit ({portfolio.daily_pnl_pct:.1%}). Trading halted.",
                check_name="daily_loss_limit",
                metric_value=portfolio.daily_pnl_pct,
                threshold=self.config.daily_loss_limit,
            )

        # Warn if approaching
        if portfolio.daily_pnl_pct <= self.config.daily_loss_limit * 0.7:
            return CheckResult(
                passed=False,
                severity="warning",
                message=f"Approaching daily loss limit ({portfolio.daily_pnl_pct:.1%})",
                check_name="daily_loss_limit",
                metric_value=portfolio.daily_pnl_pct,
                threshold=self.config.daily_loss_limit,
            )

        return CheckResult(passed=True, check_name="daily_loss_limit")

    def _check_pdt_rule(
        self,
        order: OrderContext,
        portfolio: PortfolioContext,
    ) -> CheckResult:
        """Check Pattern Day Trader rule compliance."""
        # PDT only applies to accounts under $25k
        if portfolio.equity >= 25000:
            return CheckResult(passed=True, check_name="pdt_rule")

        # Only relevant for sells
        if not order.is_sell:
            return CheckResult(passed=True, check_name="pdt_rule")

        if portfolio.day_trades_remaining <= 0:
            return CheckResult(
                passed=False,
                severity="warning",
                message="No day trades remaining. This could trigger PDT restriction.",
                check_name="pdt_rule",
                metric_value=0,
                threshold=1,
            )

        return CheckResult(passed=True, check_name="pdt_rule")

    def _check_liquidity(
        self,
        order: OrderContext,
    ) -> CheckResult:
        """Check if order size is reasonable vs average daily volume."""
        adv = self.adv_data.get(order.symbol, 1_000_000)  # Default 1M shares

        participation = order.quantity / adv

        if participation > self.config.max_adv_participation:
            return CheckResult(
                passed=False,
                severity="block",
                message=f"Order is {participation:.1%} of ADV (limit: {self.config.max_adv_participation:.0%})",
                check_name="liquidity",
                metric_value=participation,
                threshold=self.config.max_adv_participation,
            )

        # Warn if high participation
        if participation > self.config.max_adv_participation * 0.5:
            return CheckResult(
                passed=False,
                severity="warning",
                message=f"High ADV participation: {participation:.1%}",
                check_name="liquidity",
                metric_value=participation,
                threshold=self.config.max_adv_participation,
            )

        return CheckResult(passed=True, check_name="liquidity")

    def _check_volatility(
        self,
        order: OrderContext,
    ) -> CheckResult:
        """Check if stock volatility is within acceptable range."""
        vol = self.volatility_data.get(order.symbol, 0.30)  # Default 30%

        if vol > self.config.max_position_volatility:
            return CheckResult(
                passed=False,
                severity="warning",
                message=f"{order.symbol} volatility is {vol:.0%} "
                       f"(limit: {self.config.max_position_volatility:.0%})",
                check_name="volatility",
                metric_value=vol,
                threshold=self.config.max_position_volatility,
            )

        return CheckResult(passed=True, check_name="volatility")

    def _check_correlation(
        self,
        order: OrderContext,
        portfolio: PortfolioContext,
    ) -> CheckResult:
        """Check for high correlation with existing positions."""
        if self.correlation_matrix is None or not order.is_buy:
            return CheckResult(passed=True, check_name="correlation")

        high_corr_count = 0
        high_corr_symbols = []

        for pos in portfolio.positions:
            symbol = pos.get("symbol", "")
            if symbol == order.symbol:
                continue

            # Get correlation
            corr = self.correlation_matrix.get(f"{order.symbol}_{symbol}", 0)
            if abs(corr) > self.config.max_correlation:
                high_corr_count += 1
                high_corr_symbols.append(symbol)

        if high_corr_count >= 2:
            return CheckResult(
                passed=False,
                severity="warning",
                message=f"{order.symbol} highly correlated (>{self.config.max_correlation:.0%}) "
                       f"with {high_corr_count} positions: {', '.join(high_corr_symbols[:3])}",
                check_name="correlation",
                metric_value=high_corr_count,
                threshold=2,
            )

        return CheckResult(passed=True, check_name="correlation")

    def _check_beta_exposure(
        self,
        order: OrderContext,
        portfolio: PortfolioContext,
    ) -> CheckResult:
        """Check if portfolio beta would exceed limit."""
        if not order.is_buy:
            return CheckResult(passed=True, check_name="beta_exposure")

        # Get current portfolio beta
        total_value = sum(p.get("market_value", 0) for p in portfolio.positions)
        current_beta = sum(
            p.get("beta", 1.0) * p.get("market_value", 0)
            for p in portfolio.positions
        ) / total_value if total_value > 0 else 1.0

        # Estimate new beta (assume beta=1 for new position if unknown)
        # This is simplified - in production, would look up actual beta
        new_pos_beta = 1.0

        new_total = total_value + order.notional_value
        new_portfolio_beta = (
            current_beta * total_value + new_pos_beta * order.notional_value
        ) / new_total if new_total > 0 else 1.0

        if new_portfolio_beta > self.config.max_portfolio_beta:
            return CheckResult(
                passed=False,
                severity="warning",
                message=f"Portfolio beta would be {new_portfolio_beta:.2f} "
                       f"(limit: {self.config.max_portfolio_beta:.1f})",
                check_name="beta_exposure",
                metric_value=new_portfolio_beta,
                threshold=self.config.max_portfolio_beta,
            )

        return CheckResult(passed=True, check_name="beta_exposure")
