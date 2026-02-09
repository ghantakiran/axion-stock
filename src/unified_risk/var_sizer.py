"""VaR-Based Position Sizer — risk-adjusted dynamic sizing.

Uses historical VaR (Value at Risk) and CVaR (Conditional VaR)
to dynamically adjust position sizes based on actual tail risk.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class VaRConfig:
    """Configuration for VaR-based position sizing.

    Attributes:
        confidence_level: VaR confidence (e.g., 0.95 for 95% VaR).
        max_portfolio_var_pct: Max portfolio VaR as % of equity.
        max_position_var_pct: Max single position VaR as % of equity.
        lookback_days: Days of returns for VaR calculation.
        use_cvar: Use Conditional VaR (Expected Shortfall) instead of VaR.
        decay_factor: Exponential decay for recent vs. old observations.
    """

    confidence_level: float = 0.95
    max_portfolio_var_pct: float = 2.0
    max_position_var_pct: float = 0.5
    lookback_days: int = 252
    use_cvar: bool = True
    decay_factor: float = 0.97


@dataclass
class VaRResult:
    """Result of a VaR calculation.

    Attributes:
        var_pct: Value at Risk as percentage.
        cvar_pct: Conditional VaR (Expected Shortfall) as percentage.
        max_position_size: Maximum recommended position size (shares/dollars).
        risk_budget_remaining: How much VaR budget is left for new trades.
        confidence_level: The confidence level used.
        data_points: Number of returns used in calculation.
    """

    var_pct: float = 0.0
    cvar_pct: float = 0.0
    max_position_size: float = 0.0
    risk_budget_remaining: float = 0.0
    confidence_level: float = 0.95
    data_points: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "var_pct": round(self.var_pct, 4),
            "cvar_pct": round(self.cvar_pct, 4),
            "max_position_size": round(self.max_position_size, 2),
            "risk_budget_remaining": round(self.risk_budget_remaining, 4),
            "confidence_level": self.confidence_level,
            "data_points": self.data_points,
        }


class VaRPositionSizer:
    """Sizes positions using VaR/CVaR risk budgeting.

    Calculates the maximum position size such that the portfolio's
    total VaR stays within the configured budget.

    Args:
        config: VaRConfig with confidence and risk budget limits.
        equity: Current account equity.

    Example:
        sizer = VaRPositionSizer(equity=100_000)
        result = sizer.compute_var(returns=[...])
        max_shares = sizer.size_position(
            ticker_returns=[...],
            current_price=185.0,
            existing_var_pct=1.2
        )
    """

    def __init__(
        self,
        config: VaRConfig | None = None,
        equity: float = 100_000.0,
    ) -> None:
        self.config = config or VaRConfig()
        self._equity = equity

    @property
    def equity(self) -> float:
        return self._equity

    @equity.setter
    def equity(self, value: float) -> None:
        self._equity = max(0.0, value)

    def compute_var(self, returns: list[float]) -> VaRResult:
        """Compute VaR and CVaR from a return series.

        Args:
            returns: List of daily returns (e.g., [-0.02, 0.01, 0.005, ...]).

        Returns:
            VaRResult with VaR, CVaR, and risk budget info.
        """
        if len(returns) < 10:
            return VaRResult(data_points=len(returns))

        sorted_returns = sorted(returns)
        n = len(sorted_returns)

        # Historical VaR: the loss at the confidence percentile
        var_index = int(n * (1.0 - self.config.confidence_level))
        var_index = max(0, min(var_index, n - 1))
        var_pct = abs(sorted_returns[var_index]) * 100.0

        # CVaR: average of losses beyond VaR
        tail = sorted_returns[: var_index + 1]
        cvar_pct = abs(sum(tail) / max(len(tail), 1)) * 100.0

        # Risk budget
        risk_metric = cvar_pct if self.config.use_cvar else var_pct
        budget_remaining = max(0.0, self.config.max_portfolio_var_pct - risk_metric)

        return VaRResult(
            var_pct=var_pct,
            cvar_pct=cvar_pct,
            max_position_size=budget_remaining / 100.0 * self._equity,
            risk_budget_remaining=budget_remaining,
            confidence_level=self.config.confidence_level,
            data_points=n,
        )

    def size_position(
        self,
        ticker_returns: list[float],
        current_price: float,
        existing_var_pct: float = 0.0,
    ) -> float:
        """Calculate maximum position size in dollars for a new trade.

        Uses the ticker's individual VaR to determine how much capital
        can be allocated while staying within the portfolio VaR budget.

        Args:
            ticker_returns: Historical daily returns for this ticker.
            current_price: Current share price.
            existing_var_pct: Current portfolio VaR as % of equity.

        Returns:
            Maximum position size in dollars.
        """
        if current_price <= 0 or self._equity <= 0:
            return 0.0

        result = self.compute_var(ticker_returns)
        if result.var_pct <= 0:
            return self.config.max_position_var_pct / 100.0 * self._equity

        # Budget left for new positions
        var_budget = self.config.max_portfolio_var_pct - existing_var_pct
        if var_budget <= 0:
            return 0.0

        # Position size = budget / ticker's VaR
        position_var_limit = min(var_budget, self.config.max_position_var_pct)
        risk_metric = result.cvar_pct if self.config.use_cvar else result.var_pct
        if risk_metric <= 0:
            return self.config.max_position_var_pct / 100.0 * self._equity

        max_dollars = (position_var_limit / risk_metric) * self._equity * (risk_metric / 100.0)
        # Cap at the per-position VaR limit
        max_dollars = min(max_dollars, self.config.max_position_var_pct / 100.0 * self._equity)

        return max_dollars

    def compute_portfolio_var(
        self, positions_returns: dict[str, list[float]], weights: dict[str, float]
    ) -> VaRResult:
        """Compute portfolio-level VaR from individual return series.

        Uses weighted combination of returns (ignoring cross-correlations
        for simplicity — for full treatment, use the CorrelationGuard).

        Args:
            positions_returns: Dict of ticker → daily returns.
            weights: Dict of ticker → portfolio weight (sum to ~1.0).

        Returns:
            VaRResult for the portfolio.
        """
        if not positions_returns or not weights:
            return VaRResult()

        # Find the shortest common length
        min_len = min(len(r) for r in positions_returns.values())
        if min_len < 10:
            return VaRResult(data_points=min_len)

        # Compute weighted portfolio returns
        portfolio_returns = [0.0] * min_len
        for ticker, rets in positions_returns.items():
            w = weights.get(ticker, 0.0)
            for i in range(min_len):
                portfolio_returns[i] += w * rets[i]

        return self.compute_var(portfolio_returns)
