"""Hedge Constructor.

Sizes and recommends tail-risk hedges using puts, VIX calls,
inverse ETFs, and cash, with cost/effectiveness scoring.
"""

import logging
from typing import Optional

import numpy as np

from src.tailrisk.config import HedgingConfig, HedgeInstrument
from src.tailrisk.models import HedgeRecommendation, HedgePortfolio

logger = logging.getLogger(__name__)


class HedgeConstructor:
    """Constructs tail-risk hedging portfolios."""

    def __init__(self, config: Optional[HedgingConfig] = None) -> None:
        self.config = config or HedgingConfig()

    def protective_put(
        self,
        portfolio_value: float,
        volatility: float,
        protection_pct: Optional[float] = None,
        otm_pct: Optional[float] = None,
        horizon_days: Optional[int] = None,
    ) -> HedgeRecommendation:
        """Size a protective put hedge.

        Estimates put cost using simplified Black-Scholes-like approximation.

        Args:
            portfolio_value: Portfolio value to protect.
            volatility: Annualized portfolio volatility.
            protection_pct: Desired protection level (e.g., 0.10 = 10% decline).
            otm_pct: How far OTM the put strike is (e.g., 0.05 = 5% OTM).
            horizon_days: Hedge horizon in days.

        Returns:
            HedgeRecommendation.
        """
        protection = protection_pct or self.config.target_protection_pct
        otm = otm_pct or self.config.put_otm_pct
        horizon = horizon_days or self.config.hedge_horizon_days

        # Simplified put cost: vol * sqrt(T/252) * cost_factor
        t_frac = horizon / 252
        cost_factor = 0.4  # Approximate for ATM; OTM is cheaper
        otm_discount = max(0.3, 1.0 - otm * 5)  # Deeper OTM = cheaper
        put_cost_pct = volatility * np.sqrt(t_frac) * cost_factor * otm_discount
        put_cost_pct = min(put_cost_pct, self.config.max_hedge_cost_pct * 2)

        notional = portfolio_value
        cost_dollar = put_cost_pct * notional

        # Effectiveness: how much of the tail risk is hedged
        effectiveness = min(1.0, protection / (volatility * np.sqrt(t_frac) * 2))

        return HedgeRecommendation(
            instrument=HedgeInstrument.PUT_OPTION.value,
            notional=round(notional, 2),
            cost_pct=round(float(put_cost_pct), 6),
            cost_dollar=round(float(cost_dollar), 2),
            protection_pct=round(protection, 4),
            hedge_ratio=1.0,
            effectiveness=round(float(effectiveness), 4),
            description=f"Put {otm*100:.0f}% OTM, {horizon}d expiry",
        )

    def vix_call(
        self,
        portfolio_value: float,
        volatility: float,
        vix_level: float = 15.0,
        hedge_ratio: Optional[float] = None,
    ) -> HedgeRecommendation:
        """Size a VIX call hedge.

        VIX calls profit when volatility spikes, providing convex
        tail protection.

        Args:
            portfolio_value: Portfolio value.
            volatility: Portfolio volatility.
            vix_level: Current VIX level.
            hedge_ratio: Fraction of portfolio to hedge via VIX.

        Returns:
            HedgeRecommendation.
        """
        ratio = hedge_ratio or self.config.vix_hedge_ratio
        notional = portfolio_value * ratio

        # VIX call cost: approximation based on VIX level
        # Higher VIX = more expensive calls
        vix_premium_factor = 0.10 + (vix_level / 100) * 0.5
        cost_pct = ratio * vix_premium_factor
        cost_dollar = cost_pct * portfolio_value

        # Effectiveness: VIX calls are highly effective in crashes
        # but less so in slow drawdowns
        effectiveness = min(1.0, 0.7 + (vix_level - 15) * 0.01)
        effectiveness = max(0.3, effectiveness)

        # Protection estimate: VIX typically doubles in a crash
        # So hedge_ratio * VIX_gain offsets portfolio loss
        protection = ratio * 1.5  # Assume VIX 50% gain in moderate stress

        return HedgeRecommendation(
            instrument=HedgeInstrument.VIX_CALL.value,
            notional=round(notional, 2),
            cost_pct=round(float(cost_pct), 6),
            cost_dollar=round(float(cost_dollar), 2),
            protection_pct=round(float(protection), 4),
            hedge_ratio=round(ratio, 4),
            effectiveness=round(float(effectiveness), 4),
            description=f"VIX call, {ratio*100:.0f}% notional, VIX={vix_level:.0f}",
        )

    def cash_hedge(
        self,
        portfolio_value: float,
        cash_pct: float = 0.10,
    ) -> HedgeRecommendation:
        """Recommend cash allocation as hedge.

        Args:
            portfolio_value: Portfolio value.
            cash_pct: Percentage to hold in cash.

        Returns:
            HedgeRecommendation.
        """
        notional = portfolio_value * cash_pct
        # Cost of cash = opportunity cost (assume 5% equity premium)
        cost_pct = cash_pct * 0.05 / 12  # Monthly opportunity cost
        protection = cash_pct  # Direct linear protection

        return HedgeRecommendation(
            instrument=HedgeInstrument.CASH.value,
            notional=round(notional, 2),
            cost_pct=round(float(cost_pct), 6),
            cost_dollar=round(float(cost_pct * portfolio_value), 2),
            protection_pct=round(protection, 4),
            hedge_ratio=round(cash_pct, 4),
            effectiveness=round(0.4, 4),  # Cash is simple but not convex
            description=f"Cash allocation {cash_pct*100:.0f}%",
        )

    def build_hedge_portfolio(
        self,
        portfolio_value: float,
        volatility: float,
        cvar_pct: float,
        vix_level: float = 15.0,
        max_cost_pct: Optional[float] = None,
    ) -> HedgePortfolio:
        """Build a complete hedge portfolio.

        Combines puts, VIX calls, and cash within a cost budget.

        Args:
            portfolio_value: Portfolio value.
            volatility: Portfolio volatility.
            cvar_pct: Current CVaR (for measuring reduction).
            vix_level: Current VIX.
            max_cost_pct: Maximum hedge cost as % of portfolio.

        Returns:
            HedgePortfolio.
        """
        budget = max_cost_pct or self.config.max_hedge_cost_pct
        hedges = []
        remaining_budget = budget

        # 1. Protective put (primary hedge)
        put = self.protective_put(portfolio_value, volatility)
        if put.cost_pct <= remaining_budget:
            hedges.append(put)
            remaining_budget -= put.cost_pct

        # 2. VIX call (convex tail hedge)
        if remaining_budget > 0.001:
            # Scale VIX ratio to fit budget
            affordable_ratio = min(self.config.vix_hedge_ratio, remaining_budget / 0.15)
            if affordable_ratio > 0.01:
                vix = self.vix_call(portfolio_value, volatility, vix_level, affordable_ratio)
                if vix.cost_pct <= remaining_budget:
                    hedges.append(vix)
                    remaining_budget -= vix.cost_pct

        # 3. Cash (residual)
        if remaining_budget > 0.001:
            cash_pct = min(0.10, remaining_budget / 0.005)
            cash = self.cash_hedge(portfolio_value, cash_pct)
            hedges.append(cash)

        total_cost_pct = sum(h.cost_pct for h in hedges)
        total_cost_dollar = sum(h.cost_dollar for h in hedges)
        total_protection = sum(h.protection_pct * h.effectiveness for h in hedges)

        # Estimate hedged CVaR
        hedged_cvar = max(0, cvar_pct - total_protection * cvar_pct)

        return HedgePortfolio(
            hedges=hedges,
            total_cost_pct=round(float(total_cost_pct), 6),
            total_cost_dollar=round(float(total_cost_dollar), 2),
            total_protection_pct=round(float(total_protection), 4),
            portfolio_value=portfolio_value,
            unhedged_cvar=round(cvar_pct, 6),
            hedged_cvar=round(float(hedged_cvar), 6),
        )
