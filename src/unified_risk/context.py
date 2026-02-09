"""Unified Risk Context — single pass-through object for all risk checks.

Consolidates PortfolioRiskMonitor, CircuitBreaker, KillSwitch, and
the new CorrelationGuard + VaR sizer into one coherent assessment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.unified_risk.correlation import (
    CorrelationConfig,
    CorrelationGuard,
    CorrelationMatrix,
)
from src.unified_risk.var_sizer import VaRConfig, VaRPositionSizer, VaRResult
from src.unified_risk.regime_limits import RegimeLimits, RegimeRiskAdapter


@dataclass
class RiskContextConfig:
    """Configuration for the unified risk context.

    Attributes:
        max_daily_loss_pct: Max daily loss as % of equity (single source of truth).
        max_concurrent_positions: Base max positions (before regime adjustment).
        max_single_stock_pct: Max single position as % of equity.
        max_sector_pct: Max sector exposure as %.
        correlation_config: Config for the correlation guard.
        var_config: Config for VaR-based sizing.
        default_regime: Fallback market regime.
        enable_correlation_guard: Whether to enforce correlation limits.
        enable_var_sizing: Whether to use VaR-based position sizing.
    """

    max_daily_loss_pct: float = 10.0
    max_concurrent_positions: int = 10
    max_single_stock_pct: float = 15.0
    max_sector_pct: float = 30.0
    correlation_config: CorrelationConfig = field(default_factory=CorrelationConfig)
    var_config: VaRConfig = field(default_factory=VaRConfig)
    default_regime: str = "sideways"
    enable_correlation_guard: bool = True
    enable_var_sizing: bool = True


@dataclass
class UnifiedRiskAssessment:
    """Complete risk assessment combining all subsystems.

    This is the single object passed through the execution pipeline,
    replacing fragmented checks from RiskGate, KillSwitch, etc.

    Attributes:
        approved: Overall verdict.
        rejection_reason: Why rejected (None if approved).
        daily_pnl: Today's P&L (single source of truth).
        daily_pnl_pct: Today's P&L as % of equity.
        current_positions: Count of open positions.
        regime: Current market regime.
        regime_limits: Applied regime adjustments.
        correlation_matrix: Latest correlation computation.
        concentration_score: Portfolio concentration 0-100.
        portfolio_var: Portfolio VaR result.
        max_position_size: VaR-adjusted max size for next trade.
        circuit_breaker_status: Current CB state (closed/open/half_open).
        kill_switch_active: Whether kill switch is engaged.
        warnings: All accumulated warnings.
        checks_run: Names of all checks that were executed.
        timestamp: When this assessment was computed.
    """

    approved: bool = True
    rejection_reason: Optional[str] = None
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    current_positions: int = 0
    regime: str = "sideways"
    regime_limits: Optional[RegimeLimits] = None
    correlation_matrix: Optional[CorrelationMatrix] = None
    concentration_score: float = 0.0
    portfolio_var: Optional[VaRResult] = None
    max_position_size: float = 0.0
    circuit_breaker_status: str = "closed"
    kill_switch_active: bool = False
    warnings: list[str] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "rejection_reason": self.rejection_reason,
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_pnl_pct": round(self.daily_pnl_pct, 2),
            "current_positions": self.current_positions,
            "regime": self.regime,
            "regime_limits": self.regime_limits.to_dict() if self.regime_limits else None,
            "concentration_score": round(self.concentration_score, 1),
            "portfolio_var": self.portfolio_var.to_dict() if self.portfolio_var else None,
            "max_position_size": round(self.max_position_size, 2),
            "circuit_breaker_status": self.circuit_breaker_status,
            "kill_switch_active": self.kill_switch_active,
            "warnings": self.warnings,
            "checks_run": self.checks_run,
            "timestamp": self.timestamp.isoformat(),
        }


class RiskContext:
    """Unified risk assessment engine.

    Consolidates all risk subsystems into a single assess() call
    that produces a UnifiedRiskAssessment.

    Args:
        config: RiskContextConfig with all thresholds.
        equity: Current account equity.

    Example:
        ctx = RiskContext(equity=100_000)
        assessment = ctx.assess(
            ticker="AAPL",
            direction="long",
            positions=[...],
            daily_pnl=-500,
            returns_by_ticker={...},
            regime="bull"
        )
        if assessment.approved:
            execute_trade(size=assessment.max_position_size)
    """

    def __init__(
        self,
        config: RiskContextConfig | None = None,
        equity: float = 100_000.0,
    ) -> None:
        self.config = config or RiskContextConfig()
        self._equity = equity

        # Subsystems
        self._correlation_guard = CorrelationGuard(self.config.correlation_config)
        self._var_sizer = VaRPositionSizer(self.config.var_config, equity)
        self._regime_adapter = RegimeRiskAdapter(
            default_regime=self.config.default_regime
        )

        # Unified daily P&L tracking (single source of truth)
        self._daily_pnl: float = 0.0
        self._starting_equity: float = equity

    @property
    def equity(self) -> float:
        return self._equity

    @equity.setter
    def equity(self, value: float) -> None:
        self._equity = max(0.0, value)
        self._var_sizer.equity = value

    def record_pnl(self, pnl: float) -> None:
        """Record a P&L event (unified tracking)."""
        self._daily_pnl += pnl

    def reset_daily(self) -> None:
        """Reset daily tracking at start of trading day."""
        self._daily_pnl = 0.0
        self._starting_equity = self._equity

    def assess(
        self,
        ticker: str,
        direction: str,
        positions: list[dict[str, Any]],
        returns_by_ticker: dict[str, list[float]] | None = None,
        regime: str | None = None,
        circuit_breaker_status: str = "closed",
        kill_switch_active: bool = False,
        vix: float = 20.0,
    ) -> UnifiedRiskAssessment:
        """Run all risk checks and produce a unified assessment.

        Args:
            ticker: Symbol to trade.
            direction: long or short.
            positions: Current open positions (list of dicts).
            returns_by_ticker: Historical daily returns for correlation/VaR.
            regime: Current market regime (auto-detected if None).
            circuit_breaker_status: Current circuit breaker state.
            kill_switch_active: Whether kill switch is engaged.
            vix: Current VIX level.

        Returns:
            UnifiedRiskAssessment with verdict and all metrics.
        """
        warnings: list[str] = []
        checks_run: list[str] = []
        regime = regime or self.config.default_regime
        self._regime_adapter.set_regime(regime)
        limits = self._regime_adapter.get_limits()

        # 1. Kill switch check
        checks_run.append("kill_switch")
        if kill_switch_active:
            return self._reject(
                "Kill switch is active", warnings, checks_run, regime, limits
            )

        # 2. Circuit breaker check
        checks_run.append("circuit_breaker")
        if circuit_breaker_status == "open":
            return self._reject(
                "Circuit breaker is OPEN", warnings, checks_run, regime, limits
            )

        # 3. Daily loss limit (unified)
        checks_run.append("daily_loss_limit")
        if self._starting_equity > 0:
            daily_pnl_pct = abs(self._daily_pnl) / self._starting_equity * 100.0
            if self._daily_pnl < 0 and daily_pnl_pct >= self.config.max_daily_loss_pct:
                return self._reject(
                    f"Daily loss {daily_pnl_pct:.1f}% >= limit {self.config.max_daily_loss_pct}%",
                    warnings, checks_run, regime, limits,
                )

        # 4. Max positions (regime-adjusted)
        checks_run.append("max_positions")
        adjusted_max = self._regime_adapter.adjust_max_positions(
            self.config.max_concurrent_positions
        )
        if len(positions) >= adjusted_max:
            return self._reject(
                f"Max positions reached: {len(positions)}/{adjusted_max} "
                f"(regime={regime})",
                warnings, checks_run, regime, limits,
            )

        # 5. Single stock concentration
        checks_run.append("single_stock_concentration")
        if self._equity > 0:
            ticker_exposure = sum(
                abs(float(p.get("market_value", 0)))
                for p in positions if p.get("symbol") == ticker
            )
            exposure_pct = ticker_exposure / self._equity * 100.0
            if exposure_pct >= self.config.max_single_stock_pct:
                return self._reject(
                    f"{ticker} exposure {exposure_pct:.1f}% >= {self.config.max_single_stock_pct}%",
                    warnings, checks_run, regime, limits,
                )

        # 6. Correlation guard
        corr_matrix = None
        concentration_score = 0.0
        if self.config.enable_correlation_guard and returns_by_ticker:
            checks_run.append("correlation_guard")
            corr_matrix = self._correlation_guard.compute_matrix(returns_by_ticker)
            current_holdings = [p.get("symbol", "") for p in positions]
            corr_ok, corr_reason = self._correlation_guard.check_new_trade(
                ticker, corr_matrix, current_holdings
            )
            if not corr_ok:
                return self._reject(
                    corr_reason, warnings, checks_run, regime, limits,
                    correlation_matrix=corr_matrix,
                )
            concentration_score = self._correlation_guard.get_portfolio_concentration_score(
                corr_matrix, current_holdings + [ticker]
            )
            if concentration_score > 75:
                warnings.append(
                    f"High portfolio concentration: {concentration_score:.0f}/100"
                )

        # 7. VaR-based sizing
        portfolio_var = None
        max_position_size = self.config.max_single_stock_pct / 100.0 * self._equity
        if self.config.enable_var_sizing and returns_by_ticker:
            checks_run.append("var_sizing")
            ticker_returns = returns_by_ticker.get(ticker, [])
            if ticker_returns:
                portfolio_var = self._var_sizer.compute_var(ticker_returns)
                max_position_size = self._var_sizer.size_position(
                    ticker_returns, 1.0, portfolio_var.var_pct
                )

        # Apply regime multiplier to position size
        max_position_size = self._regime_adapter.adjust_position_size(max_position_size)

        # Circuit breaker half-open: reduce size
        size_mult = 0.5 if circuit_breaker_status == "half_open" else 1.0
        max_position_size *= size_mult

        return UnifiedRiskAssessment(
            approved=True,
            daily_pnl=self._daily_pnl,
            daily_pnl_pct=abs(self._daily_pnl) / max(self._starting_equity, 1) * 100,
            current_positions=len(positions),
            regime=regime,
            regime_limits=limits,
            correlation_matrix=corr_matrix,
            concentration_score=concentration_score,
            portfolio_var=portfolio_var,
            max_position_size=max_position_size,
            circuit_breaker_status=circuit_breaker_status,
            kill_switch_active=kill_switch_active,
            warnings=warnings,
            checks_run=checks_run,
        )

    def _reject(
        self,
        reason: str,
        warnings: list[str],
        checks_run: list[str],
        regime: str,
        limits: RegimeLimits,
        correlation_matrix: CorrelationMatrix | None = None,
    ) -> UnifiedRiskAssessment:
        """Helper to create a rejected assessment."""
        return UnifiedRiskAssessment(
            approved=False,
            rejection_reason=reason,
            daily_pnl=self._daily_pnl,
            daily_pnl_pct=abs(self._daily_pnl) / max(self._starting_equity, 1) * 100,
            regime=regime,
            regime_limits=limits,
            correlation_matrix=correlation_matrix,
            circuit_breaker_status="closed",
            warnings=warnings,
            checks_run=checks_run,
        )
