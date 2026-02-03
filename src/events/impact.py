"""Corporate Action Impact Estimation.

Estimates expected price impact from dividends (ex-date adjustment),
stock splits (liquidity effect), buybacks (EPS accretion), and
spinoffs (sum-of-parts value creation).
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.events.config import CorporateConfig, EventType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class DividendImpact:
    """Expected impact of a dividend event."""
    symbol: str = ""
    dividend_amount: float = 0.0
    current_price: float = 0.0
    ex_date_adjustment_pct: float = 0.0
    tax_adjusted_impact_pct: float = 0.0
    yield_signal: str = "neutral"  # attractive, neutral, low
    annualized_yield: float = 0.0

    @property
    def yield_bps(self) -> float:
        return self.annualized_yield * 10_000

    @property
    def is_high_yield(self) -> bool:
        return self.annualized_yield >= 0.04


@dataclass
class SplitImpact:
    """Expected impact of a stock split."""
    symbol: str = ""
    split_ratio: float = 0.0  # e.g., 4.0 for 4:1
    pre_split_price: float = 0.0
    post_split_price: float = 0.0
    liquidity_effect_pct: float = 0.0
    retail_flow_estimate_pct: float = 0.0
    historical_avg_impact_pct: float = 0.0

    @property
    def total_expected_impact_pct(self) -> float:
        return self.liquidity_effect_pct + self.retail_flow_estimate_pct


@dataclass
class BuybackImpact:
    """Expected impact of a share buyback."""
    symbol: str = ""
    buyback_amount: float = 0.0
    market_cap: float = 0.0
    shares_outstanding: float = 0.0
    current_eps: float = 0.0
    buyback_pct: float = 0.0
    eps_accretion_pct: float = 0.0
    shares_reduced: float = 0.0
    new_eps: float = 0.0
    price_support_estimate_pct: float = 0.0

    @property
    def is_significant(self) -> bool:
        return self.buyback_pct >= 0.02

    @property
    def total_expected_impact_pct(self) -> float:
        return self.eps_accretion_pct + self.price_support_estimate_pct


@dataclass
class SpinoffImpact:
    """Expected impact of a spinoff."""
    symbol: str = ""
    parent_value: float = 0.0
    spinoff_value: float = 0.0
    combined_value: float = 0.0
    current_market_cap: float = 0.0
    value_creation_pct: float = 0.0
    conglomerate_discount_pct: float = 0.0

    @property
    def has_value_creation(self) -> bool:
        return self.value_creation_pct > 0


@dataclass
class ImpactSummary:
    """Summary of all corporate action impacts for a symbol."""
    symbol: str = ""
    n_actions: int = 0
    total_expected_impact_pct: float = 0.0
    dividend_impact_pct: float = 0.0
    buyback_impact_pct: float = 0.0
    split_impact_pct: float = 0.0
    spinoff_impact_pct: float = 0.0
    net_signal: str = "neutral"  # positive, negative, neutral

    @property
    def is_positive(self) -> bool:
        return self.total_expected_impact_pct > 0.5


# ---------------------------------------------------------------------------
# Impact Estimator
# ---------------------------------------------------------------------------
class CorporateActionImpactEstimator:
    """Estimates price impact of corporate actions."""

    def __init__(self, config: Optional[CorporateConfig] = None) -> None:
        self.config = config or CorporateConfig()

    def estimate_dividend_impact(
        self,
        symbol: str,
        dividend_amount: float,
        current_price: float,
        frequency: int = 4,
        tax_rate: float = 0.15,
    ) -> DividendImpact:
        """Estimate impact of a dividend payment.

        Args:
            symbol: Ticker symbol.
            dividend_amount: Per-share dividend amount.
            current_price: Current stock price.
            frequency: Dividends per year (4 = quarterly).
            tax_rate: Applicable dividend tax rate.

        Returns:
            DividendImpact with ex-date adjustment and yield analysis.
        """
        if current_price <= 0 or dividend_amount <= 0:
            return DividendImpact(symbol=symbol)

        # Ex-date price adjustment
        ex_date_adj = -dividend_amount / current_price
        tax_adj = ex_date_adj * (1 - tax_rate)

        # Annualized yield
        ann_yield = (dividend_amount * frequency) / current_price

        # Yield signal
        if ann_yield >= 0.04:
            signal = "attractive"
        elif ann_yield >= 0.02:
            signal = "neutral"
        else:
            signal = "low"

        return DividendImpact(
            symbol=symbol,
            dividend_amount=round(dividend_amount, 4),
            current_price=round(current_price, 2),
            ex_date_adjustment_pct=round(ex_date_adj, 6),
            tax_adjusted_impact_pct=round(tax_adj, 6),
            yield_signal=signal,
            annualized_yield=round(ann_yield, 6),
        )

    def estimate_split_impact(
        self,
        symbol: str,
        split_ratio: float,
        current_price: float,
        avg_daily_volume: float = 0.0,
    ) -> SplitImpact:
        """Estimate impact of a stock split.

        Research shows splits generate ~2-5% positive abnormal returns
        due to increased liquidity and retail participation.

        Args:
            symbol: Ticker symbol.
            split_ratio: Split ratio (e.g., 4.0 for 4:1 split).
            current_price: Pre-split price.
            avg_daily_volume: Average daily volume.

        Returns:
            SplitImpact with liquidity and flow estimates.
        """
        if split_ratio <= 1 or current_price <= 0:
            return SplitImpact(symbol=symbol)

        post_price = current_price / split_ratio

        # Liquidity effect: lower price = higher volume
        # Empirical: ~1-3% boost from increased accessibility
        if post_price < 50:
            liquidity_pct = 0.02
        elif post_price < 200:
            liquidity_pct = 0.015
        else:
            liquidity_pct = 0.01

        # Retail flow: lower price attracts retail investors
        # Higher split ratio = more retail interest
        retail_pct = min(0.03, 0.005 * np.log(split_ratio + 1))

        # Historical average split impact
        historical_avg = 0.025  # ~2.5% average

        return SplitImpact(
            symbol=symbol,
            split_ratio=round(split_ratio, 2),
            pre_split_price=round(current_price, 2),
            post_split_price=round(post_price, 2),
            liquidity_effect_pct=round(float(liquidity_pct), 4),
            retail_flow_estimate_pct=round(float(retail_pct), 4),
            historical_avg_impact_pct=round(historical_avg, 4),
        )

    def estimate_buyback_impact(
        self,
        symbol: str,
        buyback_amount: float,
        market_cap: float,
        shares_outstanding: float,
        current_eps: float,
        current_price: float,
        net_income: float = 0.0,
    ) -> BuybackImpact:
        """Estimate impact of a share buyback program.

        Args:
            symbol: Ticker symbol.
            buyback_amount: Total buyback authorization.
            market_cap: Current market capitalization.
            shares_outstanding: Shares outstanding.
            current_eps: Current trailing EPS.
            current_price: Current stock price.
            net_income: Annual net income.

        Returns:
            BuybackImpact with EPS accretion and price support estimates.
        """
        if market_cap <= 0 or shares_outstanding <= 0 or current_price <= 0:
            return BuybackImpact(symbol=symbol)

        buyback_pct = buyback_amount / market_cap
        shares_reduced = buyback_amount / current_price
        new_shares = shares_outstanding - shares_reduced

        # EPS accretion
        if new_shares > 0 and current_eps > 0:
            if net_income > 0:
                new_eps = net_income / new_shares
            else:
                new_eps = current_eps * (shares_outstanding / new_shares)
            eps_accretion = (new_eps - current_eps) / current_eps
        else:
            new_eps = current_eps
            eps_accretion = 0.0

        # Price support: buyback reduces supply
        # Empirical: ~0.5-1% for each 1% buyback
        price_support = buyback_pct * 0.75

        return BuybackImpact(
            symbol=symbol,
            buyback_amount=round(buyback_amount, 2),
            market_cap=round(market_cap, 2),
            shares_outstanding=round(shares_outstanding, 0),
            current_eps=round(current_eps, 4),
            buyback_pct=round(buyback_pct, 6),
            eps_accretion_pct=round(eps_accretion, 6),
            shares_reduced=round(shares_reduced, 0),
            new_eps=round(new_eps, 4),
            price_support_estimate_pct=round(price_support, 6),
        )

    def estimate_spinoff_impact(
        self,
        symbol: str,
        current_market_cap: float,
        parent_estimated_value: float,
        spinoff_estimated_value: float,
    ) -> SpinoffImpact:
        """Estimate impact of a corporate spinoff.

        Spinoffs historically unlock value by removing the conglomerate
        discount and allowing focused management.

        Args:
            symbol: Ticker symbol.
            current_market_cap: Current combined market cap.
            parent_estimated_value: Estimated standalone parent value.
            spinoff_estimated_value: Estimated standalone spinoff value.

        Returns:
            SpinoffImpact with value creation estimate.
        """
        if current_market_cap <= 0:
            return SpinoffImpact(symbol=symbol)

        combined = parent_estimated_value + spinoff_estimated_value
        value_creation = (combined - current_market_cap) / current_market_cap
        conglomerate_discount = max(0, value_creation)

        return SpinoffImpact(
            symbol=symbol,
            parent_value=round(parent_estimated_value, 2),
            spinoff_value=round(spinoff_estimated_value, 2),
            combined_value=round(combined, 2),
            current_market_cap=round(current_market_cap, 2),
            value_creation_pct=round(value_creation, 6),
            conglomerate_discount_pct=round(conglomerate_discount, 6),
        )

    def summarize_impacts(
        self,
        symbol: str,
        impacts: list,
    ) -> ImpactSummary:
        """Summarize all corporate action impacts for a symbol.

        Args:
            symbol: Ticker symbol.
            impacts: List of impact dataclasses.

        Returns:
            ImpactSummary with net effect.
        """
        if not impacts:
            return ImpactSummary(symbol=symbol)

        div_pct = 0.0
        buyback_pct = 0.0
        split_pct = 0.0
        spinoff_pct = 0.0

        for imp in impacts:
            if isinstance(imp, DividendImpact):
                div_pct += imp.annualized_yield
            elif isinstance(imp, BuybackImpact):
                buyback_pct += imp.total_expected_impact_pct
            elif isinstance(imp, SplitImpact):
                split_pct += imp.total_expected_impact_pct
            elif isinstance(imp, SpinoffImpact):
                spinoff_pct += imp.value_creation_pct

        total = div_pct + buyback_pct + split_pct + spinoff_pct

        if total > 1.0:
            signal = "positive"
        elif total < -0.5:
            signal = "negative"
        else:
            signal = "neutral"

        return ImpactSummary(
            symbol=symbol,
            n_actions=len(impacts),
            total_expected_impact_pct=round(total, 4),
            dividend_impact_pct=round(div_pct, 4),
            buyback_impact_pct=round(buyback_pct, 4),
            split_impact_pct=round(split_pct, 4),
            spinoff_impact_pct=round(spinoff_pct, 4),
            net_signal=signal,
        )
