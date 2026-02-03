"""Debt Structure Analyzer.

Analyzes debt composition, leverage ratios, maturity profiles,
refinancing risk, and composite credit health scoring.
"""

import logging
from datetime import date
from typing import Optional

import numpy as np

from src.credit.config import StructureConfig, DEFAULT_CREDIT_CONFIG
from src.credit.models import DebtItem, DebtStructure

logger = logging.getLogger(__name__)


class DebtAnalyzer:
    """Analyzes issuer debt structure."""

    def __init__(self, config: Optional[StructureConfig] = None) -> None:
        self.config = config or DEFAULT_CREDIT_CONFIG.structure

    def analyze(
        self,
        symbol: str,
        debt_items: list[DebtItem],
        cash: float = 0.0,
        ebitda: float = 0.0,
        interest_expense: float = 0.0,
        equity_value: float = 0.0,
    ) -> DebtStructure:
        """Perform comprehensive debt structure analysis.

        Args:
            symbol: Issuer symbol.
            debt_items: List of debt instruments.
            cash: Cash and equivalents.
            ebitda: Trailing EBITDA.
            interest_expense: Annual interest expense.
            equity_value: Market equity value.

        Returns:
            DebtStructure with all computed metrics.
        """
        if not debt_items:
            return DebtStructure(symbol=symbol)

        total_debt = sum(d.amount for d in debt_items)
        net_debt = total_debt - cash

        # Leverage ratio (debt / EBITDA)
        leverage = total_debt / ebitda if ebitda > 0 else 0.0

        # Interest coverage (EBITDA / interest)
        coverage = ebitda / interest_expense if interest_expense > 0 else 0.0

        # Maturity profile
        maturities = [d.years_to_maturity for d in debt_items if d.maturity_date]
        amounts = [d.amount for d in debt_items if d.maturity_date]

        avg_maturity = 0.0
        if maturities and amounts:
            total_amt = sum(amounts)
            if total_amt > 0:
                avg_maturity = sum(
                    m * a for m, a in zip(maturities, amounts)
                ) / total_amt

        # Average coupon
        coupons = [d.coupon_rate for d in debt_items if d.coupon_rate > 0]
        avg_coupon = float(np.mean(coupons)) if coupons else 0.0

        # Near-term maturity percentage
        near_term = sum(
            d.amount for d in debt_items
            if d.maturity_date and d.years_to_maturity <= self.config.near_term_maturity_years
        )
        near_term_pct = near_term / total_debt if total_debt > 0 else 0.0

        # Refinancing risk
        refi_risk = self._refinancing_risk(near_term_pct, coverage, leverage)

        # Composite credit health (0-1, higher = healthier)
        health = self._credit_health(leverage, coverage, near_term_pct)

        return DebtStructure(
            symbol=symbol,
            total_debt=round(total_debt, 2),
            net_debt=round(net_debt, 2),
            leverage_ratio=round(leverage, 2),
            interest_coverage=round(coverage, 2),
            avg_maturity=round(avg_maturity, 2),
            avg_coupon=round(avg_coupon, 4),
            near_term_pct=round(near_term_pct, 4),
            refinancing_risk=round(refi_risk, 4),
            credit_health=round(health, 4),
        )

    def maturity_profile(self, debt_items: list[DebtItem]) -> list[dict]:
        """Build maturity wall profile.

        Groups debt by year of maturity.

        Returns:
            List of {year, amount, pct} sorted by year.
        """
        if not debt_items:
            return []

        total = sum(d.amount for d in debt_items)
        by_year: dict[int, float] = {}

        for d in debt_items:
            if d.maturity_date:
                year = d.maturity_date.year
                by_year[year] = by_year.get(year, 0) + d.amount

        return sorted(
            [
                {
                    "year": y,
                    "amount": amt,
                    "pct": round(amt / total, 4) if total > 0 else 0.0,
                }
                for y, amt in by_year.items()
            ],
            key=lambda x: x["year"],
        )

    def leverage_ratios(
        self,
        total_debt: float,
        equity: float,
        ebitda: float,
    ) -> dict:
        """Compute standard leverage ratios.

        Returns:
            Dict with debt_to_equity, debt_to_ebitda, debt_to_capital.
        """
        d_to_e = total_debt / equity if equity > 0 else 0.0
        d_to_ebitda = total_debt / ebitda if ebitda > 0 else 0.0
        d_to_cap = total_debt / (total_debt + equity) if (total_debt + equity) > 0 else 0.0

        return {
            "debt_to_equity": round(d_to_e, 2),
            "debt_to_ebitda": round(d_to_ebitda, 2),
            "debt_to_capital": round(d_to_cap, 4),
        }

    def _refinancing_risk(
        self, near_term_pct: float, coverage: float, leverage: float
    ) -> float:
        """Score refinancing risk (0-1, higher = more risk)."""
        # Near-term maturity component
        maturity_risk = min(near_term_pct / self.config.refinancing_risk_pct, 1.0)

        # Coverage component (low coverage = higher risk)
        if coverage <= 0:
            coverage_risk = 1.0
        elif coverage < self.config.low_coverage_threshold:
            coverage_risk = 1.0 - coverage / self.config.low_coverage_threshold
        else:
            coverage_risk = 0.0

        # Leverage component
        if leverage > self.config.high_leverage_threshold:
            leverage_risk = min(
                (leverage - self.config.high_leverage_threshold) / 4.0, 1.0
            )
        else:
            leverage_risk = 0.0

        return 0.4 * maturity_risk + 0.3 * coverage_risk + 0.3 * leverage_risk

    def _credit_health(
        self, leverage: float, coverage: float, near_term_pct: float
    ) -> float:
        """Compute composite credit health score (0-1)."""
        # Leverage score (lower = healthier)
        if leverage <= 0:
            lev_score = 1.0
        elif leverage <= 2.0:
            lev_score = 1.0
        elif leverage <= self.config.high_leverage_threshold:
            lev_score = 1.0 - (leverage - 2.0) / (self.config.high_leverage_threshold - 2.0)
        else:
            lev_score = max(0.0, 0.5 - (leverage - self.config.high_leverage_threshold) / 8.0)

        # Coverage score (higher = healthier)
        if coverage >= 4.0:
            cov_score = 1.0
        elif coverage >= self.config.low_coverage_threshold:
            cov_score = 0.5 + 0.5 * (coverage - self.config.low_coverage_threshold) / 2.0
        elif coverage > 0:
            cov_score = 0.5 * coverage / self.config.low_coverage_threshold
        else:
            cov_score = 0.0

        # Maturity score (lower near-term = healthier)
        mat_score = max(0.0, 1.0 - near_term_pct / 0.5)

        return 0.4 * lev_score + 0.35 * cov_score + 0.25 * mat_score
