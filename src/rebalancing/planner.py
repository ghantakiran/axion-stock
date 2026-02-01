"""Rebalance Planner.

Generates trade plans to bring portfolio weights back to targets.
Supports full, threshold-only, and tax-aware rebalancing.
"""

import logging
from datetime import date
from typing import Optional

from src.rebalancing.config import (
    CostConfig,
    TaxConfig,
    DriftConfig,
    DEFAULT_COST_CONFIG,
    DEFAULT_TAX_CONFIG,
    DEFAULT_DRIFT_CONFIG,
)
from src.rebalancing.models import (
    Holding,
    RebalanceTrade,
    RebalancePlan,
    PortfolioDrift,
)
from src.rebalancing.drift import DriftMonitor

logger = logging.getLogger(__name__)


class RebalancePlanner:
    """Plans rebalance trades with cost and tax optimization."""

    def __init__(
        self,
        cost_config: Optional[CostConfig] = None,
        tax_config: Optional[TaxConfig] = None,
        drift_config: Optional[DriftConfig] = None,
    ) -> None:
        self.cost_config = cost_config or DEFAULT_COST_CONFIG
        self.tax_config = tax_config or DEFAULT_TAX_CONFIG
        self.drift_config = drift_config or DEFAULT_DRIFT_CONFIG
        self._drift_monitor = DriftMonitor(config=self.drift_config)

    def plan_full_rebalance(
        self,
        holdings: list[Holding],
        portfolio_value: float,
    ) -> RebalancePlan:
        """Plan full rebalance — trade all assets to exact target weights.

        Args:
            holdings: Current holdings with target weights.
            portfolio_value: Total portfolio value.

        Returns:
            RebalancePlan with all required trades.
        """
        drift_before = self._drift_monitor.compute_drift(holdings)
        trades = self._generate_trades(holdings, portfolio_value, threshold_only=False)
        return self._build_plan(trades, drift_before, portfolio_value)

    def plan_threshold_rebalance(
        self,
        holdings: list[Holding],
        portfolio_value: float,
    ) -> RebalancePlan:
        """Plan threshold rebalance — only trade assets exceeding drift threshold.

        Args:
            holdings: Current holdings with target weights.
            portfolio_value: Total portfolio value.

        Returns:
            RebalancePlan with trades for drifted assets only.
        """
        drift_before = self._drift_monitor.compute_drift(holdings)
        trades = self._generate_trades(holdings, portfolio_value, threshold_only=True)
        return self._build_plan(trades, drift_before, portfolio_value)

    def plan_tax_aware_rebalance(
        self,
        holdings: list[Holding],
        portfolio_value: float,
    ) -> RebalancePlan:
        """Plan tax-aware rebalance — avoid short-term gains, harvest losses.

        Args:
            holdings: Current holdings with cost basis and acquisition dates.
            portfolio_value: Total portfolio value.

        Returns:
            RebalancePlan with tax-optimized trades.
        """
        drift_before = self._drift_monitor.compute_drift(holdings)
        trades = self._generate_trades(
            holdings, portfolio_value, threshold_only=True, tax_aware=True
        )
        return self._build_plan(trades, drift_before, portfolio_value)

    def _generate_trades(
        self,
        holdings: list[Holding],
        portfolio_value: float,
        threshold_only: bool = False,
        tax_aware: bool = False,
    ) -> list[RebalanceTrade]:
        """Generate rebalance trades."""
        trades: list[RebalanceTrade] = []

        for h in holdings:
            drift = h.current_weight - h.target_weight

            # Skip if below threshold in threshold mode
            if threshold_only and abs(drift) < self.drift_config.threshold:
                continue

            target_value = h.target_weight * portfolio_value
            current_value = h.current_weight * portfolio_value
            trade_value = target_value - current_value

            # Skip small trades
            if abs(trade_value) < self.cost_config.min_trade_dollars:
                continue

            # Tax-aware: skip sells of short-term gainers
            tax_impact = 0.0
            skip_trade = False
            is_harvest = False

            if tax_aware and self.tax_config.enabled and trade_value < 0:
                # Selling
                if h.is_short_term and h.unrealized_pnl > 0:
                    if self.tax_config.avoid_short_term_gains:
                        skip_trade = True
                # Tax loss harvesting
                if h.unrealized_pnl < 0 and abs(h.unrealized_pnl) / max(h.market_value, 1) >= self.tax_config.harvest_threshold:
                    is_harvest = True
                    tax_impact = h.unrealized_pnl * 0.20  # Estimated tax benefit

            if skip_trade:
                continue

            side = "buy" if trade_value > 0 else "sell"
            shares = int(abs(trade_value) / h.price) if h.price > 0 else 0

            if shares < self.cost_config.min_trade_shares:
                continue

            # Estimated cost
            spread_cost = abs(trade_value) * self.cost_config.spread_cost_bps / 10000
            estimated_cost = self.cost_config.commission_per_trade + spread_cost

            trades.append(RebalanceTrade(
                symbol=h.symbol,
                side=side,
                shares=shares,
                value=round(abs(trade_value), 2),
                from_weight=round(h.current_weight, 4),
                to_weight=round(h.target_weight, 4),
                estimated_cost=round(estimated_cost, 2),
                tax_impact=round(tax_impact, 2),
                is_tax_loss_harvest=is_harvest,
            ))

        return trades

    def _build_plan(
        self,
        trades: list[RebalanceTrade],
        drift_before: PortfolioDrift,
        portfolio_value: float,
    ) -> RebalancePlan:
        """Build plan from trades."""
        total_buy = sum(t.value for t in trades if t.side == "buy")
        total_sell = sum(t.value for t in trades if t.side == "sell")
        turnover = (total_buy + total_sell) / 2 if portfolio_value > 0 else 0.0
        estimated_cost = sum(t.estimated_cost for t in trades)
        estimated_tax = sum(t.tax_impact for t in trades)

        # Estimate drift after (approximate)
        drift_after = drift_before.max_drift
        if trades:
            # Trades reduce drift; rough estimate
            traded_symbols = {t.symbol for t in trades}
            remaining_drifts = [
                abs(d.drift) for d in drift_before.asset_drifts
                if d.symbol not in traded_symbols
            ]
            drift_after = max(remaining_drifts) if remaining_drifts else 0.0

        return RebalancePlan(
            trades=trades,
            total_turnover=round(turnover, 2),
            total_buy_value=round(total_buy, 2),
            total_sell_value=round(total_sell, 2),
            estimated_cost=round(estimated_cost, 2),
            estimated_tax=round(estimated_tax, 2),
            drift_before=drift_before.max_drift,
            drift_after=round(drift_after, 4),
            n_trades=len(trades),
            date=date.today(),
        )
