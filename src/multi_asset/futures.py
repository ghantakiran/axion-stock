"""Futures Integration.

Contract management, roll logic, margin tracking, and spread trading.
"""

import logging
from datetime import date, timedelta
from typing import Optional

from src.multi_asset.config import (
    FuturesConfig,
    FuturesCategory,
    ContractSpec,
    DEFAULT_CONTRACT_SPECS,
    SUPPORTED_FUTURES,
    MarginAlertLevel,
)
from src.multi_asset.models import (
    FuturesContract,
    FuturesPosition,
    RollOrder,
    MarginStatus,
)

logger = logging.getLogger(__name__)

# Standard month codes
MONTH_CODES = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}
MONTH_TO_CODE = {v: k for k, v in MONTH_CODES.items()}


class FuturesManager:
    """Manages futures contracts, rolls, and margin.

    Features:
    - Contract specification lookup
    - Auto-roll detection and order generation
    - Margin utilization tracking with alert levels
    - Spread trade construction (calendar, inter-commodity)
    - P&L calculation with multiplier
    """

    def __init__(self, config: Optional[FuturesConfig] = None):
        self.config = config or FuturesConfig()
        self._specs = dict(DEFAULT_CONTRACT_SPECS)
        self._positions: dict[str, FuturesPosition] = {}
        self._margin_status = MarginStatus()

    def get_contract_spec(self, root: str) -> Optional[ContractSpec]:
        """Get contract specification by root symbol.

        Args:
            root: Root symbol (e.g. 'ES', 'CL').

        Returns:
            ContractSpec or None.
        """
        return self._specs.get(root.upper())

    def get_all_specs(self) -> dict[str, ContractSpec]:
        """Get all contract specifications."""
        return dict(self._specs)

    def get_front_month(self, root: str, as_of: Optional[date] = None) -> Optional[str]:
        """Determine the front-month contract symbol.

        Args:
            root: Root symbol.
            as_of: Reference date (defaults to today).

        Returns:
            Front month contract symbol (e.g. 'ESH25').
        """
        spec = self.get_contract_spec(root)
        if not spec:
            return None

        ref = as_of or date.today()
        month = ref.month
        year = ref.year % 100

        # Find next valid expiration month
        valid_months = [MONTH_CODES[m] for m in spec.expiration_months]

        for m in valid_months:
            if m >= month:
                code = MONTH_TO_CODE[m]
                return f"{root}{code}{year:02d}"

        # Wrap to next year
        code = MONTH_TO_CODE[valid_months[0]]
        return f"{root}{code}{(year + 1) % 100:02d}"

    def get_next_contract(self, root: str, current_month: str) -> Optional[str]:
        """Get the next contract after the current one.

        Args:
            root: Root symbol.
            current_month: Current contract month code (e.g. 'H25').

        Returns:
            Next contract symbol.
        """
        spec = self.get_contract_spec(root)
        if not spec or len(current_month) < 2:
            return None

        month_code = current_month[0]
        year = int(current_month[1:])

        valid_months = spec.expiration_months
        try:
            idx = valid_months.index(month_code)
        except ValueError:
            return None

        if idx + 1 < len(valid_months):
            next_code = valid_months[idx + 1]
            return f"{root}{next_code}{year:02d}"
        else:
            next_code = valid_months[0]
            return f"{root}{next_code}{(year + 1) % 100:02d}"

    def check_roll(
        self,
        position: FuturesPosition,
        current_date: Optional[date] = None,
    ) -> Optional[RollOrder]:
        """Check if a position needs to be rolled.

        Args:
            position: Current futures position.
            current_date: Reference date.

        Returns:
            RollOrder if roll is needed, None otherwise.
        """
        ref = current_date or date.today()

        if position.contract.expiry is None:
            return None

        days_to_expiry = (position.contract.expiry - ref).days

        if days_to_expiry <= self.config.roll_threshold_days:
            next_sym = self.get_next_contract(
                position.contract.root,
                position.contract.contract_month,
            )
            if not next_sym:
                return None

            return RollOrder(
                old_contract=position.contract.symbol,
                new_contract=next_sym,
                qty=position.qty,
                roll_date=ref,
                reason=f"expiry in {days_to_expiry} days",
            )

        return None

    def add_position(self, position: FuturesPosition):
        """Add or update a futures position.

        Args:
            position: Position to add.
        """
        self._positions[position.contract.symbol] = position
        self._update_margin()

    def remove_position(self, symbol: str):
        """Remove a position.

        Args:
            symbol: Contract symbol to remove.
        """
        self._positions.pop(symbol, None)
        self._update_margin()

    def get_position(self, symbol: str) -> Optional[FuturesPosition]:
        """Get a position by contract symbol."""
        return self._positions.get(symbol)

    def get_all_positions(self) -> list[FuturesPosition]:
        """Get all open positions."""
        return list(self._positions.values())

    def get_total_pnl(self) -> float:
        """Get total unrealized P&L across all positions."""
        return sum(pos.unrealized_pnl for pos in self._positions.values())

    def get_total_notional(self) -> float:
        """Get total notional value across all positions."""
        return sum(pos.notional_value for pos in self._positions.values())

    def get_margin_status(self) -> MarginStatus:
        """Get current margin status."""
        return self._margin_status

    def set_margin_available(self, amount: float):
        """Set total available margin (account equity).

        Args:
            amount: Available margin in USD.
        """
        self._margin_status.total_margin_available = amount
        self._update_margin()

    def _update_margin(self):
        """Recalculate margin utilization."""
        total_required = 0.0
        for pos in self._positions.values():
            total_required += pos.margin_required

        self._margin_status.total_margin_required = total_required
        self._margin_status.update()

    def build_calendar_spread(
        self,
        root: str,
        front_month: str,
        back_month: str,
        qty: int = 1,
    ) -> dict:
        """Build a calendar spread (sell front, buy back).

        Args:
            root: Root symbol.
            front_month: Front month code.
            back_month: Back month code.
            qty: Number of spreads.

        Returns:
            Spread details dict.
        """
        return {
            "type": "calendar_spread",
            "root": root,
            "front_leg": {"symbol": f"{root}{front_month}", "side": "sell", "qty": qty},
            "back_leg": {"symbol": f"{root}{back_month}", "side": "buy", "qty": qty},
            "max_loss": "limited to spread differential",
        }
