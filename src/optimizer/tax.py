"""Tax-Aware Portfolio Management.

Tax-loss harvesting, wash sale detection, and tax-aware
rebalancing for portfolio optimization.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from src.optimizer.config import TaxConfig

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Portfolio position with cost basis."""

    symbol: str = ""
    shares: int = 0
    cost_basis: float = 0.0
    current_price: float = 0.0
    purchase_date: str = ""
    sector: str = ""

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return self.shares * (self.current_price - self.cost_basis)

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis <= 0:
            return 0.0
        return (self.current_price - self.cost_basis) / self.cost_basis

    @property
    def holding_days(self) -> int:
        if not self.purchase_date:
            return 0
        try:
            purchase = datetime.fromisoformat(self.purchase_date)
            return (datetime.now() - purchase).days
        except (ValueError, TypeError):
            return 0

    @property
    def is_long_term(self) -> bool:
        return self.holding_days >= 365


@dataclass
class HarvestCandidate:
    """Tax-loss harvest candidate."""

    position: Position = field(default_factory=Position)
    unrealized_loss: float = 0.0
    estimated_tax_savings: float = 0.0
    replacement: str = ""
    wash_sale_risk: bool = False
    days_to_long_term: int = 0

    def to_dict(self) -> dict:
        return {
            "symbol": self.position.symbol,
            "unrealized_loss": self.unrealized_loss,
            "estimated_tax_savings": self.estimated_tax_savings,
            "replacement": self.replacement,
            "wash_sale_risk": self.wash_sale_risk,
        }


@dataclass
class RebalanceTrade:
    """Tax-aware rebalance trade."""

    symbol: str = ""
    action: str = ""  # buy, sell
    shares: int = 0
    value: float = 0.0
    tax_impact: float = 0.0
    is_long_term: bool = False
    priority: int = 0  # Lower = sell first

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "shares": self.shares,
            "value": self.value,
            "tax_impact": self.tax_impact,
            "is_long_term": self.is_long_term,
        }


class TaxLossHarvester:
    """Identify and execute tax-loss harvesting opportunities.

    Finds positions with unrealized losses, computes tax savings,
    and suggests similar replacement securities.

    Example:
        harvester = TaxLossHarvester()
        candidates = harvester.identify_candidates(positions)
        total_savings = sum(c.estimated_tax_savings for c in candidates)
    """

    def __init__(self, config: Optional[TaxConfig] = None):
        self.config = config or TaxConfig()

    def identify_candidates(
        self,
        positions: list[Position],
        recent_sales: Optional[list[str]] = None,
    ) -> list[HarvestCandidate]:
        """Find positions eligible for tax-loss harvesting.

        Args:
            positions: Current portfolio positions.
            recent_sales: Symbols sold in last 30 days (wash sale check).

        Returns:
            List of HarvestCandidate sorted by tax savings.
        """
        recent_sales = recent_sales or []
        candidates = []

        for pos in positions:
            if pos.unrealized_pnl >= -self.config.min_harvest_loss:
                continue

            # Tax rate depends on holding period
            if pos.is_long_term:
                tax_rate = self.config.long_term_rate
            else:
                tax_rate = self.config.short_term_rate

            tax_savings = abs(pos.unrealized_pnl) * tax_rate

            # Wash sale risk
            wash_sale = pos.symbol in recent_sales

            # Days until long-term
            days_to_lt = max(0, self.config.long_term_threshold_days - pos.holding_days)

            candidates.append(HarvestCandidate(
                position=pos,
                unrealized_loss=pos.unrealized_pnl,
                estimated_tax_savings=tax_savings,
                wash_sale_risk=wash_sale,
                days_to_long_term=days_to_lt,
            ))

        candidates.sort(key=lambda c: c.estimated_tax_savings, reverse=True)
        return candidates

    def find_replacement(
        self,
        position: Position,
        universe: pd.DataFrame,
        factor_scores: Optional[pd.DataFrame] = None,
    ) -> str:
        """Find a replacement security with similar characteristics.

        Args:
            position: Position being harvested.
            universe: Available universe with sector info.
            factor_scores: Factor scores for similarity comparison.

        Returns:
            Replacement symbol or empty string.
        """
        # Filter to same sector
        if "sector" in universe.columns:
            sector_peers = universe[universe["sector"] == position.sector]
        else:
            sector_peers = universe

        # Remove the harvested symbol
        sector_peers = sector_peers[sector_peers.index != position.symbol]

        if sector_peers.empty:
            return ""

        if factor_scores is not None and position.symbol in factor_scores.index:
            target = factor_scores.loc[position.symbol]
            similarities = {}
            for peer in sector_peers.index:
                if peer in factor_scores.index:
                    peer_scores = factor_scores.loc[peer]
                    # Cosine similarity
                    common = target.index.intersection(peer_scores.index)
                    if len(common) > 0:
                        a = target[common].values.astype(float)
                        b = peer_scores[common].values.astype(float)
                        norm_a = np.linalg.norm(a)
                        norm_b = np.linalg.norm(b)
                        if norm_a > 0 and norm_b > 0:
                            sim = float(a @ b / (norm_a * norm_b))
                            similarities[peer] = sim

            if similarities:
                best = max(similarities, key=similarities.get)
                if similarities[best] >= self.config.harvest_replacement_min_similarity:
                    return best

        # Fallback: return first peer
        return str(sector_peers.index[0])

    def estimate_annual_savings(
        self,
        candidates: list[HarvestCandidate],
    ) -> dict:
        """Estimate total annual tax savings.

        Args:
            candidates: Harvest candidates.

        Returns:
            Dict with savings summary.
        """
        total_savings = sum(c.estimated_tax_savings for c in candidates)
        harvestable = sum(abs(c.unrealized_loss) for c in candidates)

        return {
            "total_tax_savings": total_savings,
            "total_harvestable_losses": harvestable,
            "num_candidates": len(candidates),
            "avg_savings_per_position": total_savings / len(candidates) if candidates else 0,
        }


