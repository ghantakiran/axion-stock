"""Portfolio Heat Tracker.

Tracks total risk exposure across all open positions
and enforces heat limits.
"""

import logging
from typing import Optional

from src.position_calculator.config import HeatConfig, DEFAULT_HEAT_CONFIG
from src.position_calculator.models import PositionRisk, PortfolioHeat

logger = logging.getLogger(__name__)


class HeatTracker:
    """Tracks portfolio heat (total risk exposure).

    Heat = sum of (position risk / account value) across all open positions.
    """

    def __init__(self, config: Optional[HeatConfig] = None) -> None:
        self.config = config or DEFAULT_HEAT_CONFIG
        self._positions: dict[str, PositionRisk] = {}

    def add_position(self, position: PositionRisk) -> None:
        """Add or update a position in the tracker."""
        self._positions[position.symbol] = position

    def remove_position(self, symbol: str) -> bool:
        """Remove a position from the tracker."""
        if symbol in self._positions:
            del self._positions[symbol]
            return True
        return False

    def update_price(self, symbol: str, price: float) -> None:
        """Update current price for a position."""
        pos = self._positions.get(symbol)
        if pos:
            pos.current_price = price

    def clear(self) -> None:
        """Remove all positions."""
        self._positions.clear()

    def compute_heat(self, account_value: float) -> PortfolioHeat:
        """Compute current portfolio heat.

        Args:
            account_value: Current account value.

        Returns:
            PortfolioHeat with breakdown by position.
        """
        if account_value <= 0:
            return PortfolioHeat(heat_limit_pct=self.config.max_heat_pct)

        position_heats: dict[str, float] = {}
        position_heat_dollars: dict[str, float] = {}
        total_heat_dollars = 0.0

        for symbol, pos in self._positions.items():
            if self.config.include_unrealized:
                risk = pos.risk_dollars
            else:
                risk = pos.initial_risk_dollars

            heat_pct = (risk / account_value) * 100
            position_heats[symbol] = heat_pct
            position_heat_dollars[symbol] = risk
            total_heat_dollars += risk

        total_heat_pct = (total_heat_dollars / account_value) * 100
        available = max(0, self.config.max_heat_pct - total_heat_pct)

        return PortfolioHeat(
            total_heat_pct=round(total_heat_pct, 2),
            total_heat_dollars=round(total_heat_dollars, 2),
            position_heats=position_heats,
            position_heat_dollars=position_heat_dollars,
            exceeds_limit=total_heat_pct >= self.config.max_heat_pct,
            at_warning=total_heat_pct >= self.config.warn_heat_pct,
            heat_limit_pct=self.config.max_heat_pct,
            available_heat_pct=round(available, 2),
            n_positions=len(self._positions),
        )

    def can_add_risk(self, account_value: float, additional_risk: float) -> bool:
        """Check if additional risk can be added within heat limits.

        Args:
            account_value: Current account value.
            additional_risk: Dollar risk of proposed trade.

        Returns:
            True if within heat limits.
        """
        heat = self.compute_heat(account_value)
        new_heat_pct = (additional_risk / account_value) * 100 if account_value > 0 else 0
        return (heat.total_heat_pct + new_heat_pct) <= self.config.max_heat_pct

    def max_additional_risk(self, account_value: float) -> float:
        """Maximum additional dollar risk allowed.

        Args:
            account_value: Current account value.

        Returns:
            Maximum additional risk in dollars.
        """
        heat = self.compute_heat(account_value)
        return account_value * (heat.available_heat_pct / 100.0)

    @property
    def positions(self) -> dict[str, PositionRisk]:
        """Current tracked positions."""
        return self._positions.copy()

    @property
    def n_positions(self) -> int:
        """Number of tracked positions."""
        return len(self._positions)