class TaxAwareRebalancer:
    """Generate tax-aware rebalance trades.

    Prioritizes selling losers (harvest) over winners,
    considers holding periods, and estimates tax impact.

    Example:
        rebalancer = TaxAwareRebalancer()
        trades = rebalancer.generate_trades(current, target, positions)
    """

    def __init__(self, config: Optional[TaxConfig] = None):
        self.config = config or TaxConfig()

    def generate_trades(
        self,
        current_weights: pd.Series,
        target_weights: pd.Series,
        positions: list[Position],
        portfolio_value: float = 100_000,
    ) -> list[RebalanceTrade]:
        """Generate tax-optimized rebalance trades.

        Args:
            current_weights: Current portfolio weights.
            target_weights: Target portfolio weights.
            positions: Current positions with cost basis.
            portfolio_value: Total portfolio value.

        Returns:
            List of RebalanceTrade ordered by priority.
        """
        pos_map = {p.symbol: p for p in positions}
        all_symbols = set(current_weights.index) | set(target_weights.index)

        trades = []

        for symbol in all_symbols:
            current = current_weights.get(symbol, 0)
            target = target_weights.get(symbol, 0)
            delta = target - current

            if abs(delta) < 0.001:
                continue

            value = abs(delta) * portfolio_value
            pos = pos_map.get(symbol)

            if delta < 0:
                # Selling
                tax_impact = 0.0
                is_lt = False

                if pos and pos.unrealized_pnl > 0:
                    # Selling at a gain
                    gain_pct = delta / current if current > 0 else 0
                    realized_gain = abs(gain_pct) * pos.unrealized_pnl
                    is_lt = pos.is_long_term
                    rate = self.config.long_term_rate if is_lt else self.config.short_term_rate
                    tax_impact = realized_gain * rate
                elif pos and pos.unrealized_pnl < 0:
                    # Selling at a loss (tax benefit)
                    loss_pct = abs(delta / current) if current > 0 else 0
                    realized_loss = loss_pct * abs(pos.unrealized_pnl)
                    is_lt = pos.is_long_term
                    rate = self.config.long_term_rate if is_lt else self.config.short_term_rate
                    tax_impact = -realized_loss * rate  # Negative = savings

                # Priority: sell losers first (lower priority number)
                priority = 0 if (pos and pos.unrealized_pnl < 0) else 10
                # Defer gains near long-term threshold
                if pos and not pos.is_long_term:
                    days_to_lt = self.config.long_term_threshold_days - pos.holding_days
                    if 0 < days_to_lt <= 30 and pos.unrealized_pnl > 0:
                        priority = 20  # Defer

                trades.append(RebalanceTrade(
                    symbol=symbol,
                    action="sell",
                    value=value,
                    tax_impact=tax_impact,
                    is_long_term=is_lt,
                    priority=priority,
                ))
            else:
                # Buying
                trades.append(RebalanceTrade(
                    symbol=symbol,
                    action="buy",
                    value=value,
                    tax_impact=0.0,
                    priority=5,
                ))

        trades.sort(key=lambda t: t.priority)
        return trades

    def estimate_rebalance_tax(
        self,
        trades: list[RebalanceTrade],
    ) -> dict:
        """Estimate total tax impact of rebalance.

        Args:
            trades: Rebalance trades.

        Returns:
            Dict with tax impact summary.
        """
        total_tax = sum(t.tax_impact for t in trades)
        tax_cost = sum(t.tax_impact for t in trades if t.tax_impact > 0)
        tax_benefit = sum(abs(t.tax_impact) for t in trades if t.tax_impact < 0)

        return {
            "net_tax_impact": total_tax,
            "tax_cost": tax_cost,
            "tax_benefit": tax_benefit,
            "num_sell_trades": sum(1 for t in trades if t.action == "sell"),
            "num_buy_trades": sum(1 for t in trades if t.action == "buy"),
        }
